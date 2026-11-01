"""The capabilities manifest compile shows Spark: what Winnow can check, and on what data.

Built from the catalog registry, so a primitive added there joins automatically, with its range
over the anchor pool, the robot data rate, the views and frame size, and which object tracks and
target boxes exist.
"""

from statistics import median

from winnow.core.context import AppContext
from winnow.criteria.catalog import CATALOG
from winnow.criteria.english import COMPARATORS, format_value
from winnow.criteria.grasps import find_grasps
from winnow.criteria.models import Criterion, RubricSettings
from winnow.criteria.primitives import PRIMITIVES, Primitive
from winnow.criteria.windows import WINDOW_NAMES
from winnow.episodes.clips import probe
from winnow.episodes.models import Episode
from winnow.episodes.store import clip_path
from winnow.triage.scoring import criterion_result
from winnow.triage.service import episode_facts


def _probe(primitive: Primitive) -> Criterion:
    info = PRIMITIVES[primitive]
    return Criterion(
        id=primitive,
        phrase="",
        primitive=primitive,
        params=dict(info.params),
        comparator="<=",
        threshold=0,
        unit=info.unit,
    )


def _ranges(
    ctx: AppContext, episodes: list[Episode], settings: RubricSettings
) -> dict[Primitive, list[float]]:
    """Each primitive's value on each anchor Episode, at its default params, whole Episode."""
    values: dict[Primitive, list[float]] = {p: [] for p in PRIMITIVES}
    free: list[Primitive] = [
        p for p in values if PRIMITIVES[p].kind != "visual"
    ]  # visual values cost a call
    for episode in episodes:
        facts = episode_facts(ctx, episode)
        grasps = find_grasps(facts.signals, settings)
        for primitive in free:
            value = criterion_result(_probe(primitive), facts, grasps).value
            if value is not None:
                values[primitive].append(value)
    return values


def _range(values: list[float], unit: str, of: int) -> str:
    if not values:
        return "no anchor-pool values yet"
    low, mid, high = (format_value(v, unit) for v in (min(values), median(values), max(values)))
    return f"anchor pool {low} to {high}, median {mid} ({len(values)} of {of} Episodes)"


def _primitive(primitive: Primitive, values: list[float], of: int) -> str:
    info = PRIMITIVES[primitive]
    params = ", ".join(f"{name}={default:g}" for name, default in info.params.items())
    what = CATALOG[primitive].english.format(**info.params).rstrip(",")
    fail = "a fail is conclusive" if info.conclusive else "a fail is inconclusive (only unsure)"
    return (
        f"- {primitive}({params}) -> {info.unit}: {what}. {info.kind.capitalize()}, from "
        f"{info.source}; {fail}; noise floor {format_value(info.noise_floor, info.unit)}; "
        f"{_range(values, info.unit, of)}."
    )


VISUAL = (
    "ask_video asks Spark about one short clip that code cuts to the window from one view (the "
    'first of "views") and crops: "crop" is "view" for the whole frame, or "placement" for the '
    "object's final box joined with the target box, enlarged (the view the object was boxed in). "
    'Use it only for what robot data and tracks can\'t decide. Give a yes/no "question" whose '
    "yes means the Phrase is met, and 2 paraphrases of it, asked one per sample; all 3 must "
    'answer pass for a pass. Compare with ">=" 3.'
)


def _frame_size(ctx: AppContext, episodes: list[Episode]) -> str:
    for episode in episodes:
        for camera in episode.cameras:
            try:
                _, width, height = probe(clip_path(ctx.episodes.episode_folder(episode), camera))
            except RuntimeError:
                continue
            return f"{width}x{height} px"
    return "unknown"


def _sources(ctx: AppContext, episodes: list[Episode]) -> list[str]:
    of = len(episodes)
    tracks = [t for e in episodes for t in ctx.tracks.for_episode(e.id) if t.status == "tracked"]
    targets = [t for e in episodes for t in ctx.targets.for_episode(e.id) if t.box is not None]
    views = sorted({camera for e in episodes for camera in e.cameras})
    durations = [e.duration_s for e in episodes]
    lengths = f"{min(durations):.1f} to {max(durations):.1f} s" if durations else "unknown"
    fps = sorted({f"{e.fps:g}" for e in episodes}) or ["unknown"]
    count = {kind: sum(1 for t in tracks if t.kind == kind) for kind in ("wrist", "exterior")}
    return [
        f"Robot data: end-effector position (m) and gripper (0 open, 1 closed) at "
        f"{'/'.join(fps)} Hz. Anchor-pool Episodes last {lengths}.",
        f"Views: {', '.join(views) or 'unknown'}; frames {_frame_size(ctx, episodes)}.",
        f"Object tracks (SAM, 5 fps): the wrist object track on {count['wrist']} of {of} "
        f"anchor Episodes; the exterior object track on {count['exterior']} of {of}; a target "
        f"box on frame 0 on {len(targets)} of {of}.",
    ]


def _settings(settings: RubricSettings) -> str:
    closed = settings.gripper_closed_level.value
    rise = format_value(settings.grasp_rise_m.value, "m")
    return (
        f"Rubric settings, which code applies to every grasp-based window: the gripper counts "
        f"as closed above {closed:g}; the grasp is the last closure during which the arm rises "
        f"{rise}, and earlier closures are failed attempts."
    )


def capabilities_manifest(
    ctx: AppContext, episodes: list[Episode], settings: RubricSettings
) -> str:
    """`episodes` is the anchor pool."""
    values = _ranges(ctx, episodes, settings)
    primitives = [_primitive(p, values[p], len(episodes)) for p in PRIMITIVES]
    windows = ", ".join(
        f"{kind} ({name.replace('{seconds:g}', 'N')})" for kind, name in WINDOW_NAMES.items()
    )
    return "\n".join(
        [
            f"Capabilities. The anchor pool is the Dev set: {len(episodes)} Episodes.",
            *_sources(ctx, episodes),
            "Primitives (each Criterion uses one; params with their defaults):",
            *primitives,
            VISUAL,
            f"Windows: {windows}.",
            f"Comparators: {', '.join(COMPARATORS)}.",
            _settings(settings),
        ]
    )
