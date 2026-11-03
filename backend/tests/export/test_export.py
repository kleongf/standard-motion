"""Exporting the kept Episodes as a LeRobot v3.0 dataset per source, with every rejection's
Reason beside it. The Test set is never exported."""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import cast

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from standard_motion.app import create_app
from standard_motion.baseline.prompts import FROZEN
from standard_motion.cli import main
from standard_motion.core.settings import Settings
from standard_motion.episodes.droid100 import CAMERAS
from standard_motion.episodes.droid101 import CAMERA_KEYS, FPS, Droid101
from standard_motion.episodes.droid101_files import LocalFiles
from standard_motion.episodes.fixtures import clip_path
from standard_motion.episodes.models import EpisodeSignals
from standard_motion.export.service import export_kept
from standard_motion.export.stats import QUANTILES
from standard_motion.labels.models import LabelDraw
from standard_motion.labels.service import save_label
from standard_motion.rubric.models import Rubric
from tests.helpers import app_context, decoded, reference_label, rgb, wait_for_job

DROID100 = [0, 1, 2, 4]  # 0 grasps cleanly, 1 releases high, 2 regrasps, 4 never closes
DROID101 = [0, 1, 2, 3]  # each grasps cleanly
TEST_SET = ["droid_1.0.1:1", "droid_100:0"]  # kept, but never exported
# Kept with no Reference label: exported all the same, by their Triage decisions.
UNLABELLED = ["droid_1.0.1:3", "droid_100:1"]
KEPT_101 = [0, 2, 3]  # the droid_1.0.1 Episodes exported, in order
NEVER_DROPS = FROZEN.phrases[1]


@pytest.fixture(scope="module")
def settings(
    tmp_path_factory: pytest.TempPathFactory, droid100_root: Path, droid101_root: Path
) -> Settings:
    return Settings(
        model_api_key=None,
        data_dir=tmp_path_factory.mktemp("export") / "data",
        droid100_root=droid100_root,
        droid101_root=droid101_root,
        ground_truth="reference_labels",
    )


@pytest.fixture(scope="module")
def api(settings: Settings) -> Iterator[TestClient]:
    """Both sources ingested and all but UNLABELLED Reference-labelled, scored on how the gripper
    grasps and releases: of droid_100, 0 and 1 are kept (1 by a reviewer's label: it releases
    high), 2 and 4 rejected; every droid_1.0.1 Episode is kept."""
    with TestClient(create_app(settings)) as client:
        for source, indices in (("droid_100", DROID100), ("droid_1.0.1", DROID101)):
            job = client.post("/api/episodes/ingest", json={"source": source, "indices": indices})
            wait_for_job(client, job.json()["job_id"])
            for index in indices:
                if f"{source}:{index}" not in UNLABELLED:
                    reference_label(client, f"{source}:{index}")
        ctx = app_context(client)
        ctx.sets.add("test", TEST_SET)
        seeded = ctx.rubrics.latest().rubric
        kept = [c for c in seeded.criteria if c.id in ("grasp-attempts", "release-height")]
        ctx.rubrics.add(Rubric.model_validate({**seeded.model_dump(), "criteria": kept}))
        draw = LabelDraw(phrase=NEVER_DROPS, value="pass", source="review")
        save_label(ctx, "droid_100:1", draw)
        yield client


