from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from standard_motion.app import create_app
from standard_motion.core.settings import Settings, get_settings


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_health_reports_missing_key():
    response = client_with(Settings(model_api_key=None)).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "meta_api_key_configured": False,
        "meta_available": False,
    }


def test_health_reports_configured_key():
    response = client_with(Settings(model_api_key=SecretStr("test"))).get("/api/health")

    assert response.json()["meta_api_key_configured"] is True
    assert response.json()["meta_available"] is True


def test_a_replay_of_the_meta_api_makes_it_available_without_a_key(tmp_path: Path):
    settings = Settings(model_api_key=None, meta_replay=tmp_path / "replay.jsonl")

    response = client_with(settings).get("/api/health")

    assert response.json()["meta_api_key_configured"] is False
    assert response.json()["meta_available"] is True
