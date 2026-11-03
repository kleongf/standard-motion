"""Where droid_1.0.1's files are read from: the Hub (nothing large is downloaded: parquet is
read by column, and ffmpeg range-reads one Episode's stretch of a shared mp4) or a local copy
laid out like the repo (the test fixtures)."""

from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from huggingface_hub import HfApi, HfFileSystem

REPO_ID = "lerobot/droid_1.0.1"


class Files(Protocol):
    def list(self, folder: str) -> list[str]:
        """Repo paths of the files directly under `folder`, sorted."""
        ...

    def open(self, path: str) -> AbstractContextManager[BinaryIO]: ...

    def video_input(self, path: str) -> str:
        """What ffmpeg's -i takes for this file: a local path or an https URL."""
        ...


class LocalFiles:
    def __init__(self, root: Path) -> None:
        self._root = root

    def list(self, folder: str) -> list[str]:
        return sorted(str(p.relative_to(self._root)) for p in (self._root / folder).glob("*"))

    @contextmanager
    def open(self, path: str) -> Generator[BinaryIO]:
        with (self._root / path).open("rb") as f:
            yield f

    def video_input(self, path: str) -> str:
        return str(self._root / path)


class HubFiles:
    def __init__(self) -> None:
        self._fs = HfFileSystem()

    def list(self, folder: str) -> list[str]:
        tree = HfApi().list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo=folder)
        return sorted(entry.path for entry in tree)

    @contextmanager
    def open(self, path: str) -> Generator[BinaryIO]:
        handle = self._fs.open(f"datasets/{REPO_ID}/{path}", "rb", block_size=2**20)  # pyright: ignore[reportUnknownMemberType]
        with cast(BinaryIO, handle) as f:
            yield f

    def video_input(self, path: str) -> str:
        return f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{path}"
