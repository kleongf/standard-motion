"""The curator's own words in the interview, read by Spark: the only interview answers that ask a
model.

To the question being asked, one cheap call maps the words onto one of its answers, which then
applies exactly as if picked (`service.answer`); or, on a Phrase, words or threshold question,
onto "change", and only then does a second call compile the asked text again with the words
(`rubric.service.clarify_draft`). Two calls, not one, because most words just pick an answer:
that call is small and low effort, while a compile call carries the whole capabilities manifest
and reasons at length. With no question, one call edits the Description with the words, which
then recompiles as any edit does.
"""

from pydantic import BaseModel, ValidationError

from winnow.core.context import AppContext
from winnow.interview.models import (
    AnswerDraw,
    AnswerValue,
    Interview,
    PhraseQuestion,
    Question,
    TextDraw,
    TextReply,
    ThresholdQuestion,
    asked_episode,
)
from winnow.interview.service import StaleQuestionError, answer, current
from winnow.interview.text_prompt import (
    CHANGE,
    MAPPING_SCHEMA_NAME,
    NONE,
    REWRITE_SCHEMA,
    REWRITE_SCHEMA_NAME,
    mapping_prompt,
    mapping_schema,
    rewrite_prompt,
)
from winnow.meta.client import MetaClient
from winnow.meta.models import SparkCall, SparkRequest, Text
from winnow.meta.pricing import SPARK_CONTRIBUTOR
from winnow.rubric.models import DESCRIPTION_MAX, RubricDraft
from winnow.rubric.service import (
    DraftChangedError,
    MetaUnavailableError,
    clarify_draft,
    compile_draft,
    current_draft,
)

MAX_OUTPUT_TOKENS = 2000  # a short answer, but low effort still reasons before it


class TextAnswerError(RuntimeError):
    """Spark's reading of the curator's words couldn't be used."""


class _Mapped(BaseModel):
    choice: str
    reply: str


class _Rewritten(BaseModel):
    description: str
    reply: str


async def answer_text(ctx: AppContext, draw: TextDraw) -> TextReply:
    """Raises StaleQuestionError unless `draw` names the question being asked, or none."""
    if ctx.meta is None:
        raise MetaUnavailableError(
            "Answering in your own words needs the Meta API: set MODEL_API_KEY in .env"
        )
    if draw.question_key is None:
        return await _edit_description(ctx, ctx.meta, draw.text)
    interview = current(ctx)
    asking = interview.question
    if asking is None or asking.key != draw.question_key:
        raise StaleQuestionError("That question isn't the one being asked")
    return await _answer_question(ctx, ctx.meta, interview, asking, draw.text)


async def _answer_question(
    ctx: AppContext, meta: MetaClient, interview: Interview, asking: Question, text: str
) -> TextReply:
    draft = current_draft(ctx)
    span = _changeable(draft, asking)
    choices = [*(o.answer for o in asking.options), *([CHANGE] if span else []), NONE]
    subject = None if span is None else draft.description[span[0] : span[1]]
    request = _request(
        mapping_prompt(asking, text, subject), mapping_schema(choices), MAPPING_SCHEMA_NAME
    )
    mapped = _read(_Mapped, await meta.spark(request))
    if mapped.choice not in choices:
        raise TextAnswerError(f"Spark answered “{mapped.choice}”, which wasn't offered")
    if mapped.choice == CHANGE and span is not None:
        if current(ctx).question != asking:  # answered meanwhile
            raise StaleQuestionError("That question was answered while Spark read your words")
        draft = await clarify_draft(ctx, draft.compiled_at, *span, text)
        interview = current(ctx)
    elif mapped.choice != NONE:
        interview = answer(ctx, _draw(asking, _value(asking, mapped.choice)))
        draft = current_draft(ctx)
    return TextReply(interview=interview, draft=draft, reply=_line(mapped.reply))


def _changeable(draft: RubricDraft, asking: Question) -> tuple[int, int] | None:
    """Where the text a "change" answer compiles again sits; None when it can't be asked."""
    match asking:
        case PhraseQuestion():
            return asking.start, asking.end
        case ThresholdQuestion():
            phrase = next((p for p in draft.phrases if p.text == asking.phrase), None)
            return None if phrase is None else (phrase.start, phrase.end)
        case _:
            return None


def _value(asking: Question, choice: str) -> AnswerValue:
    return next(o.answer for o in asking.options if o.answer == choice)


def _draw(asking: Question, value: AnswerValue) -> AnswerDraw:
    return AnswerDraw(key=asking.key, episode_id=asked_episode(asking), answer=value)


async def _edit_description(ctx: AppContext, meta: MetaClient, text: str) -> TextReply:
    draft = current_draft(ctx)
    request = _request(rewrite_prompt(draft.description, text), REWRITE_SCHEMA, REWRITE_SCHEMA_NAME)
    rewritten = _read(_Rewritten, await meta.spark(request))
    description = rewritten.description.strip()
    if not description or len(description) > DESCRIPTION_MAX:
        raise TextAnswerError("Spark's edited Description is empty or too long")
    if description != draft.description:
        if current_draft(ctx).description != draft.description:
            raise DraftChangedError("The Description changed while Spark read your words")
        draft = await compile_draft(ctx, description)
    return TextReply(interview=current(ctx), draft=draft, reply=_line(rewritten.reply))


def _request(prompt: str, schema: dict[str, object], schema_name: str) -> SparkRequest:
    return SparkRequest(
        SPARK_CONTRIBUTOR,
        (Text(prompt),),
        schema,
        f"interview:{schema_name}",
        effort="low",
        max_output_tokens=MAX_OUTPUT_TOKENS,
        schema_name=schema_name,
    )


def _read[T: BaseModel](model: type[T], call: SparkCall) -> T:
    try:
        return model.model_validate_json(call.text)
    except ValidationError as error:
        raise TextAnswerError(f"Spark's reading of your words couldn't be used: {error}") from error


def _line(reply: str) -> str:
    """Spark's reply as the one line the curator reads."""
    return " ".join(reply.split())
