"""Re-record the Meta responses that tests and e2e replay: `uv run python -m tests.record_meta`.

Runs the real ingest pipeline (Spark-alone baseline and wrist track) against the Meta API on the
e2e fixture Episodes, compiles the frozen Description against e2e's Dev set and recompiles it
with one Phrase edited (EDITED), then boxes each Episode with E2E_BOX in each exterior view in
turn and runs what a saved box queues (exterior track and target box), writing every reply to
RECORDINGS. Costs about $0.80, which is added to the main cost log. Re-record after changing a
prompt, a schema or the fixture Episodes.

With `--missing`, replies already recorded are replayed and only the calls missing from
RECORDINGS (a changed compile prompt, a new edit, a new fixture Episode) are made for real, their
clips uploaded, and appended; only their cost is logged. Cents, not dollars.
"""

import asyncio
import json
import shutil
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from winnow.baseline.prompts import FROZEN
from winnow.boxes.models import BoxDraw, ExteriorCamera
from winnow.core.context import AppContext, build_context
from winnow.core.settings import Settings, get_settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.service import ingest_items
from winnow.episodes.store import episode_id
from winnow.jobs.models import WorkItem
from winnow.meta.audio import wav_duration_ms
from winnow.meta.costs import CostEntry
from winnow.meta.limits import DEFAULT_LIMITS
from winnow.meta.models import MetaContent, Transcript
from winnow.meta.openai_transport import OpenAITransport
from winnow.meta.pricing import SAM, sam_cost, spark_cost, transcribe_cost
from winnow.meta.replay import RecordingTransport, ReplayTransport, UnrecordedCallError
from winnow.meta.transport import Reply, Transport
from winnow.rubric.service import compile_draft
from winnow.tracking.exterior import box_items

RECORDINGS = Path(__file__).parent / "recordings" / "fixture_episodes.jsonl"
E2E_EPISODES = 24  # what scripts/e2e-server.ts writes
# e2e's Dev set (DEV_SET in e2e/helpers.ts), which compile's anchor-pool ranges come from.
# Fixture Episode 0 has the same robot data, so backend tests compile against it as well.
E2E_DEV_SET = (6,)
# The frozen Description with its grasp Phrase edited, which e2e and backend tests recompile.
EDITED = FROZEN.text.replace(FROZEN.phrases[0], "grasps the object within two tries")
# The box e2e draws (a drag from 40% to 60% of each side of the 320x180 frame) and puts.
E2E_BOX = {"x1": 128, "y1": 72, "x2": 192, "y2": 108}


class ReplayThenRecord:
    """Serves what's recorded; makes the missing calls through `record`, uploading their clips."""

    def __init__(self, replay: ReplayTransport, record: Transport) -> None:
        self._replay = replay
        self._record = record
        self._clips: dict[str, Path] = {}  # replayed file id (the clip's name) -> clip
        self._uploaded: dict[str, str] = {}  # replayed file id -> real file id
        self.made: list[CostEntry] = []  # the calls made for real

    async def upload(self, path: Path) -> str:
        name = await self._replay.upload(path)
        self._clips[name] = path
        return name

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return await self._replay.count_tokens(model, content)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        try:
            return await self._replay.respond(model, content, options)
        except UnrecordedCallError:
            real = [await self._real_part(part) for part in content]
            started = time.monotonic()
            reply = await self._record.respond(model, real, options)
            latency = time.monotonic() - started
            usd = _price(model, reply.usage)
            self.made.append(CostEntry(model, "record_meta", usd, latency, dict(reply.usage)))
            return reply

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        try:
            return await self._replay.transcribe(model, audio, options)
        except UnrecordedCallError:
            started = time.monotonic()
            transcript = await self._record.transcribe(model, audio, options)
            latency = time.monotonic() - started
            audio_ms = wav_duration_ms(audio)
            usd = transcribe_cost(audio_ms)
            self.made.append(CostEntry(model, "record_meta", usd, latency, {"audio_ms": audio_ms}))
            return transcript

    async def _real_part(self, part: dict[str, object]) -> dict[str, object]:
        if "file_id" not in part:
            return part
        name = str(part["file_id"])
        if name not in self._uploaded:
            self._uploaded[name] = await self._record.upload(self._clips[name])
        return {**part, "file_id": self._uploaded[name]}


