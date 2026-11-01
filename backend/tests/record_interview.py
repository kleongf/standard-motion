"""Write the scripted Meta replies for e2e's interview specs:
`uv run python -m tests.record_interview`. Free: no call reaches the Meta API.

The recorded compile of the frozen Description gives each Phrase one Criterion, so its Criteria
never disagree. e2e's disagree spec compiles DISAGREE instead, whose compile is scripted here
(disagree_compile): a Phrase whose two Criteria disagree on e2e's Dev set Episode, which grasps
once but keeps the arm moving well over a second.

Answers in the curator's own words are scripted on STEADY, whose first question is about the
Unsupported Phrase NEVER_DROPS: PICK_TEXT maps onto its Context answer, CHANGE_TEXT compiles it
again (clarified_compile), and EDIT_TEXT, with no question, edits STEADY into STEADY_EDITED, whose
new text compiles as edit_compile. Each is answered on STEADY freshly compiled.

This replays RECORDINGS to ingest that Episode into e2e's Dev set, then runs the real calls
once, keeping the replies RECORDINGS doesn't have.
Rerun after changing the compile prompt or schema, or the anchor pool's capabilities manifest;
e2e then fails with UnrecordedCallError until you do.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from tests.meta.fakes import NoTranscribe
from tests.record_meta import E2E_DEV_SET, E2E_EPISODES, RECORDINGS
from tests.rubric.scripted import criterion, phrase
from winnow.core.context import AppContext, build_context
from winnow.core.settings import get_settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.service import ingest_items
from winnow.episodes.store import episode_id
from winnow.interview.models import TextDraw
from winnow.interview.service import current
from winnow.interview.text import answer_text
from winnow.interview.text_prompt import MAPPING_SCHEMA_NAME, REWRITE_SCHEMA_NAME
from winnow.meta.models import MetaContent
from winnow.meta.replay import RecordingTransport, ReplayTransport
from winnow.meta.transport import Reply
from winnow.rubric.service import compile_draft

INTERVIEW_ANSWERS = Path(__file__).parent / "recordings" / "interview_answers.jsonl"
CAREFUL = "grasps it once and quickly"
DISAGREE = f"Careful pick: {CAREFUL}."  # e2e/describe-interview-disagree.spec.ts compiles it
USAGE = {"input_tokens": 6000, "output_tokens": 400}

NEVER_DROPS = "never drops it"
STEADY = f"Steady pick: grasps it once, {NEVER_DROPS}."  # e2e's free-text specs compile it
STEADY_EDITED = f"Steady pick: grasps it once, {NEVER_DROPS}, within 20 s."
WITHIN = "within 20 s"
PICK_TEXT = "That's just how a steady pick looks, there's nothing to check."
PICKED = "Marked “never drops it” Context: it describes, it doesn't require."
CHANGE_TEXT = "It means it grasps once and holds on: it never needs a second grasp."
CHANGED = "I'll check “never drops it” as a single grasp."
EDIT_TEXT = "It should also finish within 20 seconds."
EDITED = "Added “within 20 s” to the Description."


def disagree_compile() -> dict[str, object]:
    """One grasp attempt passes; the arm moving under a second fails."""
    once = criterion("grasp_attempts", "<=", 1)
    quickly = criterion("active_duration_s", "<", 1)
    return {
        "phrases": [
            phrase("Careful pick", "context", reason="Names the task."),
            phrase(CAREFUL, criteria=[once, quickly]),
        ]
    }


def steady_compile() -> dict[str, object]:
    once = criterion("grasp_attempts", "<=", 1)
    return {
        "phrases": [
            phrase("Steady pick", "context", reason="Names the task."),
            phrase("grasps it once", criteria=[once]),
            phrase(NEVER_DROPS, "unsupported", reason="Nothing tracks the object yet."),
        ]
    }


def clarified_compile() -> dict[str, object]:
    return {"phrases": [phrase(NEVER_DROPS, criteria=[criterion("grasp_attempts", "<=", 1)])]}


def edit_compile() -> dict[str, object]:
    return {"phrases": [phrase(WITHIN, criteria=[criterion("active_duration_s", "<", 20)])]}


# (response format, text in the request, the scripted answer), first match wins: the clarify
# and edit compiles also hold STEADY.
SCRIPT: list[tuple[str, str, object]] = [
    ("rubric", DISAGREE, disagree_compile()),
    ("rubric", json.dumps(CHANGE_TEXT), clarified_compile()),
    ("rubric", json.dumps(STEADY_EDITED), edit_compile()),
    ("rubric", json.dumps(STEADY), steady_compile()),
    (MAPPING_SCHEMA_NAME, json.dumps(PICK_TEXT), {"choice": "context", "reply": PICKED}),
    (MAPPING_SCHEMA_NAME, json.dumps(CHANGE_TEXT), {"choice": "change", "reply": CHANGED}),
    (REWRITE_SCHEMA_NAME, json.dumps(EDIT_TEXT), {"description": STEADY_EDITED, "reply": EDITED}),
]


def _scripted(content: MetaContent, options: dict[str, object]) -> object | None:
    text_format = options.get("text")
    if not isinstance(text_format, dict):
        return None
    name = text_format["format"]["name"]  # pyright: ignore[reportUnknownVariableType]
    asked = "\n".join(str(part.get("text")) for part in content)
    return next((a for n, marker, a in SCRIPT if n == name and marker in asked), None)


class ScriptedInterview(NoTranscribe):
    """Replays RECORDINGS; answers the calls SCRIPT names as it says."""

    def __init__(self, replay: ReplayTransport) -> None:
        self._replay = replay

    async def upload(self, path: Path) -> str:
        return await self._replay.upload(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return await self._replay.count_tokens(model, content)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        answer = _scripted(content, options)
        if answer is None:
            return await self._replay.respond(model, content, options)
        return Reply(json.dumps(answer), USAGE)


async def _record(ctx: AppContext) -> None:
    job_id = ctx.jobs.create("ingest", ingest_items("droid_100", list(E2E_DEV_SET), with_meta=True))
    await ctx.runner.run(job_id)
    ctx.sets.add("dev", [episode_id("droid_100", i) for i in E2E_DEV_SET])
    draft = await compile_draft(ctx, DISAGREE, fresh=True)
    sys.stdout.write(f"compile: {[(c.phrase, c.id) for c in draft.criteria]}\n")
    for text, asked in ((PICK_TEXT, True), (CHANGE_TEXT, True), (EDIT_TEXT, False)):
        await compile_draft(ctx, STEADY, fresh=True)
        question = current(ctx).question
        key = question.key if asked and question is not None else None
        said = await answer_text(ctx, TextDraw(text=text, question_key=key))
        sys.stdout.write(f"{text!r}: {said.reply} {[c.id for c in said.draft.criteria]}\n")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = write_fixture_source(Path(tmp) / "droid_100", episodes=E2E_EPISODES)
        settings = get_settings().model_copy(
            update={
                "data_dir": Path(tmp) / "data",
                "droid100_root": root,
                "meta_replay": None,
                "model_api_key": None,
            }
        )
        everything = Path(tmp) / "replies.jsonl"
        transport = RecordingTransport(ScriptedInterview(ReplayTransport(RECORDINGS)), everything)
        ctx = build_context(settings, transport)
        try:
            asyncio.run(_record(ctx))
        finally:
            ctx.db.close()
        recorded = {json.loads(line)["key"] for line in RECORDINGS.read_text().splitlines()}
        lines: list[str] = []
        for line in everything.read_text().splitlines():  # each fresh compile of STEADY again
            key = json.loads(line)["key"]
            if key not in recorded:
                recorded.add(key)
                lines.append(line)
    INTERVIEW_ANSWERS.write_text("".join(line + "\n" for line in lines))
    sys.stdout.write(f"wrote {len(lines)} scripted interview replies to {INTERVIEW_ANSWERS.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
