"""The Dataset outcome against the Reference labels, and the FailBench check against the Dataset
outcome. The Dataset outcome answers "was the task done", not "does it meet the Description", so
their disagreements are listed rather than scored."""

from collections.abc import Sequence

from winnow.evaluation.cases import EvaluationCase
from winnow.evaluation.comparison import Decision, balanced_accuracy
from winnow.evaluation.protocol_models import DatasetOutcome, FailBenchCheck, OutcomeDisagreement
from winnow.evaluation.stats import wilson


def dataset_outcome(cases: Sequence[EvaluationCase]) -> DatasetOutcome:
    flagged = [c for c in cases if c.dataset_outcome is not None]

    def count(success: bool, fails: bool) -> int:
        return sum(c.dataset_outcome == success and c.description_failure == fails for c in flagged)

    return DatasetOutcome(
        compared=len(flagged),
        no_outcome=len(cases) - len(flagged),
        success_meets=count(True, False),
        success_fails=count(True, True),
        failure_meets=count(False, False),
        failure_fails=count(False, True),
        disagreements=[
            OutcomeDisagreement(
                episode_id=c.episode_id,
                dataset_outcome=c.dataset_outcome is True,
                failed_phrases=list(c.failed),
            )
            for c in flagged
            if c.dataset_outcome == c.description_failure  # a success that fails, or vice versa
        ],
    )


def failbench_check(cases: Sequence[EvaluationCase]) -> FailBenchCheck:
    """Its answer as a decision (success: keep), against the Dataset outcome as the truth."""
    pairs = [
        (c.dataset_outcome, c.failbench)
        for c in cases
        if c.dataset_outcome is not None and c.failbench is not None
    ]
    failures: list[Decision] = [
        "keep" if said else "reject" for outcome, said in pairs if not outcome
    ]
    successes: list[Decision] = ["keep" if said else "reject" for outcome, said in pairs if outcome]
    return FailBenchCheck(
        answered=len(pairs),
        agrees=wilson(sum(outcome == said for outcome, said in pairs), len(pairs)),
        failures_caught=wilson(failures.count("reject"), len(failures)),
        balanced_accuracy=balanced_accuracy(failures, successes),
    )
