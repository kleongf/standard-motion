"""Counting what an export holds, and saying why it would hold nothing: no Episodes, only Test
set Episodes, no Rubric Run yet, or every Episode rejected (or Needs review, left out)."""

from winnow.export.models import DecisionCounts, Include


def exported_count(counts: DecisionCounts, include: Include) -> int:
    """How many of the counted decisions an export with `include` writes."""
    return counts.keep + (counts.needs_review if include == "keep_and_review" else 0)


def nothing_exported(counts: DecisionCounts, include: Include, ran: bool) -> str | None:
    """Why an export with `include` writes no Episode, or None when it writes some, or could:
    Episodes awaiting a Reference label are exported by decisions not yet shown. `ran` is
    whether a Rubric has been Run; before that the starter Rubric decides."""
    if exported_count(counts, include) > 0 or counts.awaiting_label > 0:
        return None
    decided = counts.keep + counts.needs_review + counts.reject
    if decided == 0 and counts.test_set > 0:
        return "Every Episode is in the Test set, which is never exported."
    if decided == 0:
        return "No Episodes yet: ingest some on the Prepare page."
    if not ran:
        return (
            "No Rubric has been Run yet, and the starter Rubric keeps none of these Episodes: "
            "run one on Describe & run."
        )
    if counts.needs_review > 0:
        return (
            "No Episode outside the Test set is kept: "
            f"{counts.reject} rejected, {counts.needs_review} Needs review. "
            "Include Needs review to export those."
        )
    return "Every Episode outside the Test set was rejected."
