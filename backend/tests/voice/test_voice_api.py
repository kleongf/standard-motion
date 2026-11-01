"""A push-to-talk turn on the Review page: transcribed, then mapped by one Spark call onto the
Episode's unsure hard Phrases as pass or fail. Nothing is saved: the reviewer confirms each."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.helpers import ask_visual, reference_label, track_cleanly, wait_for_job
from tests.meta.test_transcribe import write_wav
from tests.voice.scripted import ScriptedVoice
from winnow.app import create_app
from winnow.baseline.prompts import FROZEN
from winnow.core.settings import Settings

GRASPS, NEVER_DROPS, PLACES, _ = FROZEN.phrases
UNSURE = "droid_100:1"  # unsure only on "never drops it": its release height is near threshold


@pytest.fixture
def voice() -> ScriptedVoice:
    return ScriptedVoice()


@pytest.fixture
def voice_api(settings: Settings, voice: ScriptedVoice) -> Iterator[TestClient]:
    with TestClient(create_app(settings, transport=voice)) as api:
        job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1]})
        wait_for_job(api, job.json()["job_id"])
        ask_visual(api)
        track_cleanly(api, UNSURE)  # tracked Criteria pass; release height is left unsure
        reference_label(api, UNSURE)
        yield api


def speak(api: TestClient, episode_id: str, audio: Path, t: float = 1.5):
    with audio.open("rb") as wav:
        return api.post(
            f"/api/episodes/{episode_id}/voice",
            files={"audio": ("turn.wav", wav, "audio/wav")},
            data={"t": str(t)},
        )


def test_a_turn_is_mapped_onto_only_the_unsure_hard_phrases(
    voice_api: TestClient, voice: ScriptedVoice, tmp_path: Path
):
    voice.marks = [
        {"phrase": NEVER_DROPS, "value": "fail", "quote": "It drops the marker right here"},
        {"phrase": GRASPS, "value": "pass", "quote": "the marker"},  # already decided: dropped
        {"phrase": "lifts it gently", "value": "pass", "quote": "marker"},  # not a Phrase
    ]

    turn = speak(voice_api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=2.3), t=1.5)

    assert turn.status_code == 200, turn.text
    assert turn.json() == {
        "transcript": "It drops the marker right here, before the pot.",
        "t": 1.5,
        "chips": [
            {"phrase": NEVER_DROPS, "value": "fail", "quote": "It drops the marker right here"}
        ],
    }
    (prompt,) = voice.asked
    assert voice.said in prompt
    assert NEVER_DROPS in prompt
    assert GRASPS not in prompt and PLACES not in prompt


def test_a_turn_saves_no_label(voice_api: TestClient, voice: ScriptedVoice, tmp_path: Path):
    voice.marks = [{"phrase": NEVER_DROPS, "value": "fail", "quote": "drops"}]

    speak(voice_api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=1.0))

    assert voice_api.get("/api/episodes/droid_100:1/labels").json() == []


def test_the_turn_is_transcribed_and_cost_logged(
    voice_api: TestClient, voice: ScriptedVoice, settings: Settings, tmp_path: Path
):
    speak(voice_api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=2.0))
    speak(voice_api, UNSURE, write_wav(tmp_path / "again.wav", seconds=2.0))  # same audio

    assert len(voice.transcribed) == 1  # the second is a cache hit
    logged = settings.cost_log_path.read_text()
    assert logged.count('"purpose": "voice:droid_100:1"') == 4  # transcribe and Spark, twice


def test_an_unusable_answer_is_a_502(voice_api: TestClient, voice: ScriptedVoice, tmp_path: Path):
    voice.answer = "not json"

    turn = speak(voice_api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=1.0))

    assert turn.status_code == 502


@pytest.mark.parametrize(
    "reply",
    [
        b"<html>Bad gateway</html>",  # not JSON
        {"sessionId": "s1", "transcript": "It drops it.", "turns": []},  # no audioDurationMs
    ],
)
def test_an_unusable_transcribe_reply_is_a_502(
    voice_api: TestClient, voice: ScriptedVoice, tmp_path: Path, reply: dict[str, object] | bytes
):
    voice.reply = reply

    turn = speak(voice_api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=1.0))

    assert turn.status_code == 502, turn.text
    assert "Voice Transcribe" in turn.json()["detail"]


def test_a_phrase_named_in_another_case_or_quoted_still_maps(
    voice_api: TestClient, voice: ScriptedVoice, tmp_path: Path
):
    voice.marks = [{"phrase": "“Never Drops It”", "value": "fail", "quote": "drops"}]

    turn = speak(voice_api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=1.0))

    assert turn.json()["chips"] == [{"phrase": NEVER_DROPS, "value": "fail", "quote": "drops"}]


def test_audio_that_is_not_16_khz_mono_wav_is_a_422(voice_api: TestClient, tmp_path: Path):
    junk = tmp_path / "turn.wav"
    junk.write_bytes(b"not a wav")

    assert speak(voice_api, UNSURE, junk).status_code == 422


def test_an_episode_without_a_reference_label_is_hidden(voice_api: TestClient, tmp_path: Path):
    turn = speak(voice_api, "droid_100:0", write_wav(tmp_path / "turn.wav", seconds=1.0))

    assert turn.status_code == 403


def test_without_the_meta_api_a_turn_is_a_503(api: TestClient, tmp_path: Path):
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [1]})
    wait_for_job(api, job.json()["job_id"])
    reference_label(api, UNSURE)

    turn = speak(api, UNSURE, write_wav(tmp_path / "turn.wav", seconds=1.0))

    assert turn.status_code == 503
