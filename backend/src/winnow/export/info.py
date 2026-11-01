"""An exported dataset's meta/info.json: the source's own where it has one, with the totals,
split and paths of the export; otherwise built from the data's schema and the videos."""

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pyarrow as pa

CODEBASE_VERSION = "v3.0"
CHUNKS_SIZE = 1000  # files per chunk folder
DATA_PATH = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
VIDEO_PATH = "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
_DTYPES = {"double": "float64", "float": "float32", "large_string": "string"}


def _dtype(arrow: pa.DataType) -> str:
    name = str(arrow)
    return _DTYPES.get(name, name)


def data_features(data: pa.Table) -> dict[str, dict[str, Any]]:
    """LeRobot's feature description of each data column: its dtype and per-frame shape."""
    first: dict[str, Any] = data.slice(0, 1).to_pylist()[0] if data.num_rows else {}
    features: dict[str, dict[str, Any]] = {}
    for name in data.column_names:
        arrow = cast(pa.DataType, data.schema.field(name).type)  # pyright: ignore[reportUnknownMemberType]
        if isinstance(arrow, pa.ListType | pa.FixedSizeListType | pa.LargeListType):
            values = cast(pa.DataType, arrow.value_type)  # pyright: ignore[reportUnknownMemberType]
            dtype, shape = _dtype(values), [len(first.get(name) or [])]
        else:
            dtype, shape = _dtype(arrow), [1]
        features[name] = {"dtype": dtype, "shape": shape, "names": None}
    return features


def video_feature(clip: Path, fps: float) -> dict[str, Any]:
    """LeRobot's feature description of a camera's video, read from one of its files."""
    result = subprocess.run(
        [
            *("ffprobe", "-v", "error", "-select_streams", "v:0", "-of", "json"),
            *("-show_entries", "stream=codec_name,pix_fmt,width,height", str(clip)),
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.returncode}")
    stream = json.loads(result.stdout)["streams"][0]
    height, width = int(stream["height"]), int(stream["width"])
    return {
        "dtype": "video",
        "shape": [height, width, 3],
        "names": ["height", "width", "channels"],
        "info": {
            "video.height": height,
            "video.width": width,
            "video.codec": stream["codec_name"],
            "video.pix_fmt": stream["pix_fmt"],
            "video.is_depth_map": False,
            "video.fps": fps,
            "video.channels": 3,
            "has_audio": False,
        },
    }


def info_json(
    source: dict[str, Any] | None,
    data: pa.Table,
    episodes: int,
    tasks: int,
    fps: float,
    videos: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """`videos`: each camera's feature, keyed like the data's columns, as read from the exported
    files (the source's own may describe other files: droid_100's, its shared videos)."""
    info = dict(source or {})
    info.update(
        codebase_version=CODEBASE_VERSION,
        fps=round(fps) if fps.is_integer() else fps,
        total_episodes=episodes,
        total_frames=data.num_rows,
        total_tasks=tasks,
        chunks_size=int(info.get("chunks_size") or CHUNKS_SIZE),
        splits={"train": f"0:{episodes}"},
        data_path=DATA_PATH,
        video_path=VIDEO_PATH if videos else None,
        features={**(info.get("features") or data_features(data)), **videos},
    )
    return info
