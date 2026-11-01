"""Write the scripted Meta replies for e2e's dry-run spec: `uv run python -m tests.record_dry_run`.
Free: no call reaches the Meta API.

e2e compiles PLACED, whose compile is scripted here (placed_compile): one Phrase with a visual
Criterion. Compiling it asks that Criterion of e2e's Dev set Episode in the background (the dry
run), and Spark's answers are scripted as `tests.record_visual` scripts them: every sample
passes. That Episode has its own instruction, so the Reference labeller never changes the prompt.

This replays RECORDINGS to ingest that Episode into e2e's Dev set, then runs the compile and the
dry run once, keeping the replies RECORDINGS doesn't have. Rerun after changing the compile
prompt or schema, the anchor pool's capabilities manifest, the visual prompt or how clips are
cut; e2e then fails with UnrecordedCallError until you do.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from tests.record_meta import E2E_DEV_SET, E2E_EPISODES, RECORDINGS
from tests.record_visual import ScriptedAnswers
from tests.rubric.scripted import phrase, video_criterion
from tests.visual.scripted import response_format
from winnow.core.context import AppContext, build_context
from winnow.core.settings import get_settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.service import ingest_items
from winnow.episodes.store import episode_id
from winnow.jobs.models import WorkItem
from winnow.meta.models import MetaContent
from winnow.meta.replay import RecordingTransport, ReplayTransport
from winnow.meta.transport import Reply
from winnow.rubric.service import compile_draft
from winnow.visual.service import DRY_RUN
from winnow.visual.steps import draft_visual_items

DRY_RUN_ANSWERS = Path(__file__).parent / "recordings" / "dry_run_answers.jsonl"
IN_BOWL = "leaves the block in the bowl"
PLACED = f"Neat place: {IN_BOWL}."  # e2e's dry-run spec compiles it
QUESTION = "Is the block resting inside the bowl when the clip ends?"
PARAPHRASES = [
    "Once the gripper lets go, does the block stay inside the bowl?",
    "At the end, is the block in the bowl rather than beside it?",
]
USAGE = {"input_tokens": 6000, "output_tokens": 400}


def placed_compile() -> dict[str, object]:
    return {
        "phrases": [
            phrase("Neat place", "context", reason="Names the task."),
            phrase(IN_BOWL, criteria=[video_criterion(QUESTION, PARAPHRASES)]),
        ]
    }


class ScriptedDryRun(ScriptedAnswers):
    """Answers PLACED's compile with placed_compile, and every visual sample as
    `tests.record_visual` does; replays RECORDINGS else."""

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        asked = "\n".join(str(part.get("text")) for part in content)
        if response_format(options) == "rubric" and json.dumps(PLACED) in asked:
            return Reply(json.dumps(placed_compile()), USAGE)
        return await super().respond(model, content, options)


async def _run(ctx: AppContext, items: list[WorkItem]) -> None:
    job_id = ctx.jobs.create(DRY_RUN, items)
    await ctx.runner.run(job_id)
    job = ctx.jobs.get(job_id)
    assert job is not None
    for item in job.items:
        sys.stdout.write(f"{item.label} {item.step}: {item.status} {item.detail or ''}\n")


async def _record(ctx: AppContext) -> None:
    dev = [episode_id("droid_100", i) for i in E2E_DEV_SET]
    job_id = ctx.jobs.create("ingest", ingest_items("droid_100", list(E2E_DEV_SET), with_meta=True))
    await ctx.runner.run(job_id)
    ctx.sets.add("dev", dev)
    draft = await compile_draft(ctx, PLACED, fresh=True)
    asks = [(e, c) for e in dev for c in draft.rubric().criteria if c.kind == "visual"]
    sys.stdout.write(f"compile: {[(c.phrase, c.id) for _, c in asks]}\n")
    await _run(ctx, draft_visual_items(draft, asks))


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
        transport = RecordingTransport(ScriptedDryRun(ReplayTransport(RECORDINGS)), everything)
        ctx = build_context(settings, transport)
        try:
            asyncio.run(_record(ctx))
        finally:
            ctx.db.close()
        recorded = {json.loads(line)["key"] for line in RECORDINGS.read_text().splitlines()}
        lines: list[str] = []
        for line in everything.read_text().splitlines():
            key = json.loads(line)["key"]
            if key not in recorded:
                recorded.add(key)
                lines.append(line)
    DRY_RUN_ANSWERS.write_text("".join(line + "\n" for line in lines))
    sys.stdout.write(f"wrote {len(lines)} scripted dry-run replies to {DRY_RUN_ANSWERS.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
