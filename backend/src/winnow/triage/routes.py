from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from winnow.core.context import AppContext, get_context
from winnow.reference_labels.gate import (
    HIDDEN_UNTIL_LABELLED,
    RevealedEpisode,
    revealed_episodes,
)
from winnow.triage.models import EpisodeTriage, ReasonsStarted, TriageList
from winnow.triage.reason_service import MetaUnavailableError, write_reasons
from winnow.triage.service import episode_triage, triage_list

router = APIRouter(tags=["triage"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/triage")
async def list_triage(ctx: Context) -> TriageList:
    """The Triage decision and Reason of every Episode with a Reference label, for the Episodes
    table; the rest await theirs."""
    return triage_list(ctx, revealed_episodes(ctx))


@router.get(
    "/episodes/{episode_id}/triage",
    responses=HIDDEN_UNTIL_LABELLED,
)
async def get_triage(episode: RevealedEpisode, ctx: Context) -> EpisodeTriage:
    """One labelled Episode's Criterion results, Phrase results, Triage decision and Reason."""
    return episode_triage(ctx, episode)


@router.post(
    "/reasons",
    status_code=status.HTTP_202_ACCEPTED,
    responses={503: {"description": "The Meta API isn't configured"}},
)
async def post_reasons(ctx: Context) -> ReasonsStarted:
    """Have Spark write the Reason of every Reject and Needs review whose results changed since
    its last one, in the background; each replaces its template Reason once written."""
    try:
        return ReasonsStarted(job_id=write_reasons(ctx))
    except MetaUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
