"""Where Episodes come from: one adapter per dataset, all yielding the same Episode shape.

Camera names are droid_100's (`exterior_image_1_left`, ...); other adapters map onto them."""

from pathlib import Path
from typing import Protocol

from standard_motion.core.settings import Settings
from standard_motion.episodes import droid100, droid101
from standard_motion.episodes.droid101_files import HubFiles, LocalFiles
from standard_motion.episodes.models import SourceEpisode


class Source(Protocol):
    name: str
    cameras: tuple[str, ...]

    def load(self, index: int) -> SourceEpisode: ...

    def write_clip(self, index: int, camera: str, out: Path) -> None:
        """Write the Episode's clip for one camera as H.264."""
        ...


def sources_from(settings: Settings) -> dict[str, Source]:
    root = settings.droid100_root
    fetch = (
        droid100.local_fetch(root)
        if root is not None
        else droid100.hub_fetch(settings.data_dir / "droid_100")
    )
    root101 = settings.droid101_root
    files = LocalFiles(root101) if root101 is not None else HubFiles()
    return {droid100.NAME: droid100.Droid100(fetch), droid101.NAME: droid101.Droid101(files)}
