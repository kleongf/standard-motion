"""Where Phrases sit in their Description, checked by code rather than trusted from Spark, and
which meaningful words no Phrase covers."""

import re
from collections.abc import Sequence

from pydantic import BaseModel

# Words that carry no requirement on their own, so leaving one outside every Phrase is fine.
FILLER = frozenset(
    (
        *("a", "an", "the", "and", "or", "but", "nor", "so", "yet", "of", "in", "on", "at"),
        *("to", "for", "from", "by", "with", "into", "onto", "than", "then", "it", "its"),
        *("is", "are", "be", "been", "was", "were", "this", "that", "these", "those", "as"),
        *("also", "very", "just", "each", "every", "any", "all"),
    )
)
# Words, keeping hyphens and apostrophes inside them: "pick-and-place", "doesn't".
WORD = re.compile("[A-Za-z0-9]+(?:['\u2019-][A-Za-z0-9]+)*")


class TextRange(BaseModel):
    start: int  # in characters
    end: int
    text: str


def locate(description: str, text: str, taken: Sequence[tuple[int, int]]) -> tuple[int, int]:
    """The span of `text` in `description`: its first occurrence that overlaps no span already
    `taken`. Raises ValueError when it isn't an exact substring, or every occurrence overlaps."""
    if not text.strip():
        raise ValueError("a Phrase can't be empty")
    start = description.find(text)
    if start < 0:
        raise ValueError(f"{text!r} isn't an exact substring of the Description")
    while start >= 0:
        end = start + len(text)
        if not any(start < e and s < end for s, e in taken):
            return start, end
        start = description.find(text, start + 1)
    raise ValueError(f"{text!r} overlaps another Phrase")


def uncovered_words(description: str, spans: Sequence[tuple[int, int]]) -> list[TextRange]:
    return [
        TextRange(start=m.start(), end=m.end(), text=m.group())
        for m in WORD.finditer(description)
        if m.group().lower() not in FILLER
        and not any(s <= m.start() and m.end() <= e for s, e in spans)
    ]
