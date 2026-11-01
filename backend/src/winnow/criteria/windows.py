"""Where in the Episode a Criterion looks, in robot-data frames."""

from winnow.criteria.grasps import Grasps, Interval
from winnow.criteria.models import Window

WINDOW_NAMES = {
    "whole": "whole Episode",
    "before_grasp": "before the grasp",
    "holding": "while holding",
    "after_release": "after release",
    "last_n_s": "last {seconds:g} s",
}


def window_name(window: Window) -> str:
    return WINDOW_NAMES[window.kind].format(seconds=window.seconds or 0)


def resolve_window(window: Window, grasps: Grasps, fps: float) -> Interval | None:
    """The window's frames; None when it is empty, as every grasp-relative window is in an
    Episode with no grasp."""
    last = grasps.frames - 1
    grasp = grasps.the_grasp
    match window.kind:
        case "whole":
            return Interval(0, last)
        case "last_n_s":
            return Interval(max(0, grasps.frames - round((window.seconds or 0) * fps)), last)
        case "before_grasp":
            return None if grasp is None or grasp.start == 0 else Interval(0, grasp.start - 1)
        case "holding":
            return grasp
        case "after_release":
            return None if grasp is None or not grasps.released else Interval(grasp.end + 1, last)
