"""A droid_1.0.1 Episode's clip is stream-copied when it starts on a keyframe, as LeRobot's
Episodes do, and re-encoded losslessly when it doesn't: either way, exactly its own frames."""

from pathlib import Path

from tests.helpers import decoded
from winnow.episodes.droid101 import Droid101
from winnow.episodes.droid101_files import LocalFiles
from winnow.episodes.fixtures_droid101 import write_droid101_fixture
from winnow.export.droid101 import Droid101Export

KEY = "observation.images.wrist_left"
SHARED = f"videos/{KEY}/chunk-000/file-000.mp4"


def test_an_episode_off_a_keyframe_is_re_encoded_with_exactly_its_frames(tmp_path: Path):
    root = write_droid101_fixture(tmp_path / "source", episode_keyframes=False)
    export = Droid101Export(Droid101(LocalFiles(root)))
    [row] = export.rows([2]).to_pylist()  # frames 75 to 110 of the shared video
    out = tmp_path / "clip.mp4"

    assert export.write_video(row, KEY, out) == 0.0
    assert decoded(out) == decoded(root / SHARED)[75:111]
