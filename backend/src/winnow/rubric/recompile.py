"""Recompile: after a Description edit, Spark is asked about only the changed text; after the
curator answers an interview question in their own words, about only the text it asked about.

Every Phrase the edit left alone is kept as it was, with its Criteria: their ids, thresholds,
hard/soft and on/off survive, and so do labels, which hang off the Phrase's text. A Criterion
compiled anew takes back the id a Criterion of the same Phrase and primitive had, and otherwise
gets one no Criterion of the draft had. Visual Criteria kept this way ask exactly what they
asked before, so their answers are Meta cache hits.
"""

from collections import defaultdict
from datetime import UTC, datetime

from winnow.criteria.models import Criterion
from winnow.meta.client import MetaClient
from winnow.rubric.compile import (
    Compiled,
    Scope,
    ask_phrases,
    draft_phrases,
    in_phrase_order,
    numbered,
)
from winnow.rubric.diff import DescriptionDiff
from winnow.rubric.models import RubricDraft
from winnow.rubric.prompt import clarify_prompt, recompile_prompt


def _scope(description: str, diff: DescriptionDiff) -> Scope:
    return Scope(description, tuple((p.start, p.end) for p in diff.kept))


async def ask_changes(
    meta: MetaClient, description: str, manifest: str, diff: DescriptionDiff
) -> Compiled:
    """Spark's answer about the changed text of `description`: one call, and its repair turn.
    `diff` must have stretches. It has none, and needs no call, only when the edit touched no
    Phrase and added no meaningful word, such as taking out whole Phrases; a deletion inside a
    Phrase changes that Phrase, which is asked about again."""
    kept, changed = [p.text for p in diff.kept], [s.text for s in diff.stretches]
    prompt = recompile_prompt(description, manifest, kept, changed)
    return await ask_phrases(meta, prompt, _scope(description, diff))


async def ask_clarified(
    meta: MetaClient, description: str, manifest: str, diff: DescriptionDiff, text: str
) -> Compiled:
    """Spark's answer about the one stretch of `diff` (`diff.clarify_diff`), read with the
    curator's own words about it, `text`: one call, and its repair turn."""
    kept, (stretch,) = [p.text for p in diff.kept], diff.stretches
    prompt = clarify_prompt(description, manifest, kept, stretch.text, text)
    return await ask_phrases(meta, prompt, _scope(description, diff))


def recompile_rubric(
    draft: RubricDraft, description: str, diff: DescriptionDiff, compiled: Compiled
) -> RubricDraft:
    """The draft with its Description edited to `description`: `diff` is from the draft's
    Description, and `compiled` is Spark's answer about its stretches (`ask_changes`), or empty
    when there are none. Everything else, such as the kept Criteria's edits, comes from `draft`."""
    scope = _scope(description, diff)
    added, rejected = draft_phrases(compiled, scope)
    phrases = sorted([*diff.kept, *added], key=lambda p: p.start)
    criteria = in_phrase_order(_criteria(draft, diff, compiled), phrases)
    ids = {c.id for c in criteria}
    return draft.model_copy(
        update={
            "description": description,
            "phrases": phrases,
            "criteria": criteria,
            "disabled": [id_ for id_ in draft.disabled if id_ in ids],
            "rejected": rejected,
            "recompiled": diff.stretches,
            "compiled_at": datetime.now(UTC).isoformat(),
        }
    )


def _criteria(draft: RubricDraft, diff: DescriptionDiff, compiled: Compiled) -> list[Criterion]:
    kept_phrases = {p.text for p in diff.kept}
    kept = [c for c in draft.criteria if c.phrase in kept_phrases]
    reuse: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for gone in (c for c in draft.criteria if c.phrase not in kept_phrases):
        reuse[(gone.phrase, gone.primitive)].append(gone.id)
    new = [c for checked in compiled.accepted for c in checked.criteria]
    return [*kept, *numbered(new, {c.id for c in draft.criteria}, reuse)]
