"""Choosing what an export includes (the Keeps only, or the Needs review Episodes with them),
previewing it, the exports written so far, and a failed export leaving nothing behind."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from standard_motion.app import create_app
from standard_motion.core.settings import Settings
from standard_motion.export.droid100 import Droid100Export
from standard_motion.rubric.models import Rubric
from tests.helpers import app_context, reference_label, wait_for_job

# 0 grasps cleanly: Keep. 1 releases high, within the margin: Needs review. 2 regrasps and 4
# never closes: Reject. 2 has no Reference label; 4 is in the Test set.
UNLABELLED, TEST_SET = "droid_100:2", "droid_100:4"


@pytest.fixture(scope="module")
def settings(tmp_path_factory: pytest.TempPathFactory, droid100_root: Path) -> Settings:
    data_dir = tmp_path_factory.mktemp("export-include") / "data"
    return Settings(
        model_api_key=None,
        data_dir=data_dir,
        droid100_root=droid100_root,
        ground_truth="reference_labels",
    )


@pytest.fixture(scope="module")
def api(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        job = client.post(
            "/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2, 4]}
        )
        wait_for_job(client, job.json()["job_id"])
        for index in (0, 1, 4):
            reference_label(client, f"droid_100:{index}")
        ctx = app_context(client)
        ctx.sets.add("test", [TEST_SET])
        seeded = ctx.rubrics.latest().rubric
        kept = [c for c in seeded.criteria if c.id in ("grasp-attempts", "release-height")]
        ctx.rubrics.add(Rubric.model_validate({**seeded.model_dump(), "criteria": kept}))
        yield client


def export(api: TestClient, include: str) -> tuple[dict[str, object], Path | None]:
    started = api.post("/api/export", json={"include": include})
    assert started.status_code == 202, started.text
    job = wait_for_job(api, started.json()["job_id"])
    items = cast(list[dict[str, object]], job["items"])
    if job["failed"]:
        return job, None
    return job, Path(str(items[-1]["detail"]).rsplit(" to ", 1)[1])


def test_the_preview_counts_by_decision_and_source_and_what_each_choice_exports(api: TestClient):
    keep = api.get("/api/export/preview").json()
    both = api.get("/api/export/preview", params={"include": "keep_and_review"}).json()

    assert keep["sources"] == [
        {"source": "droid_100", "keep": 1, "needs_review": 1, "reject": 0,
         "awaiting_label": 1, "test_set": 1},
    ]  # fmt: skip
    assert (keep["exported"], both["exported"]) == (1, 2)
    assert keep["nothing_exported"] is None and both["nothing_exported"] is None


def test_keep_and_review_exports_the_needs_review_episodes_too_and_the_manifest_says_so(
    api: TestClient,
):
    job, out = export(api, "keep_and_review")

    assert out is not None, job
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["include"] == "keep_and_review"
    assert [(e["episode_id"], e["exported_episode_index"], e["decision"])
            for e in manifest["exported"]] == [
        ("droid_100:0", 0, "keep"),
        ("droid_100:1", 1, "needs_review"),
    ]  # fmt: skip
    assert manifest["skipped"] == {"reject": 1, "needs_review": 0, "test_set": 1}
    rejections = [json.loads(line) for line in (out / "rejections.jsonl").read_text().splitlines()]
    assert [r["episode_id"] for r in rejections] == [UNLABELLED]
    info = json.loads((out / "droid_100" / "meta" / "info.json").read_text())
    assert info["total_episodes"] == 2
    labels = [item["label"] for item in cast(list[dict[str, object]], job["items"])]
    assert labels == ["droid_100:0", "droid_100:1", "Tables and manifest"]


def test_keep_only_leaves_the_needs_review_episodes_out_with_their_reasons(api: TestClient):
    _, out = export(api, "keep")

    assert out is not None
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["include"] == "keep"
    assert [e["episode_id"] for e in manifest["exported"]] == ["droid_100:0"]
    assert manifest["skipped"] == {"reject": 1, "needs_review": 1, "test_set": 1}
    rejections = [json.loads(line) for line in (out / "rejections.jsonl").read_text().splitlines()]
    assert [(r["episode_id"], r["decision"]) for r in rejections] == [
        ("droid_100:1", "needs_review"),
        (UNLABELLED, "reject"),
    ]


def test_past_exports_list_each_finished_export_newest_first(api: TestClient):
    _, first = export(api, "keep_and_review")
    _, second = export(api, "keep")

    past = api.get("/api/export/past").json()
    assert [p["path"] for p in past[:2]] == [str(second), str(first)]
    assert [(p["episodes"], p["include"]) for p in past[:2]] == [
        (1, "keep"),
        (2, "keep_and_review"),
    ]
    assert all(p["created_at"] for p in past)


def test_a_failed_export_removes_its_folders_and_skips_the_episodes_after(
    api: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    exports = settings.data_dir / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    before = sorted(exports.iterdir())

    def broken(*_: object) -> float:
        raise RuntimeError("the disk is full")

    monkeypatch.setattr(Droid100Export, "write_video", broken)
    job, out = export(api, "keep_and_review")

    assert out is None
    statuses = [(i["status"], i["detail"]) for i in cast(list[dict[str, str]], job["items"])]
    assert statuses == [
        ("failed", "the disk is full"),
        ("failed", "skipped: droid_100:0 failed"),
        ("failed", "skipped: droid_100:1 failed"),
    ]
    assert sorted(exports.iterdir()) == before
