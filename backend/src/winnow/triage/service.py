"""Gathers each Episode's facts and labels and scores it against the latest Rubric version, with
the margin multiplier s it was calibrated with (1 until then), on every read. Spark's Reason
replaces the template Reason when one is stored for the same inputs."""

from winnow.core.context import AppContext
from winnow.criteria.facts import EpisodeFacts
from winnow.episodes.models import Episode
from winnow.rubric.models import RubricVersion
from winnow.tracking.exterior import current_exterior_track
from winnow.tracking.target import chosen_target_box
from winnow.triage.models import EpisodeTriage, PhraseChip, Triage, TriageList, TriageRow
from winnow.triage.quality import qualities
from winnow.triage.scoring import score
from winnow.triage.spark_reason import reason_key


def episode_facts(ctx: AppContext, episode: Episode) -> EpisodeFacts:
    """Robot data, SAM's tracks so far, the target box, as they stand for the object's box now,
    and Spark's stored answers to visual Criteria."""
    tracks = ctx.tracks.for_episode(episode.id)
    box = ctx.boxes.get(episode.id)
    return EpisodeFacts(
        ctx.episodes.load_signals(episode),
        wrist=next((t for t in tracks if t.kind == "wrist"), None),
        exterior=current_exterior_track(tracks, box),
        target=None if box is None else chosen_target_box(ctx.targets, box),
        visual=ctx.visual.for_episode(episode.id),
    )


def _template(ctx: AppContext, version: RubricVersion, episode: Episode, s: float) -> Triage:
    """The Episode scored, with its template Reason."""
    facts = episode_facts(ctx, episode)
    return score(version.rubric, facts, ctx.labels.in_force(episode.id), s)


def _triage(ctx: AppContext, version: RubricVersion, episode: Episode, s: float) -> EpisodeTriage:
    triage = _template(ctx, version, episode, s)
    written = ctx.reasons.get(episode.id, reason_key(version.version, triage))
    if written is not None and triage.decision != "keep":
        triage = triage.model_copy(update={"reason": written, "reason_source": "spark"})
    return EpisodeTriage(
        **triage.model_dump(), episode_id=episode.id, rubric_version=version.version
    )


def template_triages(
    ctx: AppContext, episodes: list[Episode]
) -> tuple[RubricVersion, list[Triage]]:
    """Every one of `episodes` scored like `scored`, but each with its template Reason: what
    Spark's Reasons are written from and keyed by."""
    version = ctx.rubrics.latest()
    s = ctx.calibrations.s_for(version.version)
    return version, [_template(ctx, version, e, s) for e in episodes]


def episode_triage(ctx: AppContext, episode: Episode) -> EpisodeTriage:
    version = ctx.rubrics.latest()
    return _triage(ctx, version, episode, ctx.calibrations.s_for(version.version))


def scored(ctx: AppContext, episodes: list[Episode]) -> tuple[RubricVersion, list[EpisodeTriage]]:
    """Every one of `episodes` scored against the latest Rubric version, with its labels, and
    its quality within them: median and MAD need the whole run."""
    version = ctx.rubrics.latest()
    s = ctx.calibrations.s_for(version.version)
    triages = [_triage(ctx, version, e, s) for e in episodes]
    return version, [
        t.model_copy(update={"quality": q})
        for t, q in zip(triages, qualities(triages), strict=True)
    ]


def triage_list(ctx: AppContext, episodes: list[Episode]) -> TriageList:
    version, triages = scored(ctx, episodes)
    return TriageList(rubric_version=version.version, rows=[_row(t) for t in triages])


def plain_reason(triage: EpisodeTriage) -> str:
    return "".join(span.text for span in triage.reason)


def _row(triage: EpisodeTriage) -> TriageRow:
    return TriageRow(
        episode_id=triage.episode_id,
        decision=triage.decision,
        reason=plain_reason(triage),
        confidence=triage.confidence,
        not_passed=[
            PhraseChip(phrase=p.phrase, status=p.status)
            for p in triage.phrases
            if p.status is not None and p.status != "pass"
        ],
        uncertainty=list(dict.fromkeys(r.uncertainty for r in triage.criteria if r.uncertainty)),
        quality=triage.quality,
    )
