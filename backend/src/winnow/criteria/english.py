"""The English a Criterion shows, rendered from its typed fields and nothing else."""

from winnow.criteria.catalog import CATALOG
from winnow.criteria.models import Criterion
from winnow.criteria.windows import window_name
from winnow.visual.crop import DEFAULT_VIEW

COMPARATORS = {"<": "<", "<=": "≤", ">=": "≥", ">": ">", "==": "="}


def format_value(value: float, unit: str) -> str:
    if unit == "attempts":
        return f"{value:g}"
    if unit == "m":
        return f"{round(value * 100, 1):g} cm"
    if unit == "ratio":
        return f"{value:.2f}"
    return f"{value:g} {unit}"


CROPS = {"view": "", "placement": ", cropped to the object and its target"}


def _visual(criterion: Criterion) -> str:
    """e.g. 'Spark, on the view the object was boxed in after release, cropped to the object
    and its target: "Is the object resting in or on the target?"'."""
    view = criterion.views[0] if criterion.views else DEFAULT_VIEW
    if criterion.crop == "placement":  # the object's track and target box are in that view
        view = "the view the object was boxed in"
    crop = CROPS[criterion.crop or "view"]
    return f'Spark, on {view} {window_name(criterion.window)}{crop}: "{criterion.question}"'


def english(criterion: Criterion) -> str:
    """e.g. 'Grasp attempts, up to and including the grasp, ≤ 1' or 'Longest stretch with the
    arm under 0.01 m/s, while holding, < 1.5 s'."""
    if criterion.kind == "visual":
        return _visual(criterion)
    quantity = CATALOG[criterion.primitive].english.format(**criterion.params)
    if criterion.window.kind != "whole":
        quantity = f"{quantity.rstrip(',')}, {window_name(criterion.window)},"
    comparison = (
        f"{COMPARATORS[criterion.comparator]} {format_value(criterion.threshold, criterion.unit)}"
    )
    return f"{quantity} {comparison}"
