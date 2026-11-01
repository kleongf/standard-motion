"""What an export holds: every Episode outside the Test set, by its Triage decision under the
latest Rubric version. A Reference label only measures Winnow, so it never gates the export;
exporting shows the decisions of Episodes not labelled yet, which the scope counts first so the
UI can warn before it runs."""

from collections import defaultdict
from dataclasses import dataclass

from winnow.core.context import AppContext
from winnow.episodes.models import Episode
from winnow.export.models import ExportScope, Rejection
from winnow.reference_labels.gate import revealed_ids
from winnow.triage.service import plain_reason, scored


@dataclass(frozen=True)
class ExportPlan:
    kept: dict[str, list[int]]  # source -> its kept Episodes' indices, ascending
    rejections: list[Rejection]
    unlabelled: int  # of the Episodes decided, those without a Reference label

    def summary(self, out: str) -> str:
        kept = sum(len(indices) for indices in self.kept.values())
        episodes = "Episode" if kept == 1 else "Episodes"
        rest = len(self.rejections)
        note = f" ({self.unlabelled} of the {kept + rest} not Reference-labelled yet)"
        return (
            f"{kept} kept {episodes}, and the Reasons for {rest} not kept"
            f"{note if self.unlabelled else ''}, to {out}"
        )


def _decided(ctx: AppContext) -> list[Episode]:
    """Every Episode the export decides on: all those outside the Test set."""
    test_set = set(ctx.sets.get("test").episode_ids)
    return [e for e in ctx.episodes.list() if e.id not in test_set]


def export_scope(ctx: AppContext) -> ExportScope:
    """How many Episodes an export decides on and how many have no Reference label, without
    scoring any: counting them reveals no decision."""
    episodes = _decided(ctx)
    labelled = revealed_ids(ctx)
    return ExportScope(
        episodes=len(episodes), unlabelled=sum(e.id not in labelled for e in episodes)
    )


def export_plan(ctx: AppContext) -> ExportPlan:
    episodes = _decided(ctx)
    _, triages = scored(ctx, episodes)
    kept: defaultdict[str, list[int]] = defaultdict(list)
    rejections: list[Rejection] = []
    for episode, triage in zip(episodes, triages, strict=True):
        if triage.decision == "keep":
            kept[episode.source].append(episode.index)
        else:
            rejections.append(
                Rejection(
                    episode_id=episode.id,
                    source_index=episode.index,
                    decision=triage.decision,
                    reason=plain_reason(triage),
                )
            )
    return ExportPlan(
        kept={source: sorted(i) for source, i in kept.items()},
        rejections=rejections,
        unlabelled=export_scope(ctx).unlabelled,
    )
