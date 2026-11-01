"""The interview's words, from templates: no model call."""

from dataclasses import dataclass

from winnow.criteria.english import format_value
from winnow.criteria.models import Criterion, Setting
from winnow.interview.bisection import Resolution
from winnow.interview.models import AnswerValue, Option, SettingName

PHRASE_OPTIONS = [
    Option(answer="accept", label="Leave it unchecked: it never fails an Episode"),
    Option(answer="context", label="Mark it Context: it describes, it doesn't require"),
]


def phrase_prompt(text: str, reason: str | None) -> str:
    why = f" {reason.rstrip('.')}." if reason else ""
    return f"Nothing checks “{text}”.{why} What should Winnow do with it?"


def words_prompt(text: str) -> str:
    return f"“{text}” is in no Phrase, so nothing checks it. What should Winnow do with it?"


def threshold_prompt(measurement: str, phrase: str) -> str:
    return f"Is {measurement} fine for “{phrase}”?"


def threshold_options(phrase: str) -> list[Option]:
    return [
        Option(answer="pass", label=f"Fine: “{phrase}” passes"),
        Option(answer="fail", label=f"Not fine: “{phrase}” fails"),
        Option(answer="skip", label="Skip: leave this threshold assumed"),
    ]


def phrase_effect(answer: AnswerValue, text: str) -> str:
    if answer == "context":
        return f"Marked Context: “{text}” checks nothing, by design."
    return f"Left unchecked: nothing checks “{text}”."


def label_effect(episode_id: str, answer: AnswerValue, phrase: str) -> str:
    return f"Labelled {episode_id} {answer} on “{phrase}”."


def resolution_effect(resolution: Resolution, before: Criterion) -> str:
    unit = before.unit
    if resolution.outcome == "confirmed":
        return f"Threshold confirmed at {format_value(before.threshold, unit)}."
    if resolution.outcome == "unbracketed":
        return (
            "No anchor Episode on the other side brackets it, so the threshold stays assumed; "
            "the labels hold for these Episodes."
        )
    margin = format_value(resolution.margin or 0.0, unit)
    return (
        f"Threshold {format_value(before.threshold, unit)} → "
        f"{format_value(resolution.threshold, unit)}, margin ± {margin}."
    )


def hard_soft_prompt(english: str) -> str:
    return (
        f"If an Episode fails “{english}”, should it be rejected outright, or only lower its "
        "quality?"
    )


def hard_soft_options(hard: bool) -> list[Option]:
    return [
        Option(answer="hard", label="Hard: reject it outright"),
        Option(answer="soft", label="Soft: only lower its quality"),
        Option(answer="skip", label=f"Skip: leave it {'hard' if hard else 'soft'}"),
    ]


def hard_soft_effect(answer: AnswerValue, hard: bool) -> str:
    if answer == "hard":
        return "Hard: failing it rejects the Episode."
    if answer == "soft":
        return "Soft: failing it only lowers the Episode's quality."
    return f"Skipped: it stays {'hard' if hard else 'soft'}."


@dataclass(frozen=True)
class SettingWords:
    title: str  # as the user reads it
    unit: str  # as `format_value` reads it; "" for none
    prompt: str  # the question asked of a moment
    yes: str  # what pass means there
    no: str


SETTING_WORDS: dict[SettingName, SettingWords] = {
    "gripper_closed_level": SettingWords(
        "Gripper closed level", "", "Is the gripper closed at this moment?", "Closed", "Open"
    ),
    "grasp_rise_m": SettingWords(
        "Grasp rise", "m", "Did the gripper lift the object here?", "Lifted", "Not lifted"
    ),
}


def setting_options(name: SettingName) -> list[Option]:
    words = SETTING_WORDS[name]
    return [
        Option(answer="pass", label=words.yes),
        Option(answer="fail", label=words.no),
        Option(answer="skip", label="Skip: leave this setting assumed"),
    ]


def _setting_value(name: SettingName, value: float) -> str:
    unit = SETTING_WORDS[name].unit
    return format_value(value, unit) if unit else f"{value:g}"


def setting_answer_effect(name: SettingName, episode_id: str, answer: AnswerValue) -> str:
    words = SETTING_WORDS[name]
    if answer == "skip":
        return "Skipped: the setting stays assumed."
    return f"Marked {episode_id} {(words.yes if answer == 'pass' else words.no).lower()}."


def setting_effect(name: SettingName, resolution: Resolution, before: Setting) -> str:
    title = SETTING_WORDS[name].title
    if resolution.outcome == "confirmed":
        return f"{title} confirmed at {_setting_value(name, before.value)}."
    if resolution.outcome == "unbracketed":
        return "No anchor Episode on the other side brackets it, so the setting stays assumed."
    margin = _setting_value(name, resolution.margin or 0.0)
    return (
        f"{title} {_setting_value(name, before.value)} → "
        f"{_setting_value(name, resolution.threshold)}, margin ± {margin}."
    )


def disagree_prompt(phrase: str, crisp: bool) -> str:
    if crisp:
        return f"Its Criteria disagree on this Episode. Does “{phrase}” pass?"
    return f"A fail on “{phrase}” can't be confirmed on this Episode. Does it pass?"


def disagree_options(phrase: str) -> list[Option]:
    return [
        Option(answer="pass", label=f"Pass: “{phrase}” passes"),
        Option(answer="fail", label=f"Fail: “{phrase}” fails"),
        Option(answer="skip", label="Skip: let its Criteria decide"),
    ]


def disagree_measurement(fails: int, passes: int) -> str:
    """What the Phrase's Criteria say, e.g. "1 fails, 1 passes"."""
    said = [f"{fails} fail{'s' if fails == 1 else ''}"]
    if passes:
        said.append(f"{passes} pass{'es' if passes == 1 else ''}")
    return ", ".join(said)


DISAGREE_SKIPPED = "Skipped: its Criteria decide."
