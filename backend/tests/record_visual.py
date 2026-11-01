"""Write hand-written Spark answers for the e2e fixture Episodes' visual Criteria:
`uv run python -m tests.record_visual`. Free: no call reaches the Meta API.

The fixture videos are test patterns, so a real Spark answer about them would mean nothing;
these answers are scripted here instead (SCRIPTED), in the replay format, so e2e's Workstation
and Triage tabs are deterministic. Ingest replays RECORDINGS; the seeded Rubric's visual
Criteria are then asked of every e2e Episode, unboxed, both before and after the Reference
labeller writes the missing instructions (e2e asks in either order). Rerun after changing the
seeded visual Criteria, the visual prompt, how clips are cut, or the fixture Episodes; e2e then
fails with UnrecordedCallError until you do.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from tests.meta.fakes import NoTranscribe
from tests.record_meta import E2E_EPISODES, RECORDINGS
from winnow.core.context import AppContext, build_context
from winnow.core.settings import get_settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.service import ingest_items
from winnow.episodes.store import episode_id
from winnow.jobs.models import WorkItem
from winnow.meta.models import MetaContent
from winnow.meta.replay import RecordingTransport, ReplayTransport
from winnow.meta.transport import Reply
from winnow.visual.models import AnswerValue
from winnow.visual.steps import visual_items

VISUAL_ANSWERS = Path(__file__).parent / "recordings" / "visual_answers.jsonl"
# Per fixture Episode folder, each sample's answer in the order asked; every sample passes else.
# Episode 10 (the Workstation spec's SECOND) splits 2-1, so e2e can show a split's samples.
SCRIPTED: dict[str, tuple[AnswerValue, ...]] = {"000010": ("pass", "fail", "pass")}
WRITTEN_INSTRUCTION = "Put the block in the bowl"  # what e2e's referenceLabel writes
USAGE = {"input_tokens": 9000, "output_tokens": 120}


class ScriptedAnswers(NoTranscribe):
    """Replays RECORDINGS, and answers each visual sample from SCRIPTED."""

    def __init__(self, replay: ReplayTransport) -> None:
        self._replay = replay
        self._asked: dict[str, int] = {}

    async def upload(self, path: Path) -> str:
        return await self._replay.upload(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 0

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "visual":
            return await self._replay.respond(model, content, options)
        clip = str(content[1]["file_id"])
        sample = self._asked.get(clip, 0)
        self._asked[clip] = sample + 1
        answers = SCRIPTED.get(clip.split("/")[0], ("pass",) * 3)
        answer = answers[sample % len(answers)]
        seen = {
            "pass": "The object rests inside the target when the clip ends.",
            "fail": "The object ends beside the target, not in it.",
            "unsure": "The target is out of view at the end.",
        }[answer]
        reply = {"answer": answer, "confidence": 0.8, "observation": seen}
        return Reply(json.dumps(reply), USAGE)


async def _run(ctx: AppContext, kind: str, items: list[WorkItem]) -> None:
    job_id = ctx.jobs.create(kind, items)
    await ctx.runner.run(job_id)
    job = ctx.jobs.get(job_id)
    assert job is not None
    for item in job.items:
        sys.stdout.write(f"{item.label} {item.step}: {item.status} {item.detail or ''}\n")


async def _record(ctx: AppContext) -> None:
    indices = list(range(E2E_EPISODES))
    ids = [episode_id("droid_100", i) for i in indices]
    await _run(ctx, "ingest", ingest_items("droid_100", indices, with_meta=True))
    await _run(ctx, "visual", visual_items(ctx.rubrics.latest(), ids))
    for episode in ctx.episodes.list():
        if not episode.instruction:
            ctx.episodes.write_instruction(episode.id, WRITTEN_INSTRUCTION)
    await _run(ctx, "visual", visual_items(ctx.rubrics.latest(), ids))


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
        transport = RecordingTransport(ScriptedAnswers(ReplayTransport(RECORDINGS)), everything)
        ctx = build_context(settings, transport)
        try:
            asyncio.run(_record(ctx))
        finally:
            ctx.db.close()
        recorded = {json.loads(line)["key"] for line in RECORDINGS.read_text().splitlines()}
        lines = [
            line
            for line in everything.read_text().splitlines()
            if json.loads(line)["key"] not in recorded
        ]
    VISUAL_ANSWERS.write_text("".join(line + "\n" for line in lines))
    sys.stdout.write(f"wrote {len(lines)} scripted visual answers to {VISUAL_ANSWERS.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
