"""Queueing Spark's Reasons: one work item per Reject and Needs review whose inputs have no Reason
stored yet and that no Reason job is writing already. Queued on request (`POST /api/reasons`,
`winnow reasons`), after a Run, calibrating, accepting a threshold suggestion or saving a review
label, and when a visual job finishes, as each can change an Episode's results."""

from winnow.core.context import AppContext
from winnow.jobs.models import WorkItem
from winnow.triage.service import template_triages
from winnow.triage.spark_reason import reason_key


class MetaUnavailableError(RuntimeError):
    pass


def reason_items(ctx: AppContext) -> list[WorkItem]:
    episodes = ctx.episodes.list()
    version, triages = template_triages(ctx, episodes)
    stored = ctx.reasons.keys()
    # A queued item reads the Episode's triage when it runs, so it writes the Reason as it is then.
    writing = {str(args["episode_id"]) for args in ctx.jobs.in_flight("reason")}
    return [
        WorkItem("reason", {"episode_id": episode.id}, episode.id)
        for episode, triage in zip(episodes, triages, strict=True)
        if triage.decision != "keep"
        and episode.id not in writing
        and (episode.id, reason_key(version.version, triage)) not in stored
    ]


def write_reasons(ctx: AppContext) -> int | None:
    """Queues the Reasons to write; returns the job's id, or None when none is out of date.
    Raises MetaUnavailableError without the Meta API."""
    if ctx.meta is None:
        raise MetaUnavailableError("Spark's Reasons need the Meta API: set MODEL_API_KEY in .env")
    items = reason_items(ctx)
    return ctx.runner.submit("reason", items) if items else None


def queue_reasons(ctx: AppContext) -> int | None:
    """`write_reasons`, or nothing without the Meta API: the template Reasons stay."""
    return None if ctx.meta is None else write_reasons(ctx)
