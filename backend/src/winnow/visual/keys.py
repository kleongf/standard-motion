"""What identifies a visual Criterion's answers on an Episode: everything that decides its clip
and its prompts, and nothing else. A threshold drag, a hard/soft toggle or a renamed id keeps
the key, so the answers (and the Meta cache) still serve it."""

import hashlib
import json

from winnow.criteria.models import Criterion, RubricSettings


def prompts(criterion: Criterion) -> list[str]:
    """The frozen question, then its paraphrases: one sample each."""
    return [criterion.question or "", *criterion.paraphrases]


def ask_key(criterion: Criterion, settings: RubricSettings) -> str:
    asked = {
        "prompts": prompts(criterion),
        "views": criterion.views,
        "window": criterion.window.model_dump(),
        "crop": criterion.crop or "view",
        # The grasp rule places every grasp-relative window, and so the clip.
        "grasp": [settings.gripper_closed_level.value, settings.grasp_rise_m.value],
    }
    canonical = json.dumps(asked, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]
