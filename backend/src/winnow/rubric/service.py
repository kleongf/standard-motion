"""The Project's Rubric draft: compiled from a Description, edited directly, previewed on the
anchor pool, and frozen by Run."""

from winnow.core.context import AppContext
from winnow.criteria.models import RubricSettings
from winnow.interview.carry import carried
from winnow.meta.client import MetaClient
from winnow.rubric.anchor_pool import anchor_episodes
from winnow.rubric.compile import Compiled, compile_rubric
from winnow.rubric.diff import DescriptionDiff, clarify_diff, diff_description
from winnow.rubric.edits import apply_edit
from winnow.rubric.manifest import capabilities_manifest
from winnow.rubric.models import AnchorPreview, DraftEdit, RubricDraft, RubricVersion
from winnow.rubric.preview import anchor_labels, anchor_preview, revealed_anchor_facts
from winnow.rubric.recompile import ask_changes, ask_clarified, recompile_rubric
from winnow.rubric.seed import SEEDED_SETTINGS
from winnow.triage.reason_service import queue_reasons


class MetaUnavailableError(RuntimeError):
    pass


class NoDraftError(LookupError):
    pass


class DraftChangedError(Exception):
    """The draft's Description changed while Spark read an edit of it."""


_CLARIFY_CHANGED = "The draft changed while Spark read your answer: answer again"


async def compile_draft(ctx: AppContext, description: str, fresh: bool = False) -> RubricDraft:
    """Compiles `description` against the anchor pool and saves it as the draft.

    When it edits the draft's Description, only the changed text is compiled (`recompile`): the
    unchanged Phrases keep their Criteria, edits and labels. Otherwise, or when `fresh`, the
    whole Description is, and the Rubric settings start at their assumed defaults, for the
    curator to confirm. Compiling an unchanged Description again starts it afresh, at no cost
    when the Meta cache has seen it.

    A recompile applies Spark's answer to the draft as it is once Spark answers, so direct edits
    and interview answers made meanwhile survive; it raises DraftChangedError, saving nothing,
    when the Description was changed meanwhile. The interview goes on: its answers about text
    the edit left alone carry over to the recompiled draft. A compile afresh starts a new one."""
    draft = ctx.drafts.get()
    if fresh or draft is None or draft.description == description:
        return ctx.drafts.save(await _compile_afresh(ctx, description))
    diff = diff_description(draft.description, draft.phrases, description)
    if not diff.kept:
        return ctx.drafts.save(await _compile_afresh(ctx, description))
    compiled = Compiled([], [])
    if diff.stretches:
        manifest = _manifest(ctx, draft.settings)
        compiled = await ask_changes(_meta(ctx), description, manifest, diff)
    return _save_recompiled(ctx, draft.description, description, diff, compiled)


def _save_recompiled(
    ctx: AppContext, old: str, description: str, diff: DescriptionDiff, compiled: Compiled
) -> RubricDraft:
    """Spark's answer applied to the draft as it is now, saved with the interview answers that
    still hold. `diff` is what Spark was asked about, from `old`; diffing the draft afresh must
    find the same, or the answer no longer fits it."""
    now = current_draft(ctx)
    redo = diff_description(now.description, now.phrases, description)
    if now.description != old or _spans(redo) != _spans(diff):
        raise DraftChangedError(
            "The Description changed while Spark was reading the edit: recompile the changes"
        )
    return _store_recompiled(ctx, now, description, redo, compiled)


async def clarify_draft(
    ctx: AppContext, compiled_at: str, start: int, end: int, text: str
) -> RubricDraft:
    """Recompiles only the draft's text at [start, end), a Phrase or words in no Phrase, with the
    curator's own words about it, `text`, and saves it. Every other Phrase keeps its Criteria,
    edits and labels, and the interview answers that still hold carry over, as for an edit. The
    labels answers about that text left stay too: its text is unchanged, and they say how
    Episodes fare on it.

    Raises DraftChangedError, saving nothing, unless the draft is the one compiled at
    `compiled_at`, before and once Spark answers, with the same Phrases around that text and
    no interview answer added or undone meanwhile (direct edits may come in between)."""
    draft, answered = _clarifying(ctx, compiled_at)
    diff = clarify_diff(draft.description, draft.phrases, start, end)
    manifest = _manifest(ctx, draft.settings)
    compiled = await ask_clarified(_meta(ctx), draft.description, manifest, diff, text)
    now, still = _clarifying(ctx, compiled_at)
    redo = clarify_diff(now.description, now.phrases, start, end)
    if still != answered or _spans(redo) != _spans(diff):
        raise DraftChangedError(_CLARIFY_CHANGED)
    return _store_recompiled(ctx, now, now.description, redo, compiled)


