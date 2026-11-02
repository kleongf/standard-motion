"""Video conversions with ffmpeg: H.264 for Spark and the browser, 5 fps for SAM."""

import subprocess
import uuid
from pathlib import Path

SAM_FPS = 5


def _ffmpeg(*args: str) -> None:
    result = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip() or result.returncode}")


def _encode(source: Path, out: Path, *filters: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".partial.mp4")  # never leave a half-written clip under its name
    _ffmpeg(
        "-i", str(source), *filters,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(partial),
    )  # fmt: skip
    partial.replace(out)


def to_h264(source: Path, out: Path) -> None:
    _encode(source, out)


def to_sam_fps(source: Path, out: Path) -> None:
    _encode(source, out, "-vf", f"fps={SAM_FPS}")


def probe(clip: Path) -> tuple[int, int, int]:
    """(frames, width, height) of a clip's video stream, counting frames by decoding them."""
    result = subprocess.run(
        [
            *("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0"),
            *("-show_entries", "stream=nb_read_frames,width,height", "-of", "csv=p=0"),
            str(clip),
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.returncode}")
    width, height, frames = (int(v) for v in result.stdout.strip().split(","))
    return frames, width, height


def first_frame(clip: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".partial.jpg")
    _ffmpeg("-i", str(clip), "-frames:v", "1", "-q:v", "2", str(partial))
    partial.replace(out)


def cut_h264(source: str, start_s: float, frames: int, out: Path, lossless: bool = False) -> None:
    """`frames` frames of `source` from `start_s`, which may be an https URL ffmpeg range-reads;
    `lossless` keeps every decoded frame exactly, in a larger file."""
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".partial.mp4")
    quality = ["-qp", "0"] if lossless else []
    _ffmpeg(
        "-ss", f"{start_s:.4f}", "-i", source, "-frames:v", str(frames),
        "-c:v", "libx264", *quality, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(partial),
    )  # fmt: skip
    partial.replace(out)


def keyframe_at(source: str, t: float) -> float:
    """The time of the last keyframe at or before `t`: where a stream copy from `t` starts."""
    result = subprocess.run(
        [
            *("ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals"),
            *(f"{t:.6f}%+#1", "-show_entries", "packet=pts_time", "-of", "csv=p=0", source),
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.returncode}")
    return float(result.stdout.split()[0].strip(","))


def frame_checksum(source: str, t: float) -> str:
    """The checksum of the frame decoded at `t` (to the millisecond, so a time rounded a little
    past the frame's still finds it): the same picture gives the same one in any file."""
    result = subprocess.run(
        [
            *("ffmpeg", "-loglevel", "error", "-ss", f"{max(t - 0.001, 0.0):.6f}", "-i", source),
            *("-frames:v", "1", "-f", "framemd5", "-"),
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    lines = [line for line in result.stdout.splitlines() if not line.startswith("#")]
    if result.returncode != 0 or not lines:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip() or result.returncode}")
    return lines[0].rsplit(",", 1)[1].strip()


def copy_cut(source: str, start_s: float, frames: int, out: Path) -> bool:
    """`frames` frames from `start_s` copied without re-encoding, so in the source's own codec,
    and no frame more: a copy has to start on a keyframe, so this writes nothing and returns
    False when `start_s` isn't on one. Without B-frames the frames come out in order, so the
    copy ends on the stretch's last frame; check it, since a codec that reorders them doesn't."""
    if abs(keyframe_at(source, start_s) - start_s) > 0.001:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".partial.mp4")
    _ffmpeg(
        "-ss", f"{start_s:.6f}", "-i", source, "-frames:v", str(frames),
        "-map", "0:v:0", "-c", "copy", str(partial),
    )  # fmt: skip
    partial.replace(out)
    return True


def cut_cropped(
    source: Path, start_s: float, end_s: float, crop: tuple[int, int, int, int] | None, out: Path
) -> None:
    """The stretch from `start_s` to `end_s`, cropped to (left, top, width, height) if given.
    Visual Criteria with the same window and view share a clip and may cut it at once, so each
    cut writes its own partial file before replacing `out` with it."""
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(f".{uuid.uuid4().hex[:8]}.partial.mp4")
    filters = ["-vf", "crop={2}:{3}:{0}:{1}".format(*crop)] if crop else []
    try:
        _ffmpeg(
            "-ss", f"{start_s:.4f}", "-i", str(source), "-t", f"{end_s - start_s:.4f}", *filters,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
            str(partial),
        )  # fmt: skip
        partial.replace(out)
    finally:
        partial.unlink(missing_ok=True)  # named for this cut alone, so nothing else removes it


def tile_frames(source: str, start_s: float, duration_s: float, count: int, out: Path) -> None:
    """`count` frames spread evenly over the stretch, in one row, as a JPEG."""
    out.parent.mkdir(parents=True, exist_ok=True)
    rate = count / duration_s
    _ffmpeg(
        "-ss", f"{start_s:.4f}", "-t", f"{duration_s:.4f}", "-i", source,
        "-vf", f"fps={rate:.6f},tile={count}x1", "-frames:v", "1", "-q:v", "3", str(out),
    )  # fmt: skip
