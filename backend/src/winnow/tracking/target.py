"""The target box: where the object should end up, on frame 0 of the hand-drawn box's view.

The `target_box` step asks SAM for the instruction's target with a text prompt on that one frame,
with no track. The curator can draw it instead, and a drawn one wins: `chosen_target_box` is what
Prepare, the Workstation and scoring read.
"""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from winnow.boxes.models import Box, FrameRect
from winnow.boxes.store import BoxStore
from winnow.episodes.clips import cut_h264, probe
from winnow.episodes.models import Episode
from winnow.episodes.store import EpisodeStore, sam_clip_path
from winnow.jobs.models import Step
from winnow.meta.client import MetaClient
from winnow.meta.models import SamRequest
from winnow.tracking.exterior import boxed_episode
from winnow.tracking.models import FrameBox, TargetBox, TargetStatus
from winnow.tracking.sam_output import parse_boxes
from winnow.tracking.target_store import TargetBoxStore
from winnow.tracking.target_words import target_words

SAM_METADATA = {"include_confidence": "true"}


def episode_target(episode: Episode) -> str | None:
    """The words to prompt SAM with: the selection pass's target where it named one, else the
    instruction's."""
    if episode.instruction is None:
        return None
    return episode.task_target or target_words(episode.instruction)


def chosen_target_box(targets: TargetBoxStore, box: Box) -> TargetBox | None:
    """The curator's target box if drawn on the boxed view, else SAM's; None before either."""
    on_view = [t for t in targets.for_episode(box.episode_id) if t.camera == box.camera]
    by_origin = {t.origin: t for t in on_view}
    return by_origin.get("hand") or by_origin.get("sam")


def chosen_target_boxes(targets: TargetBoxStore, boxes: list[Box]) -> list[TargetBox]:
    chosen = (chosen_target_box(targets, box) for box in boxes)
    return [target for target in chosen if target is not None]


def _target_box(
    box: Box,
    status: TargetStatus,
    target: str | None,
    found: FrameBox | None,
    origin: Literal["sam", "hand"] = "sam",
) -> TargetBox:
    return TargetBox(
        episode_id=box.episode_id,
        camera=box.camera,
        origin=origin,
        status=status,
        target=target,
        box=found,
        frame_width=box.frame_width,
        frame_height=box.frame_height,
        made_at=datetime.now(UTC).isoformat(),
    )


def draw_target_box(
    targets: TargetBoxStore, episode: Episode, box: Box, rect: FrameRect
) -> TargetBox:
    """The curator's target box, in frame-0 pixels of the boxed view."""
    drawn = FrameBox(left=rect.x1, top=rect.y1, right=rect.x2, bottom=rect.y2)
    return targets.save(_target_box(box, "found", episode_target(episode), drawn, "hand"))


def frame_zero_clip(folder: Path, camera: str) -> Path:
    """Frame 0 of the view's 5 fps clip as a one-frame clip: SAM only reads video."""
    still = folder / f"{camera}.frame0.mp4"
    if not still.exists():
        cut_h264(str(sam_clip_path(folder, camera)), 0.0, 1, still)
    return still


async def _ask_sam(meta: MetaClient, clip: Path, target: str, box: Box) -> FrameBox | None:
    frames, width, height = await asyncio.to_thread(probe, clip)
    request = SamRequest(clip, target, frames, f"target_box:{box.episode_id}", SAM_METADATA)
    found = [b for b in parse_boxes((await meta.sam_track(request)).text) if b.frame == 0]
    if not found:
        return None
    best = max(found, key=lambda b: b.confidence or 0)
    sx, sy = box.frame_width / width, box.frame_height / height
    return FrameBox(
        left=best.left * sx, top=best.top * sy, right=best.right * sx, bottom=best.bottom * sy
    )


async def find_target_box(
    meta: MetaClient, targets: TargetBoxStore, episodes: EpisodeStore, episode: Episode, box: Box
) -> str | None:
    target = episode_target(episode)
    if episode.instruction is None:
        targets.save(_target_box(box, "no_instruction", None, None))
        return "no instruction: no target prompt"
    if target is None:
        targets.save(_target_box(box, "no_target", None, None))
        return "the instruction names no target"
    clip = await asyncio.to_thread(frame_zero_clip, episodes.episode_folder(episode), box.camera)
    found = await _ask_sam(meta, clip, target, box)
    targets.save(_target_box(box, "found" if found else "not_found", target, found))
    return None if found else f"SAM found no {target}"


def target_box_step(
    meta: MetaClient, targets: TargetBoxStore, boxes: BoxStore, episodes: EpisodeStore
) -> Step:
    async def step(args: Mapping[str, object]) -> str | None:
        episode, box = boxed_episode(episodes, boxes, args)
        return await find_target_box(meta, targets, episodes, episode, box)

    return step
