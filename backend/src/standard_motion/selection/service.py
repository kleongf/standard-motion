import asyncio
import random
from collections.abc import Mapping
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from standard_motion.episodes.droid101 import Droid101, EpisodeMeta
from standard_motion.episodes.store import episode_id
from standard_motion.jobs.models import Step, WorkItem
from standard_motion.meta.client import MetaClient
from standard_motion.meta.models import Effort, SparkRequest, Text
from standard_motion.meta.models import Image as ImagePart
from standard_motion.meta.pricing import SPARK_CONTRIBUTOR
from standard_motion.selection.models import SelectionAnswer
from standard_motion.selection.store import Sampled, SelectionStore

FAILURE_SHARE = 0.8  # the Test set needs description failures; flagged failures hold most
TILES = 4
# A yes/no reading of a picture: low effort, and room for the reasoning (at medium effort and
# the default 4,000-token cap, a third of the real calls stopped before answering).
EFFORT: Effort = "low"
MAX_OUTPUT_TOKENS = 8000

PROMPT = (
    "This contact sheet shows one robot recording: the top row is {tiles} frames from one "
    "exterior camera and the bottom row the same moments from a second one, in time order from "
    "left to right. {task}Is the robot doing a pick-and-place task: picking up one object and "
    "putting it in or on a target place? If so, name the object and the target in a few words "
    "each, the way a person would to find them in the picture. Answer only from what you see."
)
SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["pick_and_place", "object", "target"],
    "properties": {
        "pick_and_place": {"type": "boolean"},
        "object": {"type": ["string", "null"]},
        "target": {"type": ["string", "null"]},
    },
}


def sample_indices(episodes: list[EpisodeMeta], size: int, seed: int) -> list[int]:
    """A fixed-seed sample, mostly of Episodes flagged failed; the same seed, the same sample."""
    ordered = sorted(episodes, key=lambda e: e.index)
    failures = [e.index for e in ordered if not e.flagged_success]
    successes = [e.index for e in ordered if e.flagged_success]
    rng = random.Random(seed)
    from_failures = min(round(size * FAILURE_SHARE), len(failures))
    from_successes = min(size - from_failures, len(successes))
    return sorted(rng.sample(failures, from_failures) + rng.sample(successes, from_successes))


def sheet_path(data_dir: Path, source: str, index: int) -> Path:
    return data_dir / "selection" / source / f"{index:06d}.jpg"


def write_sheet(source: Droid101, index: int, out: Path) -> None:
    rows: list[Image.Image] = []
    for camera in ("exterior_image_1_left", "exterior_image_2_left"):
        tiles = out.with_name(f"{out.stem}.{camera}.jpg")
        source.write_tiles(index, camera, TILES, tiles)
        with Image.open(tiles) as image:
            rows.append(image.copy())
        tiles.unlink()
    sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows)))
    sheet.paste(rows[0], (0, 0))
    sheet.paste(rows[1], (0, rows[0].height))
    sheet.save(out, quality=85)


async def select_episode(
    meta: MetaClient, store: SelectionStore, source: Droid101, data_dir: Path, index: int,
    seed: int,
) -> str | None:  # fmt: skip
    eid = episode_id(source.name, index)
    if store.has_answer(eid):
        return "already read"
    sheet = sheet_path(data_dir, source.name, index)
    if not sheet.exists():
        sheet.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(write_sheet, source, index, sheet)
    task = source.meta(index).task
    prompt = PROMPT.format(
        tiles=TILES, task=f'The recorded task text is "{task}". ' if task else ""
    )
    request = SparkRequest(
        SPARK_CONTRIBUTOR,
        (Text(prompt), ImagePart(sheet)),
        SCHEMA,
        f"selection:{eid}",
        effort=EFFORT,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        schema_name="selection",
    )
    answer: SelectionAnswer | None = None
    error: str | None = None
    try:  # any failure still leaves a candidate, showing why, and a re-run asks again
        answer = SelectionAnswer.model_validate_json((await meta.spark(request)).text)
    except ValidationError as invalid:
        error = f"malformed answer: {invalid.errors()[0]['msg']}"
    except Exception as failed:
        error = str(failed)
    store.save_answer(Sampled(eid, source.name, index, seed, task), answer, error)
    if error:
        raise RuntimeError(error)
    return None


def select_step(meta: MetaClient, store: SelectionStore, source: Droid101, data_dir: Path) -> Step:
    async def step(args: Mapping[str, object]) -> str | None:
        index, seed = int(str(args["index"])), int(str(args["seed"]))
        return await select_episode(meta, store, source, data_dir, index, seed)

    return step


def selection_items(source: str, indices: list[int], seed: int) -> list[WorkItem]:
    return [WorkItem("select", {"index": i, "seed": seed}, episode_id(source, i)) for i in indices]
