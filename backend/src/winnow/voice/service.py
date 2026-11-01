"""One push-to-talk turn: Voice Transcribe hears it, then one Spark call maps the transcript onto
the Episode's unsure hard Phrases. Nothing is saved until the reviewer confirms a chip."""

from pathlib import Path

from pydantic import BaseModel, ValidationError

from winnow.core.context import AppContext
from winnow.episodes.models import Episode
from winnow.meta.models import SparkRequest, Text, TranscribeRequest
from winnow.meta.pricing import SPARK_CONTRIBUTOR
from winnow.review.service import review_item
from winnow.triage.service import scored
from winnow.voice.models import VoiceChip, VoiceTurn
from winnow.voice.prompt import VOICE_SCHEMA, voice_prompt

MAX_OUTPUT_TOKENS = 2000  # a short list, but low effort still reasons before it
# Straight, curly and angle quotes, in escapes: ruff takes the curly singles for backticks.
QUOTES = "\"'`\u201c\u201d\u2018\u2019\u00ab\u00bb"


class MetaUnavailableError(RuntimeError):
    pass


class VoiceAnswerError(RuntimeError):
    """Spark's mapping couldn't be read."""


class _Answer(BaseModel):
    phrases: list[VoiceChip]


async def transcribe_turn(ctx: AppContext, episode: Episode, wav: Path, t: float) -> VoiceTurn:
    """`t` is the playhead at the turn's onset. Raises ValueError, before any call, for audio
    Voice Transcribe doesn't take (anything but mono 16-bit PCM WAV at 16 or 24 kHz)."""
    if ctx.meta is None:
        raise MetaUnavailableError("Voice labeling needs the Meta API: set MODEL_API_KEY in .env")
    purpose = f"voice:{episode.id}"
    heard = await ctx.meta.transcribe(TranscribeRequest(wav, purpose=purpose))
    transcript = heard.transcript.text
    _, (triage,) = scored(ctx, [episode])
    unsure = [u.phrase for u in review_item(triage).unsure]
    if not transcript or not unsure:
        return VoiceTurn(transcript=transcript, t=t, chips=[])
    request = SparkRequest(
        SPARK_CONTRIBUTOR,
        (Text(voice_prompt(transcript, unsure)),),
        VOICE_SCHEMA,
        purpose,
        effort="low",
        max_output_tokens=MAX_OUTPUT_TOKENS,
        schema_name="voice",
    )
    reply = await ctx.meta.spark(request)
    return VoiceTurn(transcript=transcript, t=t, chips=_chips(reply.text, unsure))


def _chips(answer: str, unsure: list[str]) -> list[VoiceChip]:
    """Spark's mapping, keeping one chip per unsure Phrase, named as listed: a Phrase given in
    another case or in quotes is the same one, and any other Phrase it names is dropped."""
    try:
        marks = _Answer.model_validate_json(answer).phrases
    except ValidationError as error:
        raise VoiceAnswerError(f"Spark's mapping couldn't be read: {error}") from error
    listed = {_key(p): p for p in unsure}
    chips: dict[str, VoiceChip] = {}
    for mark in marks:
        phrase = listed.get(_key(mark.phrase))
        if phrase is not None and phrase not in chips:
            chips[phrase] = mark.model_copy(update={"phrase": phrase})
    return list(chips.values())


def _key(phrase: str) -> str:
    return " ".join(phrase.strip().strip(QUOTES).split()).casefold()
