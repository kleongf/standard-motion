"""The `reason` step: Spark writes one Episode's Reason from its template triage as it stands
now, stored under that triage's key."""

from collections.abc import Mapping

from winnow.core.context import AppContext
from winnow.jobs.models import Step
from winnow.meta.client import MetaClient
from winnow.triage.service import template_triages
from winnow.triage.spark_reason import reason_key, write_reason


def reason_step(meta: MetaClient, ctx: AppContext) -> Step:
    async def step(args: Mapping[str, object]) -> str | None:
        episode = ctx.episodes.get(str(args["episode_id"]))
        if episode is None:
            raise LookupError(f"No Episode {args['episode_id']}")
        version, [triage] = template_triages(ctx, [episode])
        if triage.decision == "keep":
            return "kept: the template Reason stays"
        key = reason_key(version.version, triage)
        if ctx.reasons.get(episode.id, key) is not None:
            return "already written"
        ctx.reasons.put(episode.id, key, await write_reason(meta, triage, episode.id))
        return None

    return step
