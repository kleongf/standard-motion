"""A scripted SAM for box-step tests: a box prompt is followed on every frame, and a text prompt
finds its target on frame 0 only if it's one of `visible`. Spark (run at ingest) is scripted too.
Every answer is the real SAM box in `sam_sample.txt`, which a mask must accompany."""

from dataclasses import dataclass, field
from pathlib import Path

from tests.baseline.scripted import ScriptedSpark
from tests.meta.fakes import NoTranscribe
from winnow.meta.models import MetaContent
from winnow.meta.pricing import SAM
from winnow.meta.transport import Reply

_SAMPLE = (Path(__file__).parent / "sam_sample.txt").read_text().splitlines()[0]
_RECORD = _SAMPLE[_SAMPLE.index(">") + 1 :]  # one object's box and mask, without its frame tag
SAMPLE_BOX = (186, 49, 221, 82)  # what _RECORD parses to: left, top, right, bottom
CLIP_FRAMES = 15  # a fixture Episode's 5 fps clip


@dataclass(frozen=True)
class SamCallMade:
    prompt: str
    clip: str  # e.g. "000001/exterior_image_2_left.5fps.mp4"


@dataclass
class ScriptedSam(NoTranscribe):
    visible: set[str] = field(default_factory=lambda: {"pot"})
    calls: list[SamCallMade] = field(default_factory=list[SamCallMade])
    spark: ScriptedSpark = field(default_factory=ScriptedSpark)

    def made(self, clip_suffix: str) -> list[SamCallMade]:
        return [c for c in self.calls if c.clip.endswith(clip_suffix)]

    async def upload(self, path: Path) -> str:
        return f"{path.parent.name}/{path.name}"

    async def count_tokens(self, model: str, content: MetaContent) -> int:
        return await self.spark.count_tokens(model, content)

    async def respond(self, model: str, content: MetaContent, options: dict[str, object]) -> Reply:
        if model != SAM:
            return await self.spark.respond(model, content, options)
        prompt, clip = str(content[0]["text"]), str(content[1]["file_id"])
        self.calls.append(SamCallMade(prompt, clip))
        usage = {"video_frames_processed": CLIP_FRAMES}
        if "<|box;" in prompt:
            return Reply("\n".join(f"<{f}f>{_RECORD}" for f in range(CLIP_FRAMES)), usage)
        if prompt in self.visible:
            return Reply(f"<0f>{_RECORD}", {"video_frames_processed": 1})
        return Reply("", usage)
