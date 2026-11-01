"""A visual Criterion and hand-written Spark answers to it, for scoring tests."""

from tests.triage.robot_data import PLACES
from winnow.criteria.models import Criterion, Window
from winnow.visual.models import AnswerValue, VisualAnswers, VisualClip, VisualReply, VisualSample

QUESTION = "Is the object resting in or on the target at the end?"
PARAPHRASES = [
    "Does the object end up in or on the target once the gripper lets go?",
    "After the release, is the object placed in or on the target rather than beside it?",
]


def placed(hard: bool = True) -> Criterion:
    return Criterion(
        id="placed",
        phrase=PLACES,
        primitive="ask_video",
        comparator=">=",
        threshold=3,
        unit="samples",
        window=Window(kind="after_release"),
        views=["exterior_image_1_left"],
        question=QUESTION,
        paraphrases=PARAPHRASES,
        crop="placement",
        hard=hard,
    )


CLIP = VisualClip(
    name="0123456789abcdef.mp4", camera="exterior_image_1_left", start=1.5, end=3.0, box=None
)


def answers(*values: AnswerValue, confidence: float = 0.9) -> VisualAnswers:
    prompts = [QUESTION, *PARAPHRASES]
    return VisualAnswers(
        clip=CLIP,
        samples=[
            VisualSample(
                prompt=prompt,
                reply=VisualReply(answer=value, confidence=confidence, observation=f"Saw {i}."),
                error=None,
            )
            for i, (prompt, value) in enumerate(zip(prompts, values, strict=True))
        ],
        error=None,
    )
