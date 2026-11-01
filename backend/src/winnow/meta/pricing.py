"""Published Meta Model API prices (dev.meta.ai pricing page, checked 2026-10-27)."""

from dataclasses import dataclass

SPARK_CONTRIBUTOR = "muse-spark-1.3-contributor"
SPARK_STANDARD = "muse-spark-1.3"
SAM = "sam-3.1"
VOICE_TRANSCRIBE = "muse-voice-transcribe-1.0"

SAM_USD_PER_FRAME = 0.20 / 1000
SAM_MIN_FRAMES = 50

VOICE_USD_PER_HOUR = 0.18  # streaming and batch alike


@dataclass(frozen=True)
class TokenPrice:
    input_per_m: float
    cached_input_per_m: float
    output_per_m: float


SPARK_PRICES = {
    SPARK_CONTRIBUTOR: TokenPrice(input_per_m=0.10, cached_input_per_m=0.002, output_per_m=0.20),
    SPARK_STANDARD: TokenPrice(input_per_m=1.25, cached_input_per_m=0.15, output_per_m=4.25),
}


def sam_cost(frames: int) -> float:
    return max(frames, SAM_MIN_FRAMES) * SAM_USD_PER_FRAME


def spark_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    price = SPARK_PRICES[model]
    fresh = input_tokens - cached_tokens
    return (
        fresh * price.input_per_m
        + cached_tokens * price.cached_input_per_m
        + output_tokens * price.output_per_m
    ) / 1_000_000


def transcribe_cost(audio_ms: int) -> float:
    return audio_ms / 3_600_000 * VOICE_USD_PER_HOUR
