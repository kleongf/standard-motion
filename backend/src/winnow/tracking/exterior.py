"""The `track_exterior` step: SAM follows the task object through the view the curator boxed it
in, seeded from that frame-0 box, at 5 fps. Placement Criteria read this track."""

import asyncio
from collections.abc import Mapping

from meta_sam_parser import FramePrompt, PromptBox, PromptObject, build_object_prompt

from winnow.boxes.models import Box
from winnow.boxes.store import BoxStore
from winnow.episodes.clips import SAM_FPS, probe
from winnow.episodes.models import Episode
from winnow.episodes.store import EpisodeStore, sam_clip_path
from winnow.jobs.models import Step, WorkItem
from winnow.meta.client import MetaClient
from winnow.meta.models import SamRequest
from winnow.tracking.models import Track
from winnow.tracking.sam_output import one_per_frame, parse_boxes
from winnow.tracking.store import TrackStore

BOX_STEPS = ("track_exterior", "target_box")


def box_items(episode_id: str, steps: tuple[str, ...] = BOX_STEPS) -> list[WorkItem]:
    """What saving an Episode's box queues: its exterior track and its target box."""
    args: dict[str, object] = {"episode_id": episode_id}
    return [WorkItem(step, args, episode_id) for step in steps]


def box_prompt(box: Box, size: tuple[int, int]) -> str:
    """The hand-drawn box as SAM's frame-0 seed, scaled from frame-0 pixels to the clip's."""
    sx, sy = size[0] / box.frame_width, size[1] / box.frame_height
    seed = PromptBox(
        left=round(box.x1 * sx),
        top=round(box.y1 * sy),
        right=min(round(box.x2 * sx), size[0]),
        bottom=min(round(box.y2 * sy), size[1]),
    )
    prompt = FramePrompt(frame=0, box=seed)
    return build_object_prompt(size=size, objects=[PromptObject(id=1, prompts=[prompt])])


async def track_exterior(
    meta: MetaClient, tracks: TrackStore, episodes: EpisodeStore, episode: Episode, box: Box
) -> str | None:
    clip = sam_clip_path(episodes.episode_folder(episode), box.camera)
    frames, width, height = await asyncio.to_thread(probe, clip)
    prompt = box_prompt(box, (width, height))
    request = SamRequest(clip, prompt, frames, f"track_exterior:{episode.id}")
    found = one_per_frame(parse_boxes((await meta.sam_track(request)).text))
    track = Track(
        episode_id=episode.id,
        kind="exterior",
        camera=box.camera,
        status="tracked",
        fps=SAM_FPS,
        frames=frames,
        width=width,
        height=height,
        seed_frame=0,
        boxes=found,
        health=None,
    )
    tracks.save(track)
    return None if found else "SAM found nothing to track"


def current_exterior_track(tracks: list[Track], box: Box | None) -> Track | None:
    """The exterior track, if it follows the box as drawn now: a box redrawn on another view
    leaves the old track stale until the work it queued replaces it."""
    exterior = next((t for t in tracks if t.kind == "exterior"), None)
    if box is None or exterior is None or exterior.camera != box.camera:
        return None
    return exterior


def boxed_episode(
    episodes: EpisodeStore, boxes: BoxStore, args: Mapping[str, object]
) -> tuple[Episode, Box]:
    """The Episode a box step is for, and its box as it is now."""
    episode = episodes.get(str(args["episode_id"]))
    if episode is None:
        raise LookupError(f"No Episode {args['episode_id']}")
    box = boxes.get(episode.id)
    if box is None:
        raise LookupError(f"{episode.id} has no hand-drawn box")
    return episode, box


def track_exterior_step(
    meta: MetaClient, tracks: TrackStore, boxes: BoxStore, episodes: EpisodeStore
) -> Step:
    async def step(args: Mapping[str, object]) -> str | None:
        episode, box = boxed_episode(episodes, boxes, args)
        return await track_exterior(meta, tracks, episodes, episode, box)

    return step
