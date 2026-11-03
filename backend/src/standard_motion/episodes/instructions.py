"""Instructions for Episodes their source shipped without one (DROID drops them from failures),
made from the object and target Spark named at selection, or written by hand. Scoring, the
Spark-alone baseline and the target box read the instruction from the Episode."""

from dataclasses import dataclass

from standard_motion.episodes.store import EpisodeStore


class InstructionError(ValueError):
    pass


def suggested_instruction(task_object: str | None, task_target: str | None) -> str | None:
    """The Label panel offers the same sentence (`labelDraft.ts`'s `suggestedInstruction`)."""
    if not task_object or not task_target:
        return None
    return f"Put the {task_object} in or on the {task_target}"


@dataclass(frozen=True)
class Filled:
    written: list[str]  # Episode ids given an instruction from Spark's names
    left: list[str]  # Episode ids still without one: Spark named no object or target


def fill_instructions(episodes: EpisodeStore) -> Filled:
    """Gives every Episode without an instruction the one Spark's names make; never overwrites."""
    written: list[str] = []
    left: list[str] = []
    for episode in episodes.list():
        if episode.instruction is not None:
            continue
        instruction = suggested_instruction(episode.task_object, episode.task_target)
        if instruction is None:
            left.append(episode.id)
            continue
        episodes.write_instruction(episode.id, instruction)
        written.append(episode.id)
    return Filled(written, left)


def write_instruction(episodes: EpisodeStore, episode_id: str, instruction: str) -> None:
    episode = episodes.get(episode_id)
    if episode is None:
        raise InstructionError(f"No Episode {episode_id}")
    if episode.instruction is not None:
        raise InstructionError(f"{episode_id} already has an instruction: {episode.instruction}")
    if not instruction.strip():
        raise InstructionError("An instruction can't be blank")
    episodes.write_instruction(episode_id, instruction.strip())
