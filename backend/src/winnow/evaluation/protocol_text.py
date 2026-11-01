"""The protocol sections as plain text for `winnow eval`: the source ablation, tracking health,
cost, review minutes, the Dataset outcome and the FailBench check."""

from winnow.evaluation.models import EvaluationReport
from winnow.evaluation.protocol_models import MetaCost, OutcomeDisagreement, ReviewTime
from winnow.evaluation.stats import Proportion


def _counted(p: Proportion | None) -> str:
    if p is None:
        return "no slack"
    if p.low is None or p.high is None:
        return f"{p.count} of {p.of}"
    return f"{p.count} of {p.of} ({p.low:.2f}–{p.high:.2f})"


def _usd(usd: float | None) -> str:
    return "—" if usd is None else f"${usd:.2f}"


def _minutes(minutes: float | None) -> str:
    return "—" if minutes is None else f"{minutes:.1f} min"


def ablation_text(report: EvaluationReport) -> list[str]:
    return [
        "Source ablation ($0, re-scored from the cache): false keeps · right reason · coverage",
        *(
            f"  {r.label} ({r.criteria} of {r.of} Criteria): {_counted(r.false_keeps)} · "
            f"{_counted(r.right_reason)} · {_counted(r.coverage)}"
            for r in report.ablation
        ),
    ]


def tracking_text(report: EvaluationReport) -> list[str]:
    return [
        "SAM tracking health:",
        *(
            f"  {r.label}: lost on {_counted(r.lost)} · {r.needs_review} Needs review with a "
            f"lost track · {r.too_small} on objects too small to see"
            for r in report.tracking_health
        ),
    ]


def cost_text(cost: MetaCost, time: ReviewTime) -> list[str]:
    return [
        f"Cost per 1,000 Episodes (extrapolated from {cost.episodes} Episodes' cost log): "
        f"Winnow {_usd(cost.winnow_per_1000_usd)} · Spark alone "
        f"{_usd(cost.spark_alone_per_1000_usd)}",
        f"  Human cost per Episode: one hand-drawn box plus "
        f"{_minutes(time.needs_review_minutes_per_episode)} of Needs review "
        f"({_counted(time.needs_review)} Episodes)",
        f"Review minutes saved: {_minutes(time.minutes_per_episode)} per Episode x "
        f"{time.decided} decided automatically = {_minutes(time.minutes_saved)}",
    ]


def _disagreement(d: OutcomeDisagreement) -> str:
    label = f"fails {', '.join(d.failed_phrases)}" if d.failed_phrases else "meets it"
    outcome = "success" if d.dataset_outcome else "failure"
    return f"  {d.episode_id}: Dataset {outcome}, Reference label {label}"


def outcome_text(report: EvaluationReport) -> list[str]:
    o, f = report.dataset_outcome, report.failbench
    return [
        f"Dataset outcome against Reference labels, on {o.compared} Episodes: success and meets "
        f"{o.success_meets} · success but fails {o.success_fails} · failure but meets "
        f"{o.failure_meets} · failure and fails {o.failure_fails}",
        *(_disagreement(d) for d in o.disagreements),
        f"FailBench check against the Dataset outcome: agrees on {_counted(f.agrees)} · "
        f"catches {_counted(f.failures_caught)} failures"
        + (
            "" if f.balanced_accuracy is None else f" · balanced accuracy {f.balanced_accuracy:.2f}"
        ),
    ]


def protocol_text(report: EvaluationReport) -> list[str]:
    return [
        *ablation_text(report),
        *tracking_text(report),
        *cost_text(report.cost, report.review_time),
        *outcome_text(report),
    ]
