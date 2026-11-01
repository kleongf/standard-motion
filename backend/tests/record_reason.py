"""Write the scripted Meta reply for e2e's Spark Reason: `uv run python -m tests.record_reason`.
Free: no call reaches the Meta API.

e2e's reason spec queues Spark's Reasons and opens its Episode's Workstation. That Episode is
rejected for two failed grasp attempts before the grasp, so Spark's Reason is scripted here
(written_reason) to cite exactly those three times, the first failed attempt first. This replays
RECORDINGS to ingest the Episode, gives it a Reference label as e2e does, then runs the real
`reason` step once, keeping the reply RECORDINGS doesn't have. Rerun after changing the reason
prompt or schema, or what decides that Episode; e2e's Reason then stays the template one.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from tests.meta.fakes import NoTranscribe
from tests.record_meta import E2E_EPISODES, RECORDINGS
from winnow.baseline.prompts import FROZEN
from winnow.core.context import AppContext, build_context
from winnow.core.settings import get_settings
from winnow.criteria.measured import seconds
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.service import ingest_items
from winnow.episodes.store import episode_id
from winnow.meta.models import MetaContent
from winnow.meta.replay import RecordingTransport, ReplayTransport
from winnow.meta.transport import Reply
from winnow.reference_labels.models import PhraseLabel, ReferenceLabelDraw
from winnow.reference_labels.service import save_label
from winnow.triage.reason_service import reason_items
from winnow.triage.service import template_triages
from winnow.triage.spark_reason import deciding

REASON_ANSWERS = Path(__file__).parent / "recordings" / "reason_answers.jsonl"
REASON_EPISODE = 20  # the reason spec's (EPISODES.reason in e2e/helpers.ts)
WRITTEN_INSTRUCTION = "Put the block in the bowl"  # what e2e's referenceLabel writes
USAGE = {"input_tokens": 1500, "output_tokens": 60}


def written_reason(first: float, second: float, grasp: float) -> list[dict[str, object]]:
    """Spark's Reason for an Episode that closed on nothing twice before its grasp."""
    return [
        {"text": "The gripper closed on nothing at ", "t": None},
        {"text": seconds(first), "t": first},
        {"text": " and again at ", "t": None},
        {"text": seconds(second), "t": second},
        {"text": ", only holding the object from ", "t": None},
        {"text": seconds(grasp), "t": grasp},
        {"text": ", so it wasn't grasped on the first try.", "t": None},
    ]


class ScriptedReason(NoTranscribe):
    """Replays RECORDINGS; writes `spans` as Spark's Reason."""

    def __init__(self, replay: ReplayTransport) -> None:
        self._replay = replay
        self.spans: list[dict[str, object]] = []

    async def upload(self, path: Path) -> str:
        return await self._replay.upload(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 0

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "reason":
            return await self._replay.respond(model, content, options)
        return Reply(json.dumps({"spans": self.spans}), USAGE)


async def _record(ctx: AppContext, spark: ScriptedReason) -> None:
    job_id = ctx.jobs.create("ingest", ingest_items("droid_100", [REASON_EPISODE], with_meta=True))
    await ctx.runner.run(job_id)
    episode = ctx.episodes.get(episode_id("droid_100", REASON_EPISODE))
    assert episode is not None
    phrases = [PhraseLabel(phrase=p, passed=True) for p in FROZEN.phrases]
    draw = ReferenceLabelDraw(phrases=phrases, instruction=WRITTEN_INSTRUCTION, elapsed_s=10)
    save_label(ctx, episode, draw)
    _, [triage] = template_triages(ctx, [episode])
    assert triage.decision == "reject", triage.decision
    first, second, grasp = (m.t for m in deciding(triage)[0].moments)
    spark.spans = written_reason(first, second, grasp)
    job_id = ctx.jobs.create("reason", reason_items(ctx))
    await ctx.runner.run(job_id)
    job = ctx.jobs.get(job_id)
    assert job is not None and job.done == 1, job
    sys.stdout.write(f"{episode.id}: {''.join(str(s['text']) for s in spark.spans)}\n")


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
        spark = ScriptedReason(ReplayTransport(RECORDINGS))
        ctx = build_context(settings, RecordingTransport(spark, everything))
        try:
            asyncio.run(_record(ctx, spark))
        finally:
            ctx.db.close()
        recorded = {json.loads(line)["key"] for line in RECORDINGS.read_text().splitlines()}
        lines = [
            line
            for line in everything.read_text().splitlines()
            if json.loads(line)["key"] not in recorded
        ]
    REASON_ANSWERS.write_text("".join(line + "\n" for line in lines))
    sys.stdout.write(f"wrote {len(lines)} scripted Reason replies to {REASON_ANSWERS.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
