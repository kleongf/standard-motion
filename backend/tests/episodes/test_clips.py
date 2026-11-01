"""A failed cut never leaves a half-written clip behind."""

from pathlib import Path

import pytest

from winnow.episodes import clips


def test_a_failed_cropped_cut_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fails_midway(*args: str) -> None:
        Path(args[-1]).write_bytes(b"half a clip")  # ffmpeg had started writing
        raise RuntimeError("ffmpeg failed: out of disk")

    monkeypatch.setattr(clips, "_ffmpeg", fails_midway)
    out = tmp_path / "clips" / "window.mp4"

    with pytest.raises(RuntimeError, match="out of disk"):
        clips.cut_cropped(tmp_path / "source.mp4", 1.0, 2.0, (0, 0, 64, 64), out)

    assert list(out.parent.iterdir()) == []