def _clarifying(ctx: AppContext, compiled_at: str) -> tuple[RubricDraft, list[int]]:
    """The draft, if it is still the one compiled at `compiled_at`, and its interview answers'
    ids."""
    draft = current_draft(ctx)
    if draft.compiled_at != compiled_at:
        raise DraftChangedError(_CLARIFY_CHANGED)
    return draft, [a.id for a in ctx.interview.answers(compiled_at)]


def _store_recompiled(
    ctx: AppContext, now: RubricDraft, description: str, diff: DescriptionDiff, compiled: Compiled
) -> RubricDraft:
    """Spark's answer applied to the draft `now`, saved with the interview answers that still
    hold. `diff` is from `now`'s Description to `description`, which may be the same
    (`clarify_diff`)."""
    draft = ctx.drafts.save(recompile_rubric(now, description, diff, compiled))
    for answer in carried(ctx.interview.answers(now.compiled_at), diff, draft):
        ctx.interview.add(draft.compiled_at, answer)
    return draft


def _spans(diff: DescriptionDiff) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    return [(p.start, p.end) for p in diff.kept], [(s.start, s.end) for s in diff.stretches]


def _meta(ctx: AppContext) -> MetaClient:
    if ctx.meta is None:
        raise MetaUnavailableError("Compiling needs the Meta API: set MODEL_API_KEY in .env")
    return ctx.meta


def _manifest(ctx: AppContext, settings: RubricSettings) -> str:
    return capabilities_manifest(ctx, anchor_episodes(ctx), settings)


async def _compile_afresh(ctx: AppContext, description: str) -> RubricDraft:
    meta = _meta(ctx)
    manifest = _manifest(ctx, SEEDED_SETTINGS)
    return await compile_rubric(meta, description, manifest, SEEDED_SETTINGS)


def current_draft(ctx: AppContext) -> RubricDraft:
    draft = ctx.drafts.get()
    if draft is None:
        raise NoDraftError("There's no Rubric draft yet: compile a Description first")
    return draft


def edit_draft(ctx: AppContext, edit: DraftEdit) -> RubricDraft:
    """Applies direct edits to the draft and saves it, with no model call."""
    return ctx.drafts.save(apply_edit(current_draft(ctx), edit))


def preview_draft(ctx: AppContext, edit: DraftEdit) -> AnchorPreview:
    """The draft, with `edit` applied but not saved, scored on the anchor pool at s = 1, as the
    version Run freezes from it starts."""
    draft = apply_edit(current_draft(ctx), edit)
    facts = revealed_anchor_facts(ctx)
    labels = anchor_labels(ctx, list(facts))
    return anchor_preview(facts, draft.rubric(), draft.criteria, None, labels)


def preview_version(ctx: AppContext, version: RubricVersion) -> AnchorPreview:
    """The version scored on the anchor pool with the margin multiplier it is calibrated with."""
    rubric = version.rubric
    facts = revealed_anchor_facts(ctx)
    labels = anchor_labels(ctx, list(facts))
    s = ctx.calibrations.s_for(version.version)
    return anchor_preview(facts, rubric, rubric.criteria, version.version, labels, s)


def run_draft(ctx: AppContext) -> RubricVersion:
    """Freezes the draft into the next Rubric version, which every Episode is then scored
    against. Never waits for unconfirmed assumptions, and never asks Spark its visual Criteria:
    those are asked only on request (`POST /api/visual/ask`, `winnow ask`). With the Meta API,
    Spark's Reasons for the new version are queued in the background."""
    version = ctx.rubrics.add(current_draft(ctx).rubric())
    queue_reasons(ctx)
    return version
