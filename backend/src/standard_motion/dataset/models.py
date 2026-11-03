from pydantic import BaseModel


class SourceCount(BaseModel):
    name: str
    episodes: int


class DatasetStatus(BaseModel):
    """Description-independent work on the Dataset so far, for the Prepare page."""

    name: str
    sources: list[SourceCount]
    episodes: int  # ingested: robot data plus H.264 and 5 fps clips for every camera
    boxes: int  # Episodes with a hand-drawn box
    baseline: int | None  # Episodes with a complete Spark-alone baseline; None without Meta
    wrist_tracks: int | None  # Episodes with a wrist object track; None without Meta
    wrist_no_closure: int  # Episodes whose gripper never closed, so they have no wrist track
    exterior_tracks: int | None  # Episodes with an exterior object track; None without Meta
    target_boxes: int  # boxed Episodes whose target box is found or drawn
    targets_missing: int  # boxed Episodes where SAM found no target box and none is drawn yet
    cost_usd: float  # Meta API spend so far
