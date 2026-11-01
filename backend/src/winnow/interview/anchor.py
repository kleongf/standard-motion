"""What the interview may show of the anchor pool: the draft scored on each anchor Episode with a
Reference label (the rest stay blind), so each Criterion's result there and the stretch it was
measured over; and each grasp setting's value at one moment of each such Episode."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from winnow.core.context import AppContext
from winnow.criteria.grasps import closures
from winnow.criteria.models import RubricSettings, Setting
from winnow.episodes.models import EpisodeSignals
from winnow.interview.models import Clip, SettingName
from winnow.reference_labels.gate import revealed_ids
from winnow.rubric.anchor_pool import anchor_episodes
from winnow.rubric.models import RubricDraft
from winnow.triage.models import CriterionResult, Triage
from winnow.triage.scoring import score
from winnow.triage.service import episode_facts

PAD_S = 1.0  # shown either side of the measured moments


@dataclass(frozen=True)
class AnchorResult:
    episode_id: str
    value: float
    measurement: str
    camera: str | None
    clip: Clip


def result_clip(result: CriterionResult, duration: float) -> Clip:
    """Around the moments the measurement marks, else its window, else the whole Episode."""
    times = [m.t for m in result.moments]
    if times:
        return Clip(start=max(0.0, min(times) - PAD_S), end=min(duration, max(times) + PAD_S))
    if result.window is not None:
        return Clip(start=result.window.start, end=result.window.end)
    return Clip(start=0.0, end=duration)


@dataclass(frozen=True)
class AnchorTriage:
    """The draft scored on one anchor Episode with a Reference label, with what a clip of it
    needs."""

    episode_id: str
    camera: str | None  # the view to play when a result names none
    duration: float  # s
    triage: Triage

    def camera_for(self, result: CriterionResult) -> str | None:
        return result.camera or self.camera


def anchor_triage(ctx: AppContext, draft: RubricDraft) -> list[AnchorTriage]:
    """Every Criterion of the draft, switched off or not, scored on each revealed anchor Episode
    (with no label: the interview asks about the Criteria's own results)."""
    revealed = revealed_ids(ctx)
    everything = draft.rubric().model_copy(update={"criteria": draft.criteria})
    found: list[AnchorTriage] = []
    for episode in anchor_episodes(ctx):
        if episode.id not in revealed:
            continue
        facts = episode_facts(ctx, episode)
        duration = float(facts.t[-1]) if len(facts.t) else 0.0
        camera = episode.cameras[0] if episode.cameras else None
        found.append(AnchorTriage(episode.id, camera, duration, score(everything, facts)))
    return found


def anchor_results(
    draft: RubricDraft, triaged: Sequence[AnchorTriage]
) -> dict[str, list[AnchorResult]]:
    """By Criterion id, the anchor Episodes it measured a value on."""
    found: dict[str, list[AnchorResult]] = {c.id: [] for c in draft.criteria}
    for episode in triaged:
        for result in episode.triage.criteria:
            if result.value is None:
                continue
            found[result.criterion_id].append(
                AnchorResult(
                    episode.episode_id,
                    result.value,
                    result.measurement,
                    episode.camera_for(result),
                    result_clip(result, episode.duration),
                )
            )
    return found


@dataclass(frozen=True)
class _Moment:
    value: float
    start: int  # the clip's frames
    end: int


def _level_moment(signals: EpisodeSignals, level: Setting) -> _Moment | None:
    """The closure whose peak sits nearest the closed level, at that peak. Closures are read at
    the margin's lower edge, so those just under the level count too."""
    found: list[_Moment] = []
    for closure in closures(signals.gripper, max(level.value - level.margin, 0.0)):
        stretch = signals.gripper[closure.start : closure.end + 1]
        peak = closure.start + int(np.argmax(stretch))
        found.append(_Moment(float(stretch.max()), peak, peak))
    return min(found, key=lambda m: abs(m.value - level.value), default=None)


def _rise_moment(signals: EpisodeSignals, settings: RubricSettings) -> _Moment | None:
    """The closure whose rise sits nearest the grasp rule, from its start to its highest climb."""
    z = signals.position[:, 2]
    found: list[_Moment] = []
    for closure in closures(signals.gripper, settings.gripper_closed_level.value):
        heights = z[closure.start : closure.end + 1]
        climb = heights - np.minimum.accumulate(heights)
        top = closure.start + int(np.argmax(climb))
        found.append(_Moment(float(climb.max()), closure.start, top))
    rule = settings.grasp_rise_m.value
    return min(found, key=lambda m: abs(m.value - rule), default=None)


def _camera(cameras: list[str], wrist: bool) -> str | None:
    """The wrist view shows the fingers close; an exterior one shows the arm rise."""
    preferred = [c for c in cameras if ("wrist" in c) == wrist]
    return next(iter(preferred or cameras), None)


def setting_points(
    episode_id: str, cameras: list[str], signals: EpisodeSignals, settings: RubricSettings
) -> dict[SettingName, AnchorResult]:
    """Each grasp setting's value at the Episode's moment nearest it; none without a closure."""
    stamps = signals.timestamps
    t = [round(float(v - stamps[0]), 4) for v in stamps]  # as `EpisodeFacts.t`
    duration = t[-1] if t else 0.0
    moments: dict[SettingName, _Moment | None] = {
        "gripper_closed_level": _level_moment(signals, settings.gripper_closed_level),
        "grasp_rise_m": _rise_moment(signals, settings),
    }
    found: dict[SettingName, AnchorResult] = {}
    for name, moment in moments.items():
        if moment is None:
            continue
        level = name == "gripper_closed_level"
        found[name] = AnchorResult(
            episode_id,
            moment.value,
            f"closed to {moment.value:.2f}" if level else f"rose {moment.value * 100:.1f} cm",
            _camera(cameras, wrist=level),
            Clip(
                start=round(max(0.0, t[moment.start] - PAD_S), 4),
                end=round(min(duration, t[moment.end] + PAD_S), 4),
            ),
        )
    return found


def anchor_setting_points(
    ctx: AppContext, settings: RubricSettings
) -> dict[SettingName, list[AnchorResult]]:
    """By grasp setting, its value at one moment of each anchor Episode with a closure."""
    revealed = revealed_ids(ctx)
    found: dict[SettingName, list[AnchorResult]] = {"gripper_closed_level": [], "grasp_rise_m": []}
    for episode in anchor_episodes(ctx):
        if episode.id not in revealed:
            continue
        signals = ctx.episodes.load_signals(episode)
        for name, point in setting_points(episode.id, episode.cameras, signals, settings).items():
            found[name].append(point)
    return found
