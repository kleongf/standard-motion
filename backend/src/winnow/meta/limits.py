"""Per-model caps on calls in flight and calls per minute."""

import asyncio
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from winnow.meta.pricing import SAM, SPARK_CONTRIBUTOR, SPARK_STANDARD, VOICE_TRANSCRIBE

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class Limit:
    in_flight: int
    per_minute: float | None = None  # None: the model's rate limit is undocumented


DEFAULT_LIMITS = {
    SPARK_CONTRIBUTOR: Limit(in_flight=50, per_minute=150),
    SPARK_STANDARD: Limit(in_flight=50, per_minute=3000),
    SAM: Limit(in_flight=8),
    # 256 concurrent streams and 16,000 an hour, batch or streamed
    VOICE_TRANSCRIBE: Limit(in_flight=256, per_minute=16_000 / 60),
}
# For scripted and replayed transports, which answer at once and have no rate limit to respect:
# the same caps on calls in flight, with no spacing between starts.
UNPACED_LIMITS = {model: Limit(limit.in_flight) for model, limit in DEFAULT_LIMITS.items()}


class Limiter:
    """Holds a slot for each call in flight, and spaces call starts evenly under the rate."""

    def __init__(
        self, limit: Limit, clock: Clock = time.monotonic, sleep: Sleep = asyncio.sleep
    ) -> None:
        self._slots = asyncio.Semaphore(limit.in_flight)
        self._interval = 60 / limit.per_minute if limit.per_minute else 0.0
        self._next_start = 0.0
        self._clock = clock
        self._sleep = sleep

    @asynccontextmanager
    async def slot(self) -> AsyncGenerator[None]:
        async with self._slots:
            await self._wait_turn()
            yield

    async def _wait_turn(self) -> None:
        if not self._interval:
            return
        now = self._clock()
        start = max(now, self._next_start)
        self._next_start = start + self._interval  # claimed before awaiting, so turns never clash
        if start > now:
            await self._sleep(start - now)
