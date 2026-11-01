"""Defining and freezing sets; the routes and the CLI both come through here."""

from winnow.episodes.store import EpisodeStore
from winnow.sets.models import SET_LABELS, EpisodeSet, SetName
from winnow.sets.protocol import freeze_warnings
from winnow.sets.store import SetStore


class SetError(ValueError):
    pass


class UnknownEpisodesError(SetError):
    """Some ids aren't ingested Episodes."""


class SetConflictError(SetError):
    """The set is frozen, or an Episode is already in the other set."""


class NotInSetError(SetError):
    pass


class FreezeWarningsError(SetError):
    """Freezing would break the protocol; freezing again with force goes ahead anyway."""

    def __init__(self, warnings: list[str]) -> None:
        super().__init__("; ".join(warnings))
        self.warnings = warnings


def _refuse_if_frozen(current: EpisodeSet) -> None:
    if current.frozen_at is not None:
        raise SetConflictError(
            f"The {SET_LABELS[current.name]} was frozen at {current.frozen_at}; "
            "its membership can't change"
        )


def add_episodes(
    sets: SetStore, episodes: EpisodeStore, name: SetName, episode_ids: list[str]
) -> EpisodeSet:
    """Adds them all or none. Adding an Episode already in this set changes nothing."""
    current = sets.get(name)
    _refuse_if_frozen(current)
    wanted = list(dict.fromkeys(episode_ids))
    unknown = [i for i in wanted if episodes.get(i) is None]
    if unknown:
        raise UnknownEpisodesError(f"Not ingested: {', '.join(unknown)}")
    elsewhere: dict[str, SetName] = {i: s for i, s in sets.sets_of(wanted).items() if s != name}
    if elsewhere:
        named = ", ".join(f"{i} ({SET_LABELS[s]})" for i, s in elsewhere.items())
        raise SetConflictError(f"Already in the other set: {named}")
    sets.add(name, [i for i in wanted if i not in current.episode_ids])
    return sets.get(name)


def remove_episode(sets: SetStore, name: SetName, episode_id: str) -> EpisodeSet:
    _refuse_if_frozen(sets.get(name))
    if not sets.remove(name, episode_id):
        raise NotInSetError(f"{episode_id} isn't in the {SET_LABELS[name]}")
    return sets.get(name)


def freeze(sets: SetStore, name: SetName, force: bool = False) -> EpisodeSet:
    """Freezing a frozen set changes nothing and keeps its original timestamp. A set that breaks
    the protocol is refused with the warnings unless forced; an empty set is refused regardless."""
    current = sets.get(name)
    if current.frozen_at is not None:
        return current
    if current.size == 0:
        raise SetError(f"The {SET_LABELS[name]} is empty: add Episodes before freezing it")
    warnings = freeze_warnings(current)
    if warnings and not force:
        raise FreezeWarningsError(warnings)
    sets.freeze(name)
    return sets.get(name)
