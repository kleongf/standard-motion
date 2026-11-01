"""The few-shot examples compile shows Spark pass the checks its own answers must."""

import json

import pytest

from winnow.rubric.answer import CheckedPhrase, check_phrase, parse_answer
from winnow.rubric.examples import EXAMPLES, Example


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.description[:30])
def test_every_example_answer_passes_the_checks(example: Example):
    answer = parse_answer(json.dumps(example.answer))
    checked: list[CheckedPhrase] = []
    for phrase in answer.phrases:
        taken = [(c.phrase.start, c.phrase.end) for c in checked]
        checked.append(check_phrase(phrase, example.description, taken))

    assert {c.phrase.status for c in checked} >= {"checked"}
