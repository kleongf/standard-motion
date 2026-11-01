"""The report as plain text for `winnow eval`: counts first, then 95% intervals, never "±"."""

from winnow.evaluation.models import (
    EvaluationReport,
    LengthRule,
    MatchedCoverage,
    McNemar,
    PhraseFailures,
    Proportion,
    RightReason,
    SystemRow,
)
from winnow.evaluation.protocol_text import protocol_text
from winnow.sets.models import SET_LABELS

COLUMNS = ("System", "Keeps", "Rejects", "Undecided", "Coverage", "False keeps", "False rejects")


def counted(p: Proportion) -> str:
    """e.g. "1 of 4 (0.05–0.70)"; with nothing to count, just "0 of 0"."""
    if p.low is None or p.high is None:
        return f"{p.count} of {p.of}"
    return f"{p.count} of {p.of} ({p.low:.2f}–{p.high:.2f})"


def length_rule_text(rule: LengthRule | None) -> str:
    if rule is None:
        return "Length alone: no labelled Episode to fit a threshold to"
    side = "≥" if rule.keep == "longer" else "≤"
    return (
        f"Length alone keeps Episodes {side} {rule.threshold_s:.1f} s (threshold set in hindsight)"
    )


def _cells(row: SystemRow) -> tuple[str, ...]:
    return (
        row.label,
        str(row.keeps),
        str(row.rejects),
        str(row.undecided),
        f"{row.coverage.count} of {row.coverage.of}",
        counted(row.false_keeps),
        counted(row.false_rejects),
    )


def right_reason_text(right: RightReason) -> list[str]:
    slack = right.slack
    if slack.seconds is None:
        return ["Right reason on correct Rejects: no slack yet (no Phrase failed in both passes)"]
    scored = " · ".join(f"{r.label} {counted(r.at_slack)}" for r in right.rows if r.at_slack)
    return [
        f"Right reason on correct Rejects, at {slack.seconds:.2f} s slack (95th percentile of "
        f"{slack.edges} interval edges over {slack.episodes} relabelled Episodes):",
        f"  {scored}",
    ]


def matched_text(matched: MatchedCoverage) -> str:
    rows = {row.system: row for row in matched.rows}
    winnow, spark = rows["winnow"], rows["spark_alone"]
    return (
        f"Keep precision at matched coverage (Winnow decides {matched.target} of "
        f"{matched.episodes}): Winnow {counted(winnow.keep_precision)} · "
        f"Spark alone {counted(spark.keep_precision)}, covering {spark.covered}"
    )


def mcnemar_text(m: McNemar) -> str:
    return (
        f"McNemar, on {m.compared} Episodes both decided: only Winnow right "
        f"{m.winnow_only_right} · only Spark alone right {m.spark_alone_only_right}"
    )


def phrase_text(p: PhraseFailures) -> str:
    noun = "failure" if p.failures == 1 else "failures"
    flag = " (too few to score)" if p.too_few else ""
    return (
        f"  {p.phrase}: {p.failures} {noun}, Winnow rejects {p.winnow_rejects}, "
        f"Spark alone {p.spark_alone_rejects}{flag}"
    )


def report_text(report: EvaluationReport) -> str:
    header = (
        f"{SET_LABELS[report.set_name]} · Rubric v{report.rubric_version} · "
        f"{report.labelled} of {report.episodes} Episodes labelled · "
        f"{report.description_failures} description failures"
    )
    table = [COLUMNS, *(_cells(row) for row in report.comparison.rows)]
    widths = [max(len(line[i]) for line in table) for i in range(len(COLUMNS))]
    lines = [
        "  ".join(cell.ljust(w) for cell, w in zip(line, widths, strict=True)) for line in table
    ]
    rule = length_rule_text(report.comparison.length_rule)
    sections = [
        *right_reason_text(report.right_reason),
        matched_text(report.matched_coverage),
        mcnemar_text(report.mcnemar),
        "Failures per Phrase:",
        *(phrase_text(p) for p in report.phrase_failures),
        *protocol_text(report),
    ]
    table_lines = [line.rstrip() for line in lines]
    return "\n".join([header, "", *table_lines, "", rule, "", *sections]) + "\n"
