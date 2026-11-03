"""What an export would hold, before it runs: per source, the Reference-labelled Episodes outside
the Test set by Triage decision, those awaiting a label, and those in the Test set. Only the
labelled are scored, so the preview shows no decision the app keeps hidden; exporting decides the
rest, which is why the UI warns first."""

from collections import Counter

from standard_motion.core.context import AppContext
from standard_motion.export.models import DecisionCounts, ExportPreview, Include, SourceCounts
from standard_motion.export.plan import has_run, test_set_ids
from standard_motion.export.tally import exported_count, nothing_exported
from standard_motion.reference_labels.gate import revealed_ids
from standard_motion.triage.service import scored


def _total(sources: list[SourceCounts]) -> DecisionCounts:
    return DecisionCounts(
        keep=sum(s.keep for s in sources),
        needs_review=sum(s.needs_review for s in sources),
        reject=sum(s.reject for s in sources),
        awaiting_label=sum(s.awaiting_label for s in sources),
        test_set=sum(s.test_set for s in sources),
    )


def export_preview(ctx: AppContext, include: Include) -> ExportPreview:
    episodes = ctx.episodes.list()
    test_set, labelled = test_set_ids(ctx), revealed_ids(ctx)
    shown = [e for e in episodes if e.id not in test_set and e.id in labelled]
    version, triages = scored(ctx, shown)
    tally: Counter[tuple[str, str]] = Counter()
    for episode, triage in zip(shown, triages, strict=True):
        tally[episode.source, triage.decision] += 1
    for e in episodes:
        if e.id in test_set:
            tally[e.source, "test_set"] += 1
        elif e.id not in labelled:
            tally[e.source, "awaiting_label"] += 1
    sources = [
        SourceCounts(
            source=name,
            keep=tally[name, "keep"],
            needs_review=tally[name, "needs_review"],
            reject=tally[name, "reject"],
            awaiting_label=tally[name, "awaiting_label"],
            test_set=tally[name, "test_set"],
        )
        for name in sorted({e.source for e in episodes})
    ]
    total = _total(sources)
    return ExportPreview(
        include=include,
        rubric_version=version.version,
        sources=sources,
        exported=exported_count(total, include),
        nothing_exported=nothing_exported(total, include, has_run(ctx)),
    )
