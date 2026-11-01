"""The `ingest` step: one Episode from its source into the Dataset."""

import asyncio
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from winnow.episodes.clips import first_frame, to_sam_fps
from winnow.episodes.models import Episode, EpisodeSignals, Signals, SourceEpisode
from winnow.episodes.sources import Source
from winnow.episodes.speed import smoothed_speed
from winnow.episodes.store import (
    EpisodeStore,
    clip_path,
    episode_id,
    frame0_path,
    sam_clip_path,
    save_signals,
)
from winnow.jobs.models import Step, WorkItem


def _write_files(source: Source, index: int, folder: Path) -> SourceEpisode:
    """Blocking work (parquet, ffmpeg), run off the event loop."""
    episode = source.load(index)
    save_signals(folder, episode.signals)
    for camera in source.cameras:
        h264 = clip_path(folder, camera)
        source.write_clip(index, camera, h264)
        to_sam_fps(h264, sam_clip_path(folder, camera))
    return episode


async def ingest(
    store: EpisodeStore, source: Source, index: int, task: tuple[str | None, str | None] | None
) -> str | None:
    """Idempotent: an Episode whose row and files already exist is left alone, except that a
    given task (object, target) is recorded."""
    note = "already ingested"
    if not store.is_ingested(source.name, index, source.cameras):
        folder = store.folder(source.name, index)
        episode = await asyncio.to_thread(_write_files, source, index, folder)
        store.save(source.name, index, episode)  # last, so a row always means complete files
        note = None
    if task is not None:
        store.set_task(episode_id(source.name, index), *task)
    return note


def ingest_step(store: EpisodeStore, sources: Mapping[str, Source]) -> Step:
    # Two jobs may ask for the same Episode at once: the second waits, then finds it ingested.
    locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def step(args: Mapping[str, object]) -> str | None:
        source = sources[str(args["source"])]
        index = int(str(args["index"]))
        task = (_text(args.get("object")), _text(args.get("target"))) if "object" in args else None
        async with locks[episode_id(source.name, index)]:
            return await ingest(store, source, index, task)

    return step


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def ingest_items(
    source: str,
    indices: list[int],
    with_meta: bool,
    tasks: Mapping[int, tuple[str | None, str | None]] | None = None,
) -> list[WorkItem]:
    """Per Episode (each once, in the order given): ingest it, with its (object, target) when
    known, then, once that has succeeded and if Meta is configured, run the Spark-alone baseline
    and track the wrist view."""
    items: list[WorkItem] = []
    for i in dict.fromkeys(indices):
        label = episode_id(source, i)
        args: dict[str, object] = {"source": source, "index": i}
        if tasks is not None and i in tasks:
            args["object"], args["target"] = tasks[i]
        items.append(WorkItem("ingest", args, label))
        if with_meta:
            ingested = len(items) - 1
            items.append(WorkItem("baseline", {"episode_id": label}, label, after=ingested))
            items.append(WorkItem("track_wrist", {"episode_id": label}, label, after=ingested))
    return items


def workstation_signals(signals: EpisodeSignals) -> Signals:
    t = signals.timestamps - signals.timestamps[0]
    return Signals(
        t=_rounded(t),
        gripper=_rounded(signals.gripper),
        z=_rounded(signals.position[:, 2]),
        speed=_rounded(smoothed_speed(signals)),
    )


def _rounded(values: np.ndarray) -> list[float]:
    return [round(float(v), 4) for v in values]


async def frame_zero(store: EpisodeStore, episode: Episode, camera: str) -> Path:
    """Frame 0 of a camera's clip as a JPEG, extracted on first request and kept."""
    folder = store.episode_folder(episode)
    still = frame0_path(folder, camera)
    if not still.exists():
        await asyncio.to_thread(first_frame, clip_path(folder, camera), still)
    return still