def _price(model: str, usage: dict[str, int]) -> float:
    """What `meta/` charges for a reply. The replayed calls around it are logged at their recorded
    price though they cost nothing, so the calls made for real are priced here instead."""
    if model == SAM:
        return sam_cost(usage.get("video_frames_processed", 0))
    tokens = (usage.get(k, 0) for k in ("input_tokens", "output_tokens", "cached_tokens"))
    return spark_cost(model, *tokens)


async def _run(ctx: AppContext, kind: str, items: list[WorkItem]) -> int:
    job_id = ctx.jobs.create(kind, items)
    await ctx.runner.run(job_id)
    job = ctx.jobs.get(job_id)
    assert job is not None
    for item in job.items:
        sys.stdout.write(f"{item.label} {item.step}: {item.status} {item.detail or ''}\n")
    return job.failed


async def _record(settings: Settings, transport: Transport) -> int:
    ctx = build_context(settings, transport, DEFAULT_LIMITS)  # records from the real API
    try:
        indices = list(range(E2E_EPISODES))
        failed = await _run(ctx, "ingest", ingest_items("droid_100", indices, with_meta=True))
        # Before boxing: e2e's Dev set Episode has no box.
        ctx.sets.add("dev", [episode_id("droid_100", i) for i in E2E_DEV_SET])
        draft = await compile_draft(ctx, FROZEN.text)
        sys.stdout.write(f"compile: {[(p.text, p.status) for p in draft.phrases]}\n")
        edited = await compile_draft(ctx, EDITED)  # recompiles the grasp Phrase only
        asked = [r.text for r in edited.recompiled or []]
        sys.stdout.write(f"recompile {asked}: {[c.id for c in edited.criteria]}\n")
        for camera in get_args(ExteriorCamera):
            ids = [episode_id("droid_100", i) for i in indices]
            for boxed in ids:
                ctx.boxes.save(boxed, BoxDraw(camera=camera, **E2E_BOX), (320, 180))
            failed += await _run(ctx, "box", [item for e in ids for item in box_items(e)])
        return failed
    finally:
        ctx.db.close()


def _transport(settings: Settings, missing_only: bool) -> RecordingTransport | ReplayThenRecord:
    key = settings.model_api_key
    if key is None:
        raise SystemExit("Set MODEL_API_KEY in .env to record")
    recording = RecordingTransport(
        OpenAITransport(settings.meta_base_url, key.get_secret_value()), RECORDINGS
    )
    if missing_only:
        return ReplayThenRecord(ReplayTransport(RECORDINGS), recording)
    RECORDINGS.unlink(missing_ok=True)
    return recording


def main(argv: list[str]) -> int:
    main_settings = get_settings()
    with tempfile.TemporaryDirectory() as tmp:
        root = write_fixture_source(Path(tmp) / "droid_100", episodes=E2E_EPISODES)
        settings = main_settings.model_copy(
            update={"data_dir": Path(tmp) / "data", "droid100_root": root, "meta_replay": None}
        )
        transport = _transport(settings, "--missing" in argv)
        failed = asyncio.run(_record(settings, transport))
        spent = settings.cost_log_path.read_text() if settings.cost_log_path.exists() else ""
        entries = [json.loads(line) for line in spent.splitlines() if line.strip()]
        if isinstance(transport, ReplayThenRecord):
            at = datetime.now(UTC).isoformat()
            entries = [{"at": at, **asdict(e)} for e in transport.made]
        main_settings.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
        with main_settings.cost_log_path.open("a") as log:
            log.writelines(json.dumps(e) + "\n" for e in entries)
        sys.stdout.write(f"spent ${sum(float(e['usd']) for e in entries):.4f}\n")
        shutil.rmtree(Path(tmp) / "data", ignore_errors=True)
    sys.stdout.write(f"recorded {len(RECORDINGS.read_text().splitlines())} replies\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
