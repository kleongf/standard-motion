"""Voice Transcribe's audio and transcripts: what it accepts, and how a transcript is kept."""

import json
import wave
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field, ValidationError

from winnow.meta.models import Transcript, Turn
from winnow.meta.transport import UnusableReplyError

SAMPLE_RATES = (16_000, 24_000)
MAX_AUDIO_MS = 10 * 60 * 1000  # the batch endpoint's limit


def wav_duration_ms(path: Path) -> int:
    """The clip's length; raises ValueError unless it is mono 16-bit PCM WAV at 16 or 24 kHz,
    at most 10 minutes long, which is all the batch endpoint takes."""
    try:
        with wave.open(str(path), "rb") as clip:
            channels, width, rate = clip.getnchannels(), clip.getsampwidth(), clip.getframerate()
            frames = clip.getnframes()
    except (wave.Error, EOFError) as error:
        raise ValueError(f"Not a WAV file: {error}") from error
    if channels != 1 or width != 2 or rate not in SAMPLE_RATES:
        raise ValueError(
            f"Audio must be mono 16-bit PCM at 16 or 24 kHz, not {channels} channel(s), "
            f"{width * 8}-bit at {rate} Hz"
        )
    ms = frames * 1000 // rate
    if ms > MAX_AUDIO_MS:
        raise ValueError(f"Audio is {ms / 1000:.0f} s long; at most 10 minutes is transcribed")
    return ms


def transcript_json(transcript: Transcript) -> str:
    turns = [{"text": t.text, "start_ms": t.start_ms, "end_ms": t.end_ms} for t in transcript.turns]
    return json.dumps({"turns": turns})


def parse_transcript(text: str) -> Transcript:
    rows = cast(list[dict[str, object]], json.loads(text)["turns"])
    return Transcript(
        turns=tuple(
            Turn(text=str(r["text"]), start_ms=_int(r["start_ms"]), end_ms=_int(r["end_ms"]))
            for r in rows
        )
    )


class _MetaTurn(BaseModel):
    transcript: str
    start_ms: int = Field(alias="startMs")
    end_ms: int = Field(alias="endMs")


class _TranscribeResponse(BaseModel):
    transcript: str = ""
    audio_duration_ms: int | None = Field(default=None, alias="audioDurationMs")
    turns: list[_MetaTurn] | None = None


def transcript_from_response(body: bytes) -> Transcript:
    """Meta's TranscribeResponse. Its `turns` is empty in PUSH_TO_TALK, where the whole clip is
    one turn: its `transcript`, over the audio's duration. Raises UnusableReplyError for a body
    that isn't one."""
    try:
        reply = _TranscribeResponse.model_validate_json(body)
    except ValidationError as error:
        raise UnusableReplyError(f"Voice Transcribe's reply couldn't be read: {error}") from error
    if reply.turns:
        return Transcript(
            turns=tuple(
                Turn(text=t.transcript, start_ms=t.start_ms, end_ms=t.end_ms) for t in reply.turns
            )
        )
    text = reply.transcript.strip()
    if not text:
        return Transcript(turns=())
    if reply.audio_duration_ms is None:
        raise UnusableReplyError("Voice Transcribe's reply couldn't be read: no audioDurationMs")
    return Transcript(turns=(Turn(text=text, start_ms=0, end_ms=reply.audio_duration_ms),))


def _int(value: object) -> int:
    return int(cast(int | float | str, value))
