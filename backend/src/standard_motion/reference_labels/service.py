import sqlite3
from datetime import UTC, datetime

from standard_motion.baseline.prompts import FROZEN
from standard_motion.boxes.service import queue_box_work
from standard_motion.core.context import AppContext
from standard_motion.episodes.models import Episode
from standard_motion.jobs.models import WorkItem
from standard_motion.reference_labels.models import ReferenceLabel, ReferenceLabelDraw


class InvalidLabelError(ValueError):
    pass


class LabelConflictError(ValueError):
    pass


def check_label(draw: ReferenceLabelDraw, episode: Episode) -> None:
    if [p.phrase for p in draw.phrases] != list(FROZEN.phrases):
        raise InvalidLabelError("Judge each Phrase of the frozen Description once, in order")
    for p in draw.phrases:
        if p.interval is not None and p.interval.end_s > episode.duration_s:
            raise InvalidLabelError(
                f"“{p.phrase}” fails past the end of the {episode.duration_s:.1f} s Episode"
            )


def _instruction(draw: ReferenceLabelDraw, episode: Episode) -> str:
    if episode.instruction:
        return episode.instruction
    written = (draw.instruction or "").strip()
    if not written:
        raise InvalidLabelError("This Episode has no instruction: write the task it attempts")
    return written


def save_label(ctx: AppContext, episode: Episode, draw: ReferenceLabelDraw) -> ReferenceLabel:
    check_label(draw, episode)
    if draw.relabel and not ctx.reference_labels.has(episode.id, relabel=False):
        raise LabelConflictError("Relabel an Episode only after its first-pass label")
    instruction = _instruction(draw, episode)
    label = ReferenceLabel(
        episode_id=episode.id,
        relabel=draw.relabel,
        description=FROZEN.text,
        phrases=draw.phrases,
        instruction=instruction,
        elapsed_s=draw.elapsed_s,
        labelled_at=datetime.now(UTC).isoformat(),
    )
    try:
        ctx.reference_labels.add(label)
    except sqlite3.IntegrityError as error:
        which = "relabelled" if draw.relabel else "labelled"
        raise LabelConflictError(f"{episode.id} is already {which}; labels never change") from error
    if episode.instruction is None:
        # Scoring and the baseline read the Episode, never its Reference label.
        ctx.episodes.write_instruction(episode.id, instruction)
        queue_instruction_work(ctx, episode.id)
    return label


def queue_instruction_work(ctx: AppContext, episode_id: str) -> None:
    """What a newly written instruction feeds: the Spark-alone baseline, which ingest skipped
    without one, and the target box, which may now have a target to look for. Nothing without
    Meta to run them."""
    if ctx.meta is None:
        return
    ctx.runner.submit("baseline", [WorkItem("baseline", {"episode_id": episode_id}, episode_id)])
    queue_box_work(ctx, episode_id, ("target_box",))
