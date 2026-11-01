"""The Rubric version every Project starts from, seeded from the frozen Description by hand: its
measured and tracked Criteria, as #18 compiles it, and the placement question Spark answers from a
cropped clip."""

from winnow.baseline.prompts import FROZEN
from winnow.criteria.models import Criterion, RubricSettings, Setting, Window
from winnow.rubric.models import Rubric

FIRST_TRY, NEVER_DROPS, PLACES, NO_PAUSES = FROZEN.phrases

SEEDED_SETTINGS = RubricSettings(
    gripper_closed_level=Setting(
        value=0.2,
        margin=0.1,
        assumption="Closed above 0.2 of the gripper's range (0 open, 1 closed); droid_100's "
        "grasps close to 0.5-1.0.",
    ),
    grasp_rise_m=Setting(
        value=0.02,
        margin=0.01,
        assumption="The grasp is the last closure during which the arm rises 2 cm; earlier "
        "closures are failed attempts.",
    ),
)

SEEDED = Rubric(
    description=FROZEN.text,
    phrases=list(FROZEN.phrases),
    settings=SEEDED_SETTINGS,
    criteria=[
        Criterion(
            id="grasp-attempts",
            phrase=FIRST_TRY,
            primitive="grasp_attempts",
            comparator="<=",
            threshold=1,
            unit="attempts",
        ),
        Criterion(
            id="in-hand-lost",
            phrase=NEVER_DROPS,
            primitive="in_hand_lost_s",
            comparator="<",
            threshold=0.4,
            unit="s",
            window=Window(kind="holding"),
            assumptions=[
                "A slip is the object out of the closed gripper's fingers for 0.4 s or more."
            ],
        ),
        Criterion(
            id="fall-after-release",
            phrase=NEVER_DROPS,
            primitive="fall_after_release",
            comparator="<=",
            threshold=0.5,
            unit="box-heights",
            assumptions=["Set down, not dropped: it falls under half its height after release."],
        ),
        Criterion(
            id="release-height",
            phrase=NEVER_DROPS,
            primitive="release_height_m",
            comparator="<=",
            threshold=0.05,
            unit="m",
            assumptions=[
                "Placed, not dropped: released within 5 cm above where it was picked up. "
                "Inconclusive, since placing on top of something is a high release."
            ],
        ),
        Criterion(
            id="final-overlap",
            phrase=PLACES,
            primitive="final_overlap",
            comparator=">=",
            threshold=0.5,
            unit="ratio",
            window=Window(kind="last_n_s", seconds=1.0),
            assumptions=["On the target: at least half its final box is inside the target box."],
        ),
        Criterion(
            id="placed-on-target",
            phrase=PLACES,
            primitive="ask_video",
            comparator=">=",
            threshold=3,
            unit="samples",
            window=Window(kind="after_release"),
            views=["exterior_image_1_left"],
            question="Is the object resting in or on the target named in the task when the clip "
            "ends?",
            paraphrases=[
                "Once the gripper lets go, does the object end up in or on the task's target?",
                "At the end, has the object been placed in or on the target rather than dropped "
                "beside it or left somewhere else?",
            ],
            crop="placement",
        ),
        Criterion(
            id="longest-pause",
            phrase=NO_PAUSES,
            primitive="longest_still_s",
            params={"speed_below_m_s": 0.01},
            comparator="<",
            threshold=2.0,
            unit="s",
            assumptions=["A pause is the arm under 1 cm/s; a long one lasts 2 s or more."],
        ),
    ],
)
