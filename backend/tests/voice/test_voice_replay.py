"""e2e's voice turn under the replay transport, from the replies `tests.record_voice` wrote, with
the real `meta/` code underneath: any audio is heard as the scripted transcript."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import reference_label, wait_for_job
from tests.meta.test_transcribe import write_wav
from tests.record_meta import RECORDINGS
from tests.record_voice import MARKS, SAID, VOICE_ANSWERS, VOICE_EPISODE
from winnow.app import create_app
from winnow.core.settings import Settings
from winnow.meta.replay import ReplayTransport


@pytest.fixture(scope="module")
def droid100_root(e2e_droid100_root: Path) -> Path:
    """e2e's fixture source, which the voice replies were recorded against."""
    return e2e_droid100_root


@pytest.fixture
def replay_api(settings: Settings, tmp_path: Path) -> Iterator[TestClient]:
    replies = tmp_path / "replies.jsonl"
    replies.write_text(RECORDINGS.read_text() + VOICE_ANSWERS.read_text())
    with TestClient(create_app(settings, transport=ReplayTransport(replies))) as client:
        body = {"source": "droid_100", "indices": [VOICE_EPISODE]}
        wait_for_job(client, client.post("/api/episodes/ingest", json=body).json()["job_id"])
        reference_label(client, f"droid_100:{VOICE_EPISODE}")
        yield client


def test_any_captured_turn_replays_as_the_scripted_transcript_and_chips(
    replay_api: TestClient, tmp_path: Path
):
    with write_wav(tmp_path / "live.wav", seconds=1.7, tone=9).open("rb") as wav:
        turn = replay_api.post(
            f"/api/episodes/droid_100:{VOICE_EPISODE}/voice",
            files={"audio": ("turn.wav", wav, "audio/wav")},
            data={"t": "0.8"},
        )

    assert turn.status_code == 200, turn.text
    assert turn.json() == {"transcript": SAID, "t": 0.8, "chips": MARKS}
