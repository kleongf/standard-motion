"""Write the scripted Meta replies for e2e's voice turn: `uv run python -m tests.record_voice`.
Free: no call reaches the Meta API.

e2e's voice spec holds V over Chromium's fake microphone, which plays FIXTURE_WAV. What the
browser captures differs every run, so replay answers any audio with the one transcript recorded
here (winnow.meta.replay ANY_AUDIO), and Spark's mapping of it onto the spec's Episode's unsure
Phrases is scripted (SAID, MARKS). This replays RECORDINGS to ingest that Episode, gives it a
Reference label as e2e does, then runs the real voice service once, keeping the replies RECORDINGS
doesn't have. Rerun after changing the voice prompt or schema, or what makes that Episode unsure;
e2e then fails with UnrecordedCallError until you do.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from tests.record_meta import E2E_EPISODES, RECORDINGS
from winnow.baseline.prompts import FROZEN
from winnow.core.context import AppContext, build_context
from winnow.core.settings import get_settings
from winnow.episodes.fixtures import write_fixture_source
from winnow.episodes.service import ingest_items
from winnow.episodes.store import episode_id
from winnow.meta.models import MetaContent, Transcript, Turn
from winnow.meta.replay import RecordingTransport, ReplayTransport
from winnow.meta.transport import Reply
from winnow.reference_labels.models import PhraseLabel, ReferenceLabelDraw
from winnow.reference_labels.service import save_label
from winnow.voice.service import transcribe_turn

VOICE_ANSWERS = Path(__file__).parent / "recordings" / "voice_answers.jsonl"
FIXTURE_WAV = Path(__file__).parents[2] / "e2e" / "fixtures" / "voice-turn.wav"
VOICE_EPISODE = 19  # the voice spec's (EPISODES.voice in e2e/helpers.ts)
WRITTEN_INSTRUCTION = "Put the block in the bowl"  # what e2e's referenceLabel writes
_, NEVER_DROPS, _, _ = FROZEN.phrases
SAID = "It drops the marker right here, before the pot."  # what FIXTURE_WAV says
MARKS = [{"phrase": NEVER_DROPS, "value": "fail", "quote": "It drops the marker right here"}]
USAGE = {"input_tokens": 600, "output_tokens": 80}


class ScriptedTurn:
    """Replays RECORDINGS; hears SAID, and maps it as MARKS."""

    def __init__(self, replay: ReplayTransport) -> None:
        self._replay = replay

    async def upload(self, path: Path) -> str:
        return await self._replay.upload(path)

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return 0

    async def transcribe(self, model: str, audio: Path, options: dict[str, object]) -> Transcript:
        return Transcript(turns=(Turn(text=SAID, start_ms=0, end_ms=2300),))

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        text_format = options.get("text")
        if not isinstance(text_format, dict) or text_format["format"]["name"] != "voice":
            return await self._replay.respond(model, content, options)
        return Reply(json.dumps({"phrases": MARKS}), USAGE)


async def _record(ctx: AppContext) -> None:
    job_id = ctx.jobs.create("ingest", ingest_items("droid_100", [VOICE_EPISODE], with_meta=True))
    await ctx.runner.run(job_id)
    episode = ctx.episodes.get(episode_id("droid_100", VOICE_EPISODE))
    assert episode is not None
    phrases = [PhraseLabel(phrase=p, passed=True) for p in FROZEN.phrases]
    draw = ReferenceLabelDraw(phrases=phrases, instruction=WRITTEN_INSTRUCTION, elapsed_s=10)
    save_label(ctx, episode, draw)
    turn = await transcribe_turn(ctx, episode, FIXTURE_WAV, t=0.0)
    sys.stdout.write(f"{turn.transcript!r}: {[(c.phrase, c.value) for c in turn.chips]}\n")


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
        transport = RecordingTransport(ScriptedTurn(ReplayTransport(RECORDINGS)), everything)
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
    VOICE_ANSWERS.write_text("".join(line + "\n" for line in lines))
    sys.stdout.write(f"wrote {len(lines)} scripted voice replies to {VOICE_ANSWERS.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
