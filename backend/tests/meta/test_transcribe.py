"""Muse Voice Transcribe through the Meta client: cached by the audio's content, priced by its
length, logged like every other call."""

import asyncio
import json
import wave
from pathlib import Path

import pytest

from tests.meta.fakes import FakeTransport, MakeClient
from winnow.meta.models import TranscribeRequest, Transcript, Turn
from winnow.meta.pricing import VOICE_TRANSCRIBE
from winnow.meta.replay import RecordingTransport, ReplayTransport

SAID = Transcript(turns=(Turn(text="It drops the marker here.", start_ms=0, end_ms=3000),))


def write_wav(path: Path, seconds: float, tone: int = 1) -> Path:
    """Mono 16-bit PCM at 16 kHz, as the browser sends it."""
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16_000)
        out.writeframes(tone.to_bytes(2, "little", signed=True) * int(seconds * 16_000))
    return path


def test_a_turn_is_transcribed_once_and_its_audio_length_is_priced_and_logged(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    transport.transcript = SAID
    client = make_client()
    audio = write_wav(tmp_path / "turn.wav", seconds=3.0)
    request = TranscribeRequest(audio, purpose="voice:droid_100:1")

    first = asyncio.run(client.transcribe(request))
    second = asyncio.run(client.transcribe(request))

    assert transport.transcribed == [audio]
    assert first.transcript == SAID
    assert (first.cached, second.cached) == (False, True)
    assert second.transcript == SAID
    assert first.usd == pytest.approx(0.18 * 3 / 3600)  # $0.18 per audio hour
    entries = client.costs.entries()
    assert [(e.model, e.purpose, e.usd) for e in entries] == [
        (VOICE_TRANSCRIBE, "voice:droid_100:1", first.usd),
        (VOICE_TRANSCRIBE, "voice:droid_100:1", 0.0),
    ]
    assert entries[0].detail["audio_ms"] == 3000


def test_different_audio_is_a_new_turn(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    client = make_client()
    one = write_wav(tmp_path / "one.wav", seconds=1.0, tone=1)
    two = write_wav(tmp_path / "two.wav", seconds=1.0, tone=2)

    asyncio.run(client.transcribe(TranscribeRequest(one, purpose="voice")))
    again = asyncio.run(client.transcribe(TranscribeRequest(two, purpose="voice")))

    assert not again.cached
    assert transport.transcribed == [one, two]


def test_audio_that_is_not_16_khz_mono_wav_is_refused_before_any_call(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    client = make_client()
    stereo = tmp_path / "stereo.wav"
    with wave.open(str(stereo), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(16_000)
        out.writeframes(b"\0\0\0\0" * 1600)

    with pytest.raises(ValueError, match="mono"):
        asyncio.run(client.transcribe(TranscribeRequest(stereo, purpose="voice")))
    assert transport.transcribed == []


def test_a_recorded_transcript_replays_for_any_audio(transport: FakeTransport, tmp_path: Path):
    # The browser captures each turn live, so no two turns' bytes match: replay keys a turn by
    # model and options alone.
    transport.transcript = SAID
    recordings = tmp_path / "replies.jsonl"
    options: dict[str, object] = {"audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
    recorder = RecordingTransport(transport, recordings)
    recorded = write_wav(tmp_path / "recorded.wav", seconds=1.0, tone=1)
    asyncio.run(recorder.transcribe(VOICE_TRANSCRIBE, recorded, options))

    replay = ReplayTransport(recordings)
    other = write_wav(tmp_path / "other.wav", seconds=2.0, tone=5)
    replayed = asyncio.run(replay.transcribe(VOICE_TRANSCRIBE, other, options))

    assert replayed == SAID
    assert json.loads(recordings.read_text())["model"] == VOICE_TRANSCRIBE
