"""The instruction's target, in the words SAM's text prompt uses: the last place the object is
put in, on or to ("Put the marker in the pot" -> "pot"). Directions and parts of a place ("to
the left", "the left side of") are not targets; "the first shelf" in "the left side of the
first shelf" is. Deterministic, so the same instruction always prompts SAM the same way."""

import re

PLACING = frozenset(
    {"in", "into", "inside", "on", "onto", "to", "of", "at", "within", "under", "over", "near"}
)
# Words that end a place's name without starting another.
ENDS = frozenset(
    {"and", "then", "from", "out", "off", "with", "for", "by", "while", "until", ",", ".", ";"}
)
LEADING = frozenset({"the", "a", "an", "one", "some", "its", "this", "that", "it", "them"})
# Directions and parts of a place: a phrase made only of these names no target of its own.
NOT_A_PLACE = frozenset(
    {
        *("left", "right", "front", "back", "forward", "forwards", "backward", "backwards"),
        *("middle", "center", "centre", "side", "top", "bottom", "corner", "edge", "row"),
        *("section", "part", "end", "up", "down", "away", "here", "there", "closer"),
        *("first", "second", "third", "last", "far", "upper", "lower"),
    }
)


def _is_place(phrase: list[str]) -> bool:
    return any(word not in NOT_A_PLACE for word in phrase)


def _phrases(words: list[str]) -> list[list[str]]:
    """Each run of words after a placing preposition. "of" carries on a place ("sheet of
    paper") but restarts after a part of one ("the left side of")."""
    phrases: list[list[str]] = []
    current: list[str] | None = None
    for word in words:
        if word == "of" and current and _is_place(current):
            current.append(word)
        elif word in PLACING:
            current = []
            phrases.append(current)
        elif word in ENDS:
            current = None
        elif current is not None and (current or word not in LEADING):
            current.append(word)
    return phrases


def target_words(instruction: str) -> str | None:
    """The target the instruction names, or None if it names no place."""
    words = re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*|[,.;]", instruction.lower())
    for phrase in reversed(_phrases(words)):
        while phrase and phrase[-1] == "of":
            phrase.pop()
        if _is_place(phrase):
            return " ".join(phrase)
    return None
