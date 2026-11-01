"""The words of the one Spark call that writes a Reason from a template Reason and its Evidence.

Every time Spark may cite is written as `[t=…]` after the text it belongs to; it copies that
number into the span, so a time it cites always seeks to a moment Winnow measured.
"""

from winnow.criteria.models import TextSpan
from winnow.triage.models import CriterionResult, Triage

REASON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["spans"],
    "properties": {
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "t"],
                "properties": {
                    "text": {"type": "string"},
                    "t": {"type": ["number", "null"]},
                },
            },
        }
    },
}

DECISIONS = {"reject": "Reject", "needs_review": "Needs review", "keep": "Keep"}


def shown(triage: Triage) -> list[CriterionResult]:
    """The results the prompt lays out: every one that didn't pass."""
    return [r for r in triage.criteria if r.status != "pass"]


def timed(spans: list[TextSpan]) -> str:
    return "".join(s.text if s.t is None else f"{s.text} [t={s.t:.3f}]" for s in spans)


def _result(result: CriterionResult) -> str:
    lines = [
        f'- "{result.phrase}" ({"hard" if result.hard else "soft"}): {result.english}',
        f"  {result.status}{f', {result.uncertainty}' if result.uncertainty else ''}; "
        f"measured {result.measurement}",
    ]
    if result.evidence:
        lines.append(f"  Evidence: {timed(result.evidence)}")
    if result.moments:
        moments = ", ".join(f"{m.label} [t={m.t:.3f}]" for m in result.moments)
        lines.append(f"  Moments: {moments}")
    if result.at_s is not None:
        lines.append(f"  Went wrong at [t={result.at_s:.3f}]")
    return "\n".join(lines)


def reason_prompt(triage: Triage) -> str:
    results = "\n".join(_result(r) for r in shown(triage))
    lead = (
        "Lead with the earliest conclusive fail, citing first the time it went wrong, then "
        "name any others. "
        if triage.decision == "reject"
        else "Say which Phrases couldn't be decided and why. "
    )
    return (
        "Winnow judged one recorded robot Episode against a description of an expert Episode. "
        f"Its Triage decision is {DECISIONS[triage.decision]}, and its template Reason is:\n\n"
        f"{timed(triage.reason)}\n\n"
        f"The Criterion results that didn't pass, with their Evidence:\n{results}\n\n"
        "Rewrite the Reason as one plain sentence a curator reads at a glance, using only "
        f"these facts. {lead}"
        "Answer it as spans of text. A span that cites a time holds just that time, e.g. "
        '"1.3 s", with `t` set to the number from one of the [t=…] marks above, copied '
        "exactly; cite no other time. Every other span has `t` null. Leave the [t=…] marks "
        "themselves out of the text."
    )
