import asyncio
from pathlib import Path

import pytest

from tests.meta.fakes import FakeTime, FakeTransport, MakeClient
from winnow.meta.client import IncompleteReplyError
from winnow.meta.costs import BudgetExceededError
from winnow.meta.limits import Limit
from winnow.meta.models import SamRequest, SparkCall, SparkRequest, Text, Video
from winnow.meta.pricing import SPARK_CONTRIBUTOR
from winnow.meta.transport import FileGoneError, Reply, TransientError

SCHEMA: dict[str, object] = {"type": "object"}


def ask(question: str = "Is the remote on the cushion?", sample: int = 0) -> SparkRequest:
    return SparkRequest(SPARK_CONTRIBUTOR, (Text(question),), SCHEMA, "test", sample=sample)


def test_repeated_request_is_served_from_the_cache_at_no_cost(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    client = make_client()

    first = asyncio.run(client.spark(ask()))
    second = asyncio.run(client.spark(ask()))

    assert len(transport.calls) == 1
    assert (first.cached, second.cached) == (False, True)
    assert second.text == first.text
    assert second.usd == 0.0
    assert client.costs.spent_usd() == first.usd


def track(video: Path) -> SamRequest:
    return SamRequest(video, "remote control", frames=107, purpose="test")


def test_new_file_content_at_the_same_path_is_a_cache_miss(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    client = make_client()
    clip = tmp_path / "wrist.mp4"
    clip.write_bytes(b"first encoding")
    asyncio.run(client.sam_track(track(clip)))
    asyncio.run(client.sam_track(track(clip)))

    clip.write_bytes(b"second encoding")
    again = asyncio.run(client.sam_track(track(clip)))

    assert len(transport.calls) == 2
    assert not again.cached
    assert len(transport.uploads) == 2  # each distinct content is uploaded once


def test_identical_requests_in_flight_together_share_one_call(
    make_client: MakeClient, transport: FakeTransport
):
    client = make_client()

    async def both() -> tuple[SparkCall, SparkCall]:
        return await asyncio.gather(client.spark(ask()), client.spark(ask()))

    first, second = asyncio.run(both())

    assert len(transport.calls) == 1
    assert sorted([first.cached, second.cached]) == [False, True]
    assert client.costs.spent_usd() == first.usd + second.usd


def test_requests_in_flight_together_upload_their_shared_clip_once(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    client = make_client()
    clip = tmp_path / "placement.mp4"
    clip.write_bytes(b"one encoding")

    def about(question: str) -> SparkRequest:
        return SparkRequest(SPARK_CONTRIBUTOR, (Text(question), Video(clip)), SCHEMA, "test")

    async def three() -> list[SparkCall]:
        questions = ("On the target?", "Resting on the target?", "Placed on the target?")
        return await asyncio.gather(*(client.spark(about(q)) for q in questions))

    asyncio.run(three())

    assert len(transport.calls) == 3
    assert len(transport.uploads) == 1


def test_calls_in_flight_count_against_the_budget_before_they_settle(
    make_client: MakeClient, transport: FakeTransport
):
    # Each call is estimated at $0.0009 (1,000 tokens in, up to 4,000 out), so one fits
    # in a $0.0015 budget and two don't, even though nothing has been spent yet.
    client = make_client(budget_usd=0.0015)
    transport.gate = asyncio.Event()

    async def two_at_once() -> tuple[SparkCall | BaseException, ...]:
        first = asyncio.ensure_future(client.spark(ask("first?")))
        second = asyncio.ensure_future(client.spark(ask("second?")))
        await asyncio.sleep(0.01)
        assert transport.gate is not None
        transport.gate.set()
        return tuple(await asyncio.gather(first, second, return_exceptions=True))

    first, second = asyncio.run(two_at_once())

    assert isinstance(first, SparkCall)
    assert isinstance(second, BudgetExceededError)
    assert len(transport.calls) == 1


def test_a_transient_error_is_retried_after_a_backoff(
    make_client: MakeClient, transport: FakeTransport, fake_time: FakeTime
):
    transport.script = [TransientError("429 Too Many Requests")]

    answer = asyncio.run(make_client().spark(ask()))

    assert answer.text == transport.reply.text
    assert len(transport.calls) == 2
    assert len(fake_time.slept) == 1 and fake_time.slept[0] > 0


def test_three_transient_errors_in_a_row_give_up(
    make_client: MakeClient, transport: FakeTransport, fake_time: FakeTime
):
    transport.script = [TransientError("503"), TransientError("503"), TransientError("503")]
    client = make_client()

    with pytest.raises(TransientError):
        asyncio.run(client.spark(ask()))

    assert len(transport.calls) == 3
    assert fake_time.slept[1] > fake_time.slept[0]  # the backoff grows
    assert client.costs.spent_usd() == 0.0


def test_calls_in_flight_per_model_are_capped(make_client: MakeClient, transport: FakeTransport):
    client = make_client(limits={SPARK_CONTRIBUTOR: Limit(in_flight=2)})
    transport.gate = asyncio.Event()

    async def five() -> int:
        calls = [asyncio.ensure_future(client.spark(ask(f"q{i}?"))) for i in range(5)]
        await asyncio.sleep(0.01)
        held = transport.in_flight
        assert transport.gate is not None
        transport.gate.set()
        await asyncio.gather(*calls)
        return held

    assert asyncio.run(five()) == 2
    assert transport.max_in_flight == 2
    assert len(transport.calls) == 5


def test_call_starts_are_spaced_to_the_rate_limit(make_client: MakeClient, fake_time: FakeTime):
    client = make_client(limits={SPARK_CONTRIBUTOR: Limit(in_flight=10, per_minute=60)})

    async def three() -> None:
        await asyncio.gather(*(client.spark(ask(f"q{i}?")) for i in range(3)))

    asyncio.run(three())

    assert sum(fake_time.slept) == pytest.approx(2.0)  # starts at 0 s, 1 s and 2 s


def test_a_file_the_server_lost_is_uploaded_again(
    make_client: MakeClient, transport: FakeTransport, tmp_path: Path
):
    client = make_client()
    clip = tmp_path / "exterior.mp4"
    clip.write_bytes(b"clip")

    def about(question: str) -> SparkRequest:
        return SparkRequest(SPARK_CONTRIBUTOR, (Text(question), Video(clip)), SCHEMA, "test")

    asyncio.run(client.spark(about("Did it spill?")))
    transport.script = [FileGoneError("file-1 not found")]
    answer = asyncio.run(client.spark(about("Is it upright?")))

    assert not answer.cached
    assert len(transport.uploads) == 2
    assert transport.calls[-1][1][1] == {"type": "input_video", "file_id": "file-2"}


def test_a_reply_cut_off_by_the_token_cap_is_paid_for_but_not_cached(
    make_client: MakeClient, transport: FakeTransport
):
    client = make_client()
    transport.script = [Reply("", {"output_tokens": 4000}, incomplete="max_output_tokens")]

    with pytest.raises(IncompleteReplyError, match="max_output_tokens"):
        asyncio.run(client.spark(ask()))
    again = asyncio.run(client.spark(ask()))

    assert len(transport.calls) == 2  # the cut-off reply wasn't served from the cache
    assert not again.cached
    assert client.costs.spent_usd() > again.usd  # the first call still cost money
