"""What callers ask the Meta API for, and what comes back."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Meta extends the Responses API with content types the OpenAI SDK doesn't type (input_video).
MetaContent = list[dict[str, object]]
Effort = Literal["minimal", "low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Video:
    """Uploaded once per distinct file content, then referenced by file id."""

    path: Path


@dataclass(frozen=True)
class Image:
    """Sent inline as a data URL."""

    path: Path


@dataclass(frozen=True)
class Audio:
    """A WAV clip, keyed by content; Voice Transcribe takes the file itself, not a content part."""

    path: Path


Part = Text | Video | Image | Audio


def _sam_metadata() -> dict[str, str]:
    return {"include_confidence": "true", "propagation_direction": "forward"}


@dataclass(frozen=True)
class SamRequest:
    """Track through one video from a noun phrase or a box/point prompt."""

    video: Path
    prompt: str
    frames: int  # the clip's frame count, which bounds the cost estimate
    purpose: str  # for the cost log, not part of the cache key
    metadata: Mapping[str, str] = field(default_factory=_sam_metadata)


@dataclass(frozen=True)
class SparkRequest:
    model: str
    parts: tuple[Part, ...]
    schema: Mapping[str, object]
    purpose: str  # for the cost log, not part of the cache key
    effort: Effort = "medium"
    max_output_tokens: int = 4000
    sample: int = 0  # repeated samples of one prompt cache separately
    schema_name: str = "answer"  # names the structured-output format


@dataclass(frozen=True)
class TranscribeRequest:
    """One push-to-talk turn: mono 16-bit PCM WAV at 16 kHz."""

    audio: Path
    purpose: str  # for the cost log, not part of the cache key
    mode: Literal["PUSH_TO_TALK", "ENDPOINTING"] = "PUSH_TO_TALK"


@dataclass(frozen=True)
class Turn:
    text: str
    start_ms: int  # from the start of the clip
    end_ms: int


@dataclass(frozen=True)
class Transcript:
    turns: tuple[Turn, ...]

    @property
    def text(self) -> str:
        return " ".join(t.text.strip() for t in self.turns if t.text.strip())


@dataclass(frozen=True)
class SamCall:
    text: str
    frames_processed: int
    usd: float  # what this call cost: 0 when served from the cache
    latency_s: float
    cached: bool


@dataclass(frozen=True)
class SparkCall:
    text: str
    input_tokens: int
    output_tokens: int
    usd: float  # what this call cost: 0 when served from the cache
    latency_s: float
    cached: bool


@dataclass(frozen=True)
class TranscribeCall:
    transcript: Transcript
    audio_ms: int
    usd: float  # what this call cost: 0 when served from the cache
    latency_s: float
    cached: bool
