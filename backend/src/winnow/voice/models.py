"""Voice labeling on the Review page: what one push-to-talk turn says about an Episode. Voice is
only the input mode: a chip the reviewer confirms saves as an ordinary `review` label."""

from typing import Literal

from pydantic import BaseModel


class VoiceChip(BaseModel):
    """One unsure Phrase the reviewer's words decide, to confirm or discard."""

    phrase: str
    value: Literal["pass", "fail"]
    quote: str  # the reviewer's words that decide it


class VoiceTurn(BaseModel):
    transcript: str
    # The playhead at the turn's onset, in seconds: Voice Transcribe has no word timestamps, so
    # this is every chip's moment.
    t: float
    chips: list[VoiceChip]  # only the Episode's unsure hard Phrases, in Spark's order
