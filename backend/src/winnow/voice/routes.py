import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from winnow.core.context import AppContext, get_context
from winnow.reference_labels.gate import HIDDEN_UNTIL_LABELLED, RevealedEpisode
from winnow.voice.models import VoiceTurn
from winnow.voice.service import MetaUnavailableError, transcribe_turn

router = APIRouter(tags=["voice"])

Context = Annotated[AppContext, Depends(get_context)]


@router.post(
    "/episodes/{episode_id}/voice",
    responses={
        **HIDDEN_UNTIL_LABELLED,
        422: {"description": "The audio isn't mono 16-bit PCM WAV at 16 or 24 kHz"},
        502: {
            "description": "Voice Transcribe or Spark failed, or Spark's answer couldn't be read"
        },
        503: {"description": "The Meta API isn't configured"},
    },
)
async def post_voice(
    episode: RevealedEpisode,
    ctx: Context,
    audio: UploadFile,
    t: Annotated[float, Form(ge=0)],
) -> VoiceTurn:
    """One push-to-talk turn on the Review page, `t` the playhead at its onset: transcribed, then
    mapped by one Spark call onto the Episode's unsure hard Phrases as pass or fail. Saves
    nothing: each chip the reviewer confirms is posted as a `review` label."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "turn.wav"
        wav.write_bytes(await audio.read())
        try:
            return await transcribe_turn(ctx, episode, wav, t)
        except MetaUnavailableError as error:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        except RuntimeError as error:  # the Meta API failed, or its answer couldn't be read
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Voice failed: {error}") from error
