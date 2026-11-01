"""End-effector speed, smoothed the same way for the Workstation's plot and for Criteria."""

import numpy as np

from winnow.episodes.models import EpisodeSignals, FloatArray

SPEED_SMOOTHING_FRAMES = 5  # a third of a second at 15 Hz


def smoothed_speed(signals: EpisodeSignals) -> FloatArray:
    """m/s, one value per frame, averaged over SPEED_SMOOTHING_FRAMES."""
    n = len(signals.timestamps)
    step = np.linalg.norm(np.diff(signals.position, axis=0), axis=1) * signals.fps
    speed = np.concatenate([step[:1], step]) if len(step) else np.zeros(n)
    kernel = np.ones(SPEED_SMOOTHING_FRAMES) / SPEED_SMOOTHING_FRAMES
    padded = np.pad(speed, SPEED_SMOOTHING_FRAMES // 2, mode="edge")
    return np.convolve(padded, kernel, mode="valid")
