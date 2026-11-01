"""The Review queue, scored like every other read: a review label recomputes the Triage decision,
so an Episode it decides drops out on the next read. Test set Episodes never enter it, so no
review label lands on an Episode held out for reported numbers."""

from winnow.core.context import AppContext
from winnow.episodes.models import Episode
from winnow.review.models import ReviewItem, ReviewQueue, UnsurePhrase
from winnow.triage.models import EpisodeTriage
from winnow.triage.reason import signal_text, undecided
from winnow.triage.service import plain_reason, scored


def review_queue(ctx: AppContext, episodes: list[Episode]) -> ReviewQueue:
    test = set(ctx.sets.get("test").episode_ids)
    version, triages = scored(ctx, [e for e in episodes if e.id not in test])
    waiting = [t for t in triages if t.decision == "needs_review"]
    # Scoring found each in-force label by the Phrase it's on, so a label on a Phrase the Rubric no
    # longer has (detached by an edit, kept in history) is on no Phrase here and isn't counted.
    reviewed = [
        t
        for t in triages
        if t.decision != "needs_review"
        and any(p.label is not None and p.label.source == "review" for p in t.phrases)
    ]
    return ReviewQueue(
        rubric_version=version.version,
        reviewed=len(reviewed),
        # sorted() is stable: equally confident Episodes keep the Dataset's order.
        items=[review_item(t) for t in sorted(waiting, key=lambda t: t.confidence)],
    )


def review_item(triage: EpisodeTriage) -> ReviewItem:
    """What a reviewer is asked about one Episode: its hard Phrases Winnow couldn't decide."""
    return ReviewItem(
        episode_id=triage.episode_id,
        confidence=triage.confidence,
        reason=plain_reason(triage),
        unsure=[
            UnsurePhrase(
                phrase=p.phrase,
                signals=list(
                    dict.fromkeys(signal_text(r) for r in undecided(triage.criteria, p.phrase))
                ),
            )
            for p in triage.phrases
            if p.hard and p.status == "unsure"
        ],
    )