@pytest.fixture(scope="module")
def exported(api: TestClient, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("exports") / "kept"
    export_kept(app_context(api), out)
    return out


def assert_same_signals(exported: EpisodeSignals, source: EpisodeSignals) -> None:
    assert exported.fps == source.fps
    assert exported.dataset_outcome == source.dataset_outcome
    for name in ("timestamps", "position", "gripper", "joint_positions"):
        np.testing.assert_array_equal(getattr(exported, name), getattr(source, name))
    assert exported.camera_extrinsics is not None and source.camera_extrinsics is not None
    for camera, extrinsics in source.camera_extrinsics.items():
        np.testing.assert_array_equal(exported.camera_extrinsics[camera], extrinsics)


def test_droid101_exports_only_kept_episodes_the_reader_loads_unchanged(
    exported: Path, droid101_root: Path, tmp_path: Path
):
    source = Droid101(LocalFiles(droid101_root))
    export = Droid101(LocalFiles(exported / "droid_1.0.1"))

    # 1 is in the Test set: kept 0, 2 and 3 become 0, 1 and 2.
    assert sorted(export.index) == [0, 1, 2]
    for new, old in enumerate(KEPT_101):
        ours, theirs = export.load(new), source.load(old)
        assert ours.signals.episode_index == new
        assert ours.instruction == theirs.instruction
        assert_same_signals(ours.signals, theirs.signals)
        assert export.meta(new).length == source.meta(old).length
        for camera in export.cameras:
            export.write_clip(new, camera, tmp_path / f"ours-{new}-{camera}.mp4")
            source.write_clip(old, camera, tmp_path / f"theirs-{new}-{camera}.mp4")
            frames = decoded(tmp_path / f"ours-{new}-{camera}.mp4")
            assert len(frames) == source.meta(old).length
            assert frames == decoded(tmp_path / f"theirs-{new}-{camera}.mp4")


def episode_rows(data: pa.Table, index: int) -> list[dict[str, object]]:
    rows = [i == index for i in data.column("episode_index").to_pylist()]
    return data.filter(pa.array(rows, type=pa.bool_())).to_pylist()


def test_kept_episodes_export_by_decision_without_a_reference_label_never_the_test_set(
    exported: Path, droid100_root: Path, droid101_root: Path
):
    # droid_100:1 and droid_1.0.1:3 are unlabelled; droid_100:0 and droid_1.0.1:1, Test set.
    for root, name, kept in (
        (droid100_root / "main", "droid_100", [1]),
        (droid101_root, "droid_1.0.1", KEPT_101),
    ):
        data = "data/chunk-000/file-000.parquet"
        source, ours = (pq.read_table(r / data) for r in (root, exported / name))  # pyright: ignore[reportUnknownMemberType]
        indices = {int(str(i)) for i in ours.column("episode_index").to_pylist()}
        assert sorted(indices) == list(range(len(kept)))
        for new, old in enumerate(kept):
            theirs = episode_rows(source, old)
            renumbered = episode_rows(ours, new)
            assert [r["timestamp"] for r in renumbered] == [r["timestamp"] for r in theirs]
            assert all(r["episode_index"] == new for r in renumbered)


def test_the_preview_counts_decisions_only_of_the_labelled_and_the_rest_apart(api: TestClient):
    preview = api.get("/api/export/preview").json()

    # droid_100:1 and droid_1.0.1:3 await a label; droid_100:0 and droid_1.0.1:1 are Test set.
    assert preview["sources"] == [
        {"source": "droid_1.0.1", "keep": 2, "needs_review": 0, "reject": 0,
         "awaiting_label": 1, "test_set": 1},
        {"source": "droid_100", "keep": 0, "needs_review": 0, "reject": 2,
         "awaiting_label": 1, "test_set": 1},
    ]  # fmt: skip
    assert (preview["include"], preview["exported"], preview["nothing_exported"]) == (
        "keep",
        2,
        None,
    )


def episodes_of(export: Path) -> list[dict[str, object]]:
    path = export / "meta" / "episodes" / "chunk-000" / "file-000.parquet"
    return pq.read_table(path).to_pylist()  # pyright: ignore[reportUnknownMemberType]


def test_every_exported_clip_holds_exactly_its_episodes_frames(
    exported: Path, droid100_root: Path, droid101_root: Path
):
    # droid_1.0.1 Episodes share a video per camera: each clip is its own stretch, no more.
    source = Droid101(LocalFiles(droid101_root))
    for row, old in zip(episodes_of(exported / "droid_1.0.1"), KEPT_101, strict=True):
        new, length = int(str(row["episode_index"])), source.meta(old).length
        for key in CAMERA_KEYS.values():
            video = f"videos/observation.images.{key}"
            assert row[f"{video}/from_timestamp"] == 0.0
            shared = decoded(droid101_root / video / "chunk-000" / "file-000.mp4")
            start = round(float(source.meta(old).row[f"{video}/from_timestamp"]) * FPS)
            clip = exported / "droid_1.0.1" / video / "chunk-000" / f"file-{new:03d}.mp4"
            assert decoded(clip) == shared[start : start + length]
    # droid_100's are copies of the Episode's own clip.
    [row] = episodes_of(exported / "droid_100")
    for camera in CAMERAS:
        clip = exported / "droid_100" / "videos" / f"observation.images.{camera}" / "chunk-000"
        assert decoded(clip / "file-000.mp4") == decoded(clip_path(droid100_root, 1, camera))
        assert len(decoded(clip / "file-000.mp4")) == row["length"]


def test_stats_json_holds_the_stats_of_the_exported_data_on_both_sources(exported: Path):
    for name in ("droid_100", "droid_1.0.1"):
        out = exported / name
        stats = json.loads((out / "meta" / "stats.json").read_text())
        data = pq.read_table(out / "data" / "chunk-000" / "file-000.parquet")  # pyright: ignore[reportUnknownMemberType]
        numeric = [c for c in data.column_names if c != "language_instruction"]

        assert set(numeric) <= set(stats), name
        for column in numeric:
            values = np.asarray(data.column(column).to_pylist()).reshape(data.num_rows, -1)
            ours = cast(dict[str, list[float]], stats[column])
            assert ours["min"] == values.min(axis=0).tolist(), column
            assert ours["max"] == values.max(axis=0).tolist(), column
            numbers = values.astype(np.float64)
            np.testing.assert_allclose(ours["mean"], numbers.mean(axis=0), atol=1e-6)
            np.testing.assert_allclose(ours["std"], numbers.std(axis=0), atol=1e-6)
            assert ours["count"] == [data.num_rows]
            low, middle, high = (np.asarray(ours[q]) for q in ("q01", "q50", "q99"))
            assert (low <= middle).all() and (middle <= high).all(), column


def test_stats_json_holds_every_cameras_pixel_stats_on_both_sources(exported: Path):
    # lerobot-train gives every camera ImageNet's mean and std by default, which fails on a
    # camera stats.json has nothing for; and normalizing by the data's own needs them anyway.
    for name in ("droid_100", "droid_1.0.1"):
        out = exported / name
        stats = json.loads((out / "meta" / "stats.json").read_text())
        info = json.loads((out / "meta" / "info.json").read_text())
        cameras = [key for key, f in info["features"].items() if f["dtype"] == "video"]

        assert len(cameras) == 3, name
        for camera in cameras:
            assert camera in stats, (name, camera)
            ours = {stat: np.asarray(value) for stat, value in stats[camera].items()}
            assert set(ours) == {"min", "max", "mean", "std", "count", *QUANTILES}
            assert all(v.shape == (3, 1, 1) for s, v in ours.items() if s != "count"), camera
            folder = out / "videos" / camera / "chunk-000"
            pixels = np.concatenate([rgb(clip) for clip in sorted(folder.glob("*.mp4"))]) / 255
            # Episodes under 100 frames have every frame sampled, at half size, as LeRobot does.
            assert ours["count"].tolist() == [info["total_frames"]]
            np.testing.assert_allclose(ours["mean"].ravel(), pixels.mean(axis=(0, 1, 2)), atol=0.01)
            np.testing.assert_allclose(ours["std"].ravel(), pixels.std(axis=(0, 1, 2)), atol=0.01)
            assert (ours["min"] >= 0).all() and (ours["max"] <= 1).all(), camera
            assert (ours["q01"] <= ours["q50"]).all() and (ours["q50"] <= ours["q99"]).all()


def test_droid100_exports_every_column_of_its_kept_episode_renumbered(
    exported: Path, droid100_root: Path
):
    source = pq.read_table(droid100_root / "main" / "data" / "chunk-000" / "file-000.parquet")  # pyright: ignore[reportUnknownMemberType]
    out = exported / "droid_100"
    data = pq.read_table(out / "data" / "chunk-000" / "file-000.parquet")  # pyright: ignore[reportUnknownMemberType]

    # 1 is the one kept (0 is in the Test set): it becomes Episode 0, and its task, task 0.
    assert data.schema == source.schema
    one = [i == 1 for i in source.column("episode_index").to_pylist()]
    theirs = source.filter(pa.array(one, type=pa.bool_())).to_pylist()
    ours = data.to_pylist()
    assert len(ours) == 45
    assert ours == [{**row, "episode_index": 0, "task_index": 0} for row in theirs]
    task = "Move the black remote control to the left"
    tasks = pq.read_table(out / "meta" / "tasks.parquet").to_pylist()  # pyright: ignore[reportUnknownMemberType]
    assert tasks == [{"task_index": 0, "__index_level_0__": task}]
    for camera in CAMERAS:
        clip = out / "videos" / f"observation.images.{camera}" / "chunk-000" / "file-000.mp4"
        assert clip.read_bytes() == clip_path(droid100_root, 1, camera).read_bytes()
    episodes = pq.read_table(out / "meta" / "episodes" / "chunk-000" / "file-000.parquet")  # pyright: ignore[reportUnknownMemberType]
    [row] = episodes.to_pylist()
    assert (row["episode_index"], row["length"], row["tasks"]) == (0, 45, [task])
    assert row["videos/observation.images.wrist_image_left/from_timestamp"] == 0.0
    info = json.loads((out / "meta" / "info.json").read_text())
    assert (info["codebase_version"], info["fps"]) == ("v3.0", 15.0)
    assert (info["total_episodes"], info["total_frames"], info["total_tasks"]) == (1, 45, 1)
    assert info["splits"] == {"train": "0:1"}
    assert set(info["features"]) == {
        *source.column_names,
        *(f"observation.images.{c}" for c in CAMERAS),
    }
    assert info["features"]["observation.state"]["shape"] == [7]
    wrist = info["features"]["observation.images.wrist_image_left"]
    assert (wrist["dtype"], wrist["shape"]) == ("video", [180, 320, 3])


def test_every_episode_not_kept_is_listed_with_its_reason(exported: Path):
    lines = (exported / "rejections.jsonl").read_text().splitlines()

    first_try = FROZEN.phrases[0]
    assert [json.loads(line) for line in lines] == [
        {
            "episode_id": "droid_100:2",
            "source_index": 2,
            "decision": "reject",
            "reason": f'Rejected: "{first_try}" failed. 2 failed grasp attempts, at 0.9 s and '
            "1.3 s, before the grasp at 1.8 s.",
        },
        {
            "episode_id": "droid_100:4",
            "source_index": 4,
            "decision": "reject",
            "reason": f'Rejected: "{first_try}" failed. No grasp: the gripper never closed.',
        },
    ]


def test_the_manifest_maps_each_exported_episode_to_its_source_and_the_counts_add_up(
    exported: Path, api: TestClient
):
    manifest = json.loads((exported / "manifest.json").read_text())

    kept = [("droid_1.0.1", new, old) for new, old in enumerate(KEPT_101)] + [("droid_100", 0, 1)]
    assert manifest["include"] == "keep"
    assert manifest["exported"] == [
        {
            "exported_episode_index": new,
            "source": source,
            "source_episode_index": old,
            "episode_id": f"{source}:{old}",
            "decision": "keep",
        }
        for source, new, old in kept
    ]
    assert manifest["skipped"] == {"reject": 2, "needs_review": 0, "test_set": 2}
    ctx = app_context(api)
    total = len(manifest["exported"]) + sum(manifest["skipped"].values())
    assert total == len(ctx.episodes.list())
    rejections = (exported / "rejections.jsonl").read_text().splitlines()
    assert len(rejections) == manifest["skipped"]["reject"] + manifest["skipped"]["needs_review"]
    for source in ("droid_1.0.1", "droid_100"):
        info = json.loads((exported / source / "meta" / "info.json").read_text())
        assert info["total_episodes"] == sum(k["source"] == source for k in manifest["exported"])
    assert manifest["rubric_version"] == ctx.rubrics.latest().version
    assert manifest["margin_multiplier"] == 1.0
    assert manifest["not_reference_labelled"] == 2
    assert datetime.fromisoformat(manifest["created_at"]).tzinfo is not None


def test_cli_exports_to_the_folder_given_and_never_over_another_export(
    api: TestClient, settings: Settings, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    out = tmp_path / "kept"

    assert main(["export", str(out)], settings=settings) == 0
    written = (
        f"4 kept Episodes, and the Reasons for 2 not kept (2 of the 6 not Reference-labelled "
        f"yet), to {out}"
    )
    assert written in capsys.readouterr().out
    names = sorted(p.name for p in out.iterdir())
    assert names == ["droid_1.0.1", "droid_100", "manifest.json", "rejections.jsonl"]
    assert main(["export", str(out)], settings=settings) == 1
    assert "already exists" in capsys.readouterr().out


def test_the_api_exports_in_the_background_an_item_per_episode_to_a_new_folder(
    api: TestClient, settings: Settings
):
    started = api.post("/api/export", json={})

    assert started.status_code == 202
    job = wait_for_job(api, started.json()["job_id"])
    items = cast(list[dict[str, object]], job["items"])
    assert [item["label"] for item in items] == [
        *(f"droid_1.0.1:{i}" for i in KEPT_101),
        "droid_100:1",
        "Tables and manifest",
    ]
    assert all(item["status"] == "done" for item in items), items
    out = Path(str(items[-1]["detail"]).rsplit(" to ", 1)[1])
    assert out.parent == settings.data_dir / "exports"
    assert (out / "droid_1.0.1" / "meta" / "info.json").exists()
    assert not out.with_name(f"{out.name}.partial").exists()
    assert api.get("/api/jobs/latest", params={"kind": "export"}).json()["id"] == job["id"]
