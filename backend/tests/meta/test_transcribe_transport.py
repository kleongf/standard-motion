"""The real transport's batch transcribe request, against a mock of Meta's `/asr/transcribe`."""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from tests.meta.test_transcribe import write_wav
from winnow.meta.models import Transcript, Turn
from winnow.meta.openai_transport import OpenAITransport
from winnow.meta.pricing import VOICE_TRANSCRIBE
from winnow.meta.transport import TransientError, UnusableReplyError

OPTIONS: dict[str, object] = {"audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}


def transport_answering(
    status: int, body: dict[str, object] | bytes, seen: list[httpx2.Request]
) -> OpenAITransport:
    """Meta's `/asr/transcribe` answering `body`: JSON, or raw bytes as they came."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if isinstance(body, bytes):
            return httpx2.Response(status, content=body)
        return httpx2.Response(status, json=body)

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handle))
    return OpenAITransport("https://api.meta.test/v1", "secret", http=http)


def test_a_push_to_talk_turn_is_sent_as_multipart_and_its_transcript_is_one_turn(
    tmp_path: Path,
):
    seen: list[httpx2.Request] = []
    body: dict[str, object] = {
        "sessionId": "s1",
        "transcript": "It drops the marker here.",
        "audioDurationMs": 2500,
        "turns": [],  # always empty in PUSH_TO_TALK
    }
    transport = transport_answering(200, body, seen)
    audio = write_wav(tmp_path / "turn.wav", seconds=2.5)

    transcript = asyncio.run(transport.transcribe(VOICE_TRANSCRIBE, audio, OPTIONS))

    assert transcript == Transcript(
        turns=(Turn(text="It drops the marker here.", start_ms=0, end_ms=2500),)
    )
    (request,) = seen
    assert str(request.url) == "https://api.meta.test/v1/asr/transcribe"
    assert request.headers["authorization"] == "Bearer secret"
    assert request.headers["accept"] == "application/json"
    sent = request.read()
    settings = {"model": VOICE_TRANSCRIBE, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
    assert json.dumps(settings).encode() in sent
    assert audio.read_bytes() in sent


def test_reported_turns_keep_their_own_times(tmp_path: Path):
    body: dict[str, object] = {
        "sessionId": "s1",
        "transcript": "Grasps it. Drops it.",
        "audioDurationMs": 4000,
        "turns": [
            {"turnId": 1, "startMs": 200, "endMs": 1200, "transcript": "Grasps it."},
            {"turnId": 2, "startMs": 2000, "endMs": 3100, "transcript": "Drops it."},
        ],
    }
    transport = transport_answering(200, body, [])

    transcript = asyncio.run(
        transport.transcribe(VOICE_TRANSCRIBE, write_wav(tmp_path / "t.wav", 4.0), OPTIONS)
    )

    assert transcript.turns == (
        Turn(text="Grasps it.", start_ms=200, end_ms=1200),
        Turn(text="Drops it.", start_ms=2000, end_ms=3100),
    )


def test_a_rate_limit_is_transient(tmp_path: Path):
    transport = transport_answering(429, {"error": "slow down"}, [])

    with pytest.raises(TransientError):
        asyncio.run(
            transport.transcribe(VOICE_TRANSCRIBE, write_wav(tmp_path / "t.wav", 1.0), OPTIONS)
        )


@pytest.mark.parametrize(
    "body",
    [
        b"<html>Bad gateway</html>",  # not JSON
        b"[]",  # JSON, but not a TranscribeResponse
        {"sessionId": "s1", "transcript": "It drops it.", "turns": []},  # no audioDurationMs
        {"transcript": "Drops it.", "turns": [{"turnId": 1, "transcript": "Drops it."}]},
    ],
)
def test_a_reply_that_cannot_be_read_is_unusable(tmp_path: Path, body: dict[str, object] | bytes):
    transport = transport_answering(200, body, [])

    with pytest.raises(UnusableReplyError):
        asyncio.run(
            transport.transcribe(VOICE_TRANSCRIBE, write_wav(tmp_path / "t.wav", 1.0), OPTIONS)
        )
