"""What an export holds: every Episode outside the Test set, by its Triage decision under the
latest Rubric version, the Keeps only or the Needs review Episodes with them. A Reference label
only measures Standard Motion, so it never gates the export; exporting shows the decisions of
Episodes not labelled yet, which the preview counts first so the UI can warn before it runs."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from standard_motion.core.context import AppContext
from standard_motion.episodes.models import Episode
from standard_motion.export.models import (
    DecisionCounts,
    Exported,
    Include,
    Manifest,
    ManifestEpisode,
    Rejection,
    Skipped,
)
from standard_motion.export.tally import nothing_exported
from standard_motion.reference_labels.gate import revealed_ids
from standard_motion.triage.service import plain_reason, scored


@dataclass(frozen=True)
class ExportPlan:
    kept: dict[str, list[int]]  # source -> its exported Episodes' indices, ascending
    rejections: list[Rejection]  # every Episode decided and left out, with its Reason
    unlabelled: int  # of the Episodes decided, those without a Reference label
    test_set: int  # Episodes left out for being in it
    rubric_version: int
    s: float  # the margin multiplier the version is scored with
    include: Include = "keep"
    needs_review: frozenset[str] = field(default_factory=frozenset[str])  # exported ones' ids
    ran: bool = True  # whether a Rubric has been Run; before that, the starter one decides

    def episodes(self) -> list[tuple[str, int]]:
        """Every exported Episode in the order it's written: by source, then index."""
        return [(source, index) for source in sorted(self.kept) for index in self.kept[source]]

    def _decision(self, episode_id: str) -> Exported:
        return "needs_review" if episode_id in self.needs_review else "keep"

    def manifest(self, created_at: datetime) -> Manifest:
        """Each source's Episodes are renumbered from 0 in order, as they're written."""
        exported = [
            ManifestEpisode(
                exported_episode_index=new,
                source=source,
                source_episode_index=index,
                episode_id=f"{source}:{index}",
                decision=self._decision(f"{source}:{index}"),
            )
            for source in sorted(self.kept)
            for new, index in enumerate(self.kept[source])
        ]
        decisions = [r.decision for r in self.rejections]
        return Manifest(
            created_at=created_at.isoformat(),
            include=self.include,
            rubric_version=self.rubric_version,
            margin_multiplier=self.s,
            not_reference_labelled=self.unlabelled,
            exported=exported,
            skipped=Skipped(
                reject=decisions.count("reject"),
                needs_review=decisions.count("needs_review"),
                test_set=self.test_set,
            ),
        )

    def counts(self) -> DecisionCounts:
        exported = len(self.episodes())
        rejected = sum(r.decision == "reject" for r in self.rejections)
        needs_review = len(self.needs_review) + len(self.rejections) - rejected
        return DecisionCounts(
            keep=exported - len(self.needs_review),
            needs_review=needs_review,
            reject=rejected,
            awaiting_label=0,  # exporting decides every one
            test_set=self.test_set,
        )

    def _exported_text(self) -> str:
        counts = self.counts()
        exported = len(self.episodes())
        episodes = "Episode" if exported == 1 else "Episodes"
        if self.include == "keep":
            return f"{exported} kept {episodes}"
        return f"{exported} {episodes} ({counts.keep} Keep, {len(self.needs_review)} Needs review)"

    def summary(self, out: str) -> str:
        rest = len(self.rejections)
        decided = len(self.episodes()) + rest
        note = f" ({self.unlabelled} of the {decided} not Reference-labelled yet)"
        why = nothing_exported(self.counts(), self.include, self.ran)
        return (
            f"{self._exported_text()}, and the Reasons for {rest} not kept"
            f"{note if self.unlabelled else ''}, to {out}{f'. {why}' if why else ''}"
        )


def test_set_ids(ctx: AppContext) -> set[str]:
    return set(ctx.sets.get("test").episode_ids)


def decided_episodes(ctx: AppContext) -> list[Episode]:
    """Every Episode the export decides on: all those outside the Test set."""
    test_set = test_set_ids(ctx)
    return [e for e in ctx.episodes.list() if e.id not in test_set]


def has_run(ctx: AppContext) -> bool:
    return ctx.rubrics.latest().origin == "run"


def _exports(decision: str, include: Include) -> bool:
    return decision == "keep" or (decision == "needs_review" and include == "keep_and_review")


def export_plan(ctx: AppContext, include: Include = "keep") -> ExportPlan:
    episodes = decided_episodes(ctx)
    version, triages = scored(ctx, episodes)
    kept: defaultdict[str, list[int]] = defaultdict(list)
    rejections: list[Rejection] = []
    needs_review: set[str] = set()
    for episode, triage in zip(episodes, triages, strict=True):
        if _exports(triage.decision, include):
            kept[episode.source].append(episode.index)
            if triage.decision == "needs_review":
                needs_review.add(episode.id)
        elif triage.decision != "keep":
            rejections.append(
                Rejection(
                    episode_id=episode.id,
                    source_index=episode.index,
                    decision=triage.decision,
                    reason=plain_reason(triage),
                )
            )
    labelled = revealed_ids(ctx)
    return ExportPlan(
        kept={source: sorted(i) for source, i in kept.items()},
        rejections=rejections,
        unlabelled=sum(e.id not in labelled for e in episodes),
        test_set=len(ctx.episodes.list()) - len(episodes),
        rubric_version=version.version,
        s=ctx.calibrations.s_for(version.version),
        include=include,
        needs_review=frozenset(needs_review),
        ran=has_run(ctx),
    )
