"""A camera's per-Episode pixel stats, computed from its exported clip as LeRobot's
`compute_episode_stats` computes them for a video feature: up to about 100 frames sampled
evenly, each strided down to about 150 pixels across when 300 or more, and per channel the
pixels' min, max, mean, std and quantiles in [0, 1], shaped (3, 1, 1), with the count of frames
sampled. LeRobot's training reads them for every camera, so a source without them gets these."""

import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from standard_motion.episodes.clips import probe
from standard_motion.export.stats import QUANTILES

_TARGET, _THRESHOLD = 150, 300  # LeRobot's auto_downsample_height_width


def sampled(length: int) -> list[int]:
    """The frames LeRobot samples from an Episode of `length` frames (its `sample_indices`)."""
    count = max(min(100, length), min(int(length**0.75), 10_000))
    return [int(i) for i in np.round(np.linspace(0, length - 1, count))]


def _frames(clip: Path, start: float, indices: list[int]) -> NDArray[np.uint8]:
    """The frames at `indices` of the clip from `start`, as (frames, height, width, 3)."""
    _, width, height = probe(clip)
    select = "+".join(f"eq(n\\,{i})" for i in indices)
    result = subprocess.run(
        [
            *("ffmpeg", "-loglevel", "error", "-ss", f"{start:.6f}", "-i", str(clip)),
            *("-vf", f"select={select}", "-fps_mode", "passthrough"),
            *("-frames:v", str(len(indices)), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"),
        ],
        capture_output=True, check=False,
    )  # fmt: skip
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode().strip()}")
    frames = np.frombuffer(result.stdout, np.uint8).reshape(-1, height, width, 3)
    if len(frames) != len(indices):
        raise RuntimeError(f"{clip} has {len(frames)} of the {len(indices)} frames sampled")
    return frames


def _downsampled(frames: NDArray[np.uint8]) -> NDArray[np.uint8]:
    height, width = frames.shape[1:3]
    if max(width, height) < _THRESHOLD:
        return frames
    step = int(max(width, height) / _TARGET)
    return frames[:, ::step, ::step]


def video_stats(clip: Path, start: float, length: int, key: str) -> dict[str, list[Any]]:
    """meta/episodes' `stats/<key>/...` columns for the Episode's `length` frames of `clip`
    from `start`."""
    indices = sampled(length)
    pixels = _downsampled(_frames(clip, start, indices)).reshape(-1, 3) / 255.0
    found: dict[str, NDArray[Any]] = {
        "min": pixels.min(axis=0),
        "max": pixels.max(axis=0),
        "mean": pixels.mean(axis=0),
        "std": pixels.std(axis=0),
        **{q: np.quantile(pixels, p, axis=0) for q, p in QUANTILES.items()},
    }
    stats = {f"stats/{key}/{s}": v.reshape(3, 1, 1).tolist() for s, v in found.items()}
    return stats | {f"stats/{key}/count": [len(indices)]}
