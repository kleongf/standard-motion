"""The words of the compile call and its one repair turn."""

import json
from collections.abc import Sequence

from winnow.rubric.examples import EXAMPLES


def _examples() -> str:
    return "\n\n".join(
        f"Example {i + 1}. Description:\n{json.dumps(e.description)}\nAnswer:\n"
        f"{json.dumps(e.answer)}"
        for i, e in enumerate(EXAMPLES)
    )


def compile_prompt(description: str, manifest: str) -> str:
    return f"""You turn a curator's Description of an expert robot Episode into a Rubric: typed \
Criteria that code measures on every Episode. You never measure anything yourself.

{manifest}

How to answer:
1. Split the Description into Phrases, in order. Each Phrase is one requirement (or one piece of \
framing), copied from the Description exactly, character for character, as one contiguous \
stretch of it ("phrase"). Phrases never overlap. Every meaningful word should fall inside some \
Phrase.
2. For each Phrase, first restate precisely what it requires of an Episode ("restatement"), \
then give it a status:
   - "checked": the primitives above can check it. Give one or more Criteria \
("typed_criteria"); most Phrases need one.
   - "context": it frames the Description and asks nothing checkable of an Episode (e.g. it \
names the task). Give a one-line reason ("status_reason"). No Criteria.
   - "unsupported": it asks something of an Episode, but no primitive above can check it. Give a \
one-line reason naming what is missing. No Criteria. Never stretch a primitive to cover a \
Phrase it doesn't measure.
3. A Criterion is one primitive compared with one threshold, in the primitive's unit:
   - "params": every parameter the primitive takes; null for the parameters it doesn't take.
   - "window": where in the Episode it looks; "seconds" only for last_n_s, else null.
   - "views", "question" and "paraphrases" are for tracked and visual primitives only, and \
"crop" for visual ones: use [], null, [] and null for measured ones.
   - "hard": true, unless the Phrase says ideally, preferably or similar; a soft Criterion is \
shown but never rejects an Episode.
   - "assumptions": one sentence for each value the Description doesn't state that you had to \
choose (a threshold, a speed, a window), saying what you assumed. Use the anchor-pool ranges to \
choose values that separate good Episodes from bad ones. No assumption for a value the \
Description states.

{_examples()}

Now the curator's Description:
{json.dumps(description)}"""


def recompile_prompt(
    description: str, manifest: str, kept: Sequence[str], changed: Sequence[str]
) -> str:
    """The compile call after an edit: the whole Description, answered only for what changed."""
    unchanged, asked = _listed(kept), _listed(changed)
    return f"""{compile_prompt(description, manifest)}

The curator edited this Description after it was compiled. These Phrases are unchanged and \
already compiled, so leave them out of your answer:
{unchanged}

Answer only for the changed text below, split into Phrases as above. Each Phrase is still \
copied exactly from the Description and overlaps none of the unchanged Phrases:
{asked}"""


def clarify_prompt(
    description: str, manifest: str, kept: Sequence[str], phrase: str, text: str
) -> str:
    """The compile call after the curator answered, in their own words, a question about one
    Phrase (or words in no Phrase): the unchanged Description, answered only for that text, read
    as the curator's answer means it."""
    return f"""{compile_prompt(description, manifest)}

This Description is compiled already. These Phrases stay as they are, so leave them out of your \
answer:
{_listed(kept)}

The curator's answer about {json.dumps(phrase)}: {json.dumps(text)}

Answer only for {json.dumps(phrase)}, split into Phrases as above and read as the curator's \
answer says it is meant. Each Phrase is still copied exactly from the Description and overlaps \
none of the Phrases that stay."""


def _listed(texts: Sequence[str]) -> str:
    return "\n".join(f"- {json.dumps(t)}" for t in texts)


def repair_prompt(errors: Sequence[str], whole: bool) -> str:
    """The follow-up after an answer failed code's checks: fix the listed Phrases, or the whole
    answer when it couldn't be read at all."""
    listed = "\n".join(f"- {e}" for e in errors)
    if whole:
        scope = "Answer again in full, following the schema."
    else:
        scope = (
            "Answer again with only these Phrases, corrected, in the order listed. If a Phrase "
            'truly can\'t be checked with the primitives above, mark it "unsupported" with a '
            "reason."
        )
    return f"Your answer above failed these checks:\n{listed}\n\n{scope}"
