from fastapi.testclient import TestClient

from tests.helpers import wait_for_job

EXTERIOR_2 = "exterior_image_2_left"
BOX = {"camera": EXTERIOR_2, "x1": 100, "y1": 60, "x2": 140, "y2": 90}


def save_box(api: TestClient, episode_id: str, **changes: object) -> dict[str, object]:
    """Save a box and wait for the work it queues."""
    assert api.put(f"/api/episodes/{episode_id}/box", json=BOX | changes).status_code == 200
    job = api.get("/api/jobs/latest", params={"kind": "box"}).json()
    return wait_for_job(api, job["id"])
