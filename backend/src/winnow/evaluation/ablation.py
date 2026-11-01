"""The $0 source ablation: what each Meta model adds. Winnow is re-scored with some sources'
Criteria left out (robot data only; plus SAM's tracks; plus Spark's visual answers; all), from
the facts and answers already stored, so it makes no Meta call."""

from collections.abc import Callable, Sequence

from winnow.criteria.primitives import PRIMITIVES, Source
from winnow.evaluation.cases import EvaluationCase
from winnow.evaluation.comparison import Outcome, system_row
from winnow.evaluation.models import Slack
from winnow.evaluation.protocol_models import AblationRow, SourceMask
from winnow.evaluation.right_reason import right_reason
from winnow.rubric.models import Rubric

SAM: tuple[Source, ...] = ("wrist track", "exterior track")
MASKS: dict[SourceMask, tuple[str, frozenset[Source]]] = {
    "robot_data": ("Robot data only", frozenset({"robot data"})),
    "robot_data_sam": ("Robot data + SAM", frozenset({"robot data", *SAM})),
    "robot_data_visual": ("Robot data + Spark visual", frozenset({"robot data", "video"})),
    "all": ("All sources", frozenset({"robot data", *SAM, "video"})),
}


def masked(rubric: Rubric, sources: frozenset[Source]) -> Rubric:
    """The Rubric with only the Criteria that read one of `sources`. A Phrase left with no
    Criterion is unchecked, so it no longer decides the Episode."""
    kept = [c for c in rubric.criteria if PRIMITIVES[c.primitive].source in sources]
    return rubric.model_copy(update={"criteria": kept})


def ablation_row(
    mask: SourceMask, criteria: int, of: int, cases: Sequence[EvaluationCase], slack: Slack
) -> AblationRow:
    """`cases` are the labelled Episodes scored with the masked Rubric."""
    outcomes: list[Outcome] = [
        (c.description_failure, None if c.winnow == "needs_review" else c.winnow) for c in cases
    ]
    row = system_row("winnow", outcomes)
    [reason] = [r for r in right_reason(cases, slack).rows if r.system == "winnow"]
    return AblationRow(
        mask=mask,
        label=MASKS[mask][0],
        criteria=criteria,
        of=of,
        false_keeps=row.false_keeps,
        right_reason=reason.at_slack,
        coverage=row.coverage,
    )


def ablation(
    rubric: Rubric, scored: Callable[[Rubric], list[EvaluationCase]], slack: Slack
) -> list[AblationRow]:
    """One row per mask; `scored` scores every labelled Episode against a Rubric."""
    rows: list[AblationRow] = []
    for mask, (_, sources) in MASKS.items():
        kept = masked(rubric, sources)
        rows.append(
            ablation_row(mask, len(kept.criteria), len(rubric.criteria), scored(kept), slack)
        )
    return rows
