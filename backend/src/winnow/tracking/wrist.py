"""The `track_wrist` step: SAM tracks the held object in the wrist view, with no human input.

The wrist camera is fixed relative to the gripper, so just after the first closure the object
sits at the same spot in every Episode. SAM is seeded there with a point, plus negative points
on the fingers so it doesn't segment the gripper, and tracks both ways from that frame.
Settled on droid_100 Episodes 16 and 42 and droid_1.0.1 Episodes 1, 9 and 17 (#17).
"""

import asyncio
from collections.abc import Mapping

from meta_sam_parser import (
    FramePrompt,
    PromptObject,
    PromptPoint,
    PromptPointLabel,
    build_object_prompt,
)

from winnow.criteria.grasps import closures
from winnow.episodes.clips import SAM_FPS, probe
from winnow.episodes.models import Episode, EpisodeSignals
from winnow.episodes.store import EpisodeStore, sam_clip_path
from winnow.jobs.models import Step
from winnow.meta.client import MetaClient
from winnow.meta.models import SamRequest
from winnow.tracking.models import Track, TrackBox
from winnow.tracking.sam_output import one_per_frame, parse_boxes
from winnow.tracking.store import TrackStore

WRIST_CAMERA = "wrist_image_left"
# Closed means gripper > 0.3 for the seed: the level the recipe was settled with, kept apart
# from the Rubric's gripper-closed level so tuning that never moves the seed.
SEED_CLOSED_LEVEL = 0.3
SEED_DELAY_FRAMES = 3  # robot-data frames after the first closure: the fingers have settled
RECIPE_SIZE = (320, 180)  # the frame size the points below were chosen on
OBJECT_POINT = (190, 105)  # between the fingertips
FINGER_POINTS = ((120, 150), (260, 150), (190, 172))  # left finger, right finger, palm
SAM_METADATA = {"include_confidence": "true", "propagation_direction": "both"}


def seed_frame(signals: EpisodeSignals, sam_frames: int) -> int | None:
    """The 5 fps frame to seed on: the first gripper closure plus a few frames. None if the
    gripper never closes."""
    found = closures(signals.gripper, SEED_CLOSED_LEVEL)
    if not found:
        return None
    frame = min(found[0].start + SEED_DELAY_FRAMES, len(signals.gripper) - 1)
    return min(int(frame * SAM_FPS / signals.fps), sam_frames - 1)


def wrist_prompt(seed: int, size: tuple[int, int]) -> str:
    """The recipe's points, scaled from the 320x180 frame they were chosen on."""

    def point(xy: tuple[int, int], label: PromptPointLabel) -> PromptPoint:
        x = min(round(xy[0] * size[0] / RECIPE_SIZE[0]), size[0] - 1)
        y = min(round(xy[1] * size[1] / RECIPE_SIZE[1]), size[1] - 1)
        return PromptPoint(x=x, y=y, label=label)

    points = [point(OBJECT_POINT, "positive"), *(point(p, "negative") for p in FINGER_POINTS)]
    prompt = FramePrompt(frame=seed, points=points)
    return build_object_prompt(size=size, objects=[PromptObject(id=1, prompts=[prompt])])


async def track_wrist(
    meta: MetaClient, tracks: TrackStore, episodes: EpisodeStore, episode: Episode
) -> str | None:
    folder = episodes.episode_folder(episode)
    clip = sam_clip_path(folder, WRIST_CAMERA)
    frames, width, height = await asyncio.to_thread(probe, clip)
    seed = seed_frame(episodes.load_signals(episode), frames)
    boxes: list[TrackBox] = []
    if seed is not None:
        request = SamRequest(
            clip,
            wrist_prompt(seed, (width, height)),
            frames,
            f"track_wrist:{episode.id}",
            SAM_METADATA,
        )
        boxes = one_per_frame(parse_boxes((await meta.sam_track(request)).text))
    track = Track(
        episode_id=episode.id,
        kind="wrist",
        camera=WRIST_CAMERA,
        status="tracked" if seed is not None else "no_closure",
        fps=SAM_FPS,
        frames=frames,
        width=width,
        height=height,
        seed_frame=seed,
        boxes=boxes,
        health=None,
    )
    tracks.save(track)
    if seed is None:
        return "the gripper never closed: no wrist track"
    return None if boxes else "SAM found nothing to track"


def track_wrist_step(meta: MetaClient, tracks: TrackStore, episodes: EpisodeStore) -> Step:
    async def step(args: Mapping[str, object]) -> str | None:
        episode = episodes.get(str(args["episode_id"]))
        if episode is None:
            raise LookupError(f"No Episode {args['episode_id']}")
        if WRIST_CAMERA not in episode.cameras:
            raise LookupError(f"{episode.id} has no wrist clip")
        return await track_wrist(meta, tracks, episodes, episode)

    return step
