"""The `baseline` step: Spark alone on one Episode, 3 samples plus the FailBench check."""

import asyncio
from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from standard_motion.baseline.models import BaselineAnswer, FailBenchAnswer
from standard_motion.baseline.prompts import (
    FAILBENCH_SCHEMA,
    FROZEN,
    Description,
    baseline_prompt,
    baseline_schema,
    failbench_prompt,
)
from standard_motion.baseline.store import SAMPLES, BaselineStore
from standard_motion.episodes.models import Episode
from standard_motion.episodes.store import EpisodeStore, clip_path
from standard_motion.jobs.models import Step, WorkItem
from standard_motion.meta.client import MetaClient
from standard_motion.meta.models import SparkCall, SparkRequest, Text, Video
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR

MAX_OUTPUT_TOKENS = 8000  # effort `high` reasons at length; Day 1 used up to ~3,400
SKIPPED_NO_INSTRUCTION = "skipped: no instruction; it runs once one is written"


def _parse[T: BaseModel](
    result: SparkCall | BaseException, model: type[T]
) -> tuple[T | None, str | None]:
    if isinstance(result, BaseException):
        return None, f"{type(result).__name__}: {result}"
    try:
        return model.model_validate_json(result.text), None
    except ValidationError as error:
        return None, f"malformed answer: {error.errors()[0]['msg']}"


def _requests(
    episode: Episode, videos: tuple[Video, ...], description: Description
) -> tuple[list[SparkRequest], SparkRequest]:
    def request(prompt: str, schema: Mapping[str, object], name: str, sample: int) -> SparkRequest:
        return SparkRequest(
            SPARK_CONTRIBUTOR,
            (Text(prompt), *videos),
            schema,
            f"baseline:{episode.id}",
            effort="high",
            max_output_tokens=MAX_OUTPUT_TOKENS,
            sample=sample,
            schema_name=name,
        )

    prompt = baseline_prompt(description, episode.instruction)
    schema = baseline_schema(description)
    samples = [request(prompt, schema, "baseline", i) for i in range(SAMPLES)]
    failbench = request(failbench_prompt(episode.instruction), FAILBENCH_SCHEMA, "failbench", 0)
    return samples, failbench


async def run_baseline(
    meta: MetaClient,
    store: BaselineStore,
    episodes: EpisodeStore,
    episode: Episode,
    description: Description = FROZEN,
) -> str | None:
    folder = episodes.episode_folder(episode)
    videos = tuple(Video(clip_path(folder, camera)) for camera in episode.cameras)
    samples, failbench = _requests(episode, videos, description)
    results = await asyncio.gather(
        *(meta.spark(r) for r in [*samples, failbench]), return_exceptions=True
    )
    errors: list[str] = []
    for i, result in enumerate(results[:SAMPLES]):
        answer, error = _parse(result, BaselineAnswer)
        store.save_sample(episode.id, description.text, i, answer, error)
        errors += [error] if error else []
    answer, error = _parse(results[SAMPLES], FailBenchAnswer)
    store.save_failbench(episode.id, answer, error)
    errors += [error] if error else []
    if len(errors) == len(results):
        raise RuntimeError(f"every answer failed; first: {errors[0]}")
    return f"{len(errors)} of {len(results)} answers failed" if errors else None


def baseline_step(meta: MetaClient, store: BaselineStore, episodes: EpisodeStore) -> Step:
    async def step(args: Mapping[str, object]) -> str | None:
        episode = episodes.get(str(args["episode_id"]))
        if episode is None:
            raise LookupError(f"No Episode {args['episode_id']}")
        if episode.instruction is None:
            # Judged without its task, Spark alone would be scored on a different question.
            return SKIPPED_NO_INSTRUCTION
        return await run_baseline(meta, store, episodes, episode)

    return step


def unanswered_items(store: BaselineStore, episodes: list[Episode]) -> list[WorkItem]:
    """A `baseline` item for each Episode with an instruction that lacks an answer (an interrupted
    run, or one skipped before its instruction was written). Answers already in are cached."""

    def complete(episode: Episode) -> bool:
        baseline = store.answers(episode.id, FROZEN.text)
        answered = [s for s in baseline.samples if s.answer is not None]
        failbench = baseline.failbench is not None and baseline.failbench.answer is not None
        return len(answered) == SAMPLES and failbench

    return [
        WorkItem("baseline", {"episode_id": e.id}, e.id)
        for e in episodes
        if e.instruction is not None and not complete(e)
    ]
