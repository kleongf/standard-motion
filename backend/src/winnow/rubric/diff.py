"""What a Description edit changed: the draft's Phrases it left alone, and the stretches of new
text compile must ask Spark about.

The two Descriptions are compared word by word (punctuation counts as a word, spacing doesn't).
A Phrase is kept only when no edit falls inside it or adds words at its edges and its text is
still there character for character; every other Phrase the edit touched is asked about again,
with the new words around it. Words added after punctuation at a Phrase's edge (a new sentence
or clause beside it) don't touch it, and are asked about on their own.
"""

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from winnow.rubric.models import DraftPhrase
from winnow.rubric.phrases import FILLER, WORD, TextRange

TOKEN = re.compile(rf"{WORD.pattern}|\S")


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class _Edit:
    old: range  # token positions in the old Description; empty where words were only added
    new: range  # and in the new


@dataclass(frozen=True)
class _Alignment:
    """Both Descriptions' tokens, where each unchanged old token now sits, and the edits."""

    old: str
    new: str
    before: list[_Token]
    after: list[_Token]
    moved: dict[int, int]  # old token position -> new, for unchanged tokens
    edits: list[_Edit]

    def now_at(self, start: int, end: int) -> list[int]:
        """Where the unchanged tokens of the old text at [start, end) now sit."""
        return [self.moved[i] for i in _span(self.before, start, end) if i in self.moved]

    def left_alone(self, start: int, end: int) -> tuple[int, int] | None:
        span, here = _span(self.before, start, end), self.now_at(start, end)
        if not here or any(_touches(e, span, self.after) for e in self.edits):
            return None
        now = (self.after[here[0]].start, self.after[here[-1]].end)
        return now if self.new[now[0] : now[1]] == self.old[start:end] else None


@dataclass(frozen=True)
class DescriptionDiff:
    kept: list[DraftPhrase]  # unchanged, moved to where each now sits
    stretches: list[TextRange]  # the changed text, in Description order
    _alignment: _Alignment = field(repr=False, compare=False)

    def moved(self, start: int, end: int) -> tuple[int, int] | None:
        """Where the old Description's text at [start, end) sits in the new one, when the edit
        left it alone by the rule that keeps a Phrase there; None when it touched it."""
        return self._alignment.left_alone(start, end)


def _tokens(text: str) -> list[_Token]:
    return [_Token(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def _span(tokens: list[_Token], start: int, end: int) -> range:
    """The positions of the tokens inside characters [start, end)."""
    inside = [i for i, t in enumerate(tokens) if start <= t.start and t.end <= end]
    return range(inside[0], inside[-1] + 1) if inside else range(0)


def _is_word(token: _Token) -> bool:
    return WORD.fullmatch(token.text) is not None


def _touches(edit: _Edit, phrase: range, after: list[_Token]) -> bool:
    if edit.old:
        return edit.old.start < phrase.stop and phrase.start < edit.old.stop
    # Text only added: inside the Phrase, or at an edge with no punctuation between them.
    at = edit.old.start
    if at == phrase.stop:
        return _is_word(after[edit.new.start])
    if at == phrase.start:
        return _is_word(after[edit.new.stop - 1])
    return phrase.start < at < phrase.stop


def _meaningful(run: list[int], tokens: list[_Token]) -> bool:
    words = [tokens[i].text for i in run if _is_word(tokens[i])]
    return any(w.lower() not in FILLER for w in words)


def _stretches(changed: set[int], tokens: list[_Token], new: str) -> list[TextRange]:
    """Changed tokens, joined into runs across punctuation; runs with no meaningful word go."""
    runs: list[list[int]] = []
    for i in sorted(changed):
        between = range(runs[-1][-1] + 1, i) if runs else range(0)
        if runs and not any(_is_word(tokens[j]) for j in between):
            runs[-1].append(i)
        else:
            runs.append([i])
    spans = [(tokens[r[0]].start, tokens[r[-1]].end) for r in runs if _meaningful(r, tokens)]
    return [TextRange(start=start, end=end, text=new[start:end]) for start, end in spans]


def diff_description(old: str, phrases: Sequence[DraftPhrase], new: str) -> DescriptionDiff:
    """`phrases` are the draft's, in `old`."""
    before, after = _tokens(old), _tokens(new)
    matcher = difflib.SequenceMatcher(
        None, [t.text for t in before], [t.text for t in after], autojunk=False
    )
    moved: dict[int, int] = {}
    edits: list[_Edit] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            moved |= {i1 + k: j1 + k for k in range(i2 - i1)}
        else:
            edits.append(_Edit(range(i1, i2), range(j1, j2)))
    alignment = _Alignment(old, new, before, after, moved, edits)
    # The words an edit added; punctuation it added at their edges stays out of the stretches.
    changed = {j for edit in edits for j in edit.new if _is_word(after[j])}
    kept: list[DraftPhrase] = []
    for phrase in phrases:
        now = alignment.left_alone(phrase.start, phrase.end)
        if now is None:
            changed.update(alignment.now_at(phrase.start, phrase.end))
        else:
            kept.append(phrase.model_copy(update={"start": now[0], "end": now[1]}))
    return DescriptionDiff(kept, _stretches(changed, after, new), alignment)


def clarify_diff(
    description: str, phrases: Sequence[DraftPhrase], start: int, end: int
) -> DescriptionDiff:
    """The Description unchanged, with only its text at [start, end) to be asked about again, as
    if an edit had replaced it with itself: every Phrase outside it is kept where it is, and any
    text that overlaps it counts as touched."""
    tokens = _tokens(description)
    span = _span(tokens, start, end)
    same = {i: i for i in range(len(tokens))}
    alignment = _Alignment(description, description, tokens, tokens, same, [_Edit(span, span)])
    kept = [p for p in phrases if p.end <= start or end <= p.start]
    stretch = TextRange(start=start, end=end, text=description[start:end])
    return DescriptionDiff(kept, [stretch], alignment)
