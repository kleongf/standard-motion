"""Check a Winnow export with the real `lerobot` library: for each dataset in it, load it, read
the first, middle and last frame of every Episode (each camera, and one camera and the action
with a window of past frames, which LeRobot decodes to within 1e-4 s), check meta/stats.json
covers every feature its normalizers read, then train a small ACT policy on it for a few steps.

Opt-in, never part of `pnpm verify` or CI: `lerobot` isn't a dependency. It runs in a throwaway
environment, via scripts/check-lerobot-export.sh. It imports nothing from Winnow.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import lerobot  # pyright: ignore
import torch  # pyright: ignore
from lerobot.datasets.lerobot_dataset import LeRobotDataset  # pyright: ignore

REPO_ID = "local/winnow-export"
STATS = ("min", "max", "mean", "std", "count", "q01", "q10", "q50", "q90", "q99")


def _say(line: str) -> None:
    sys.stdout.write(f"{line}\n")
    sys.stdout.flush()


def _datasets(export: Path) -> list[Path]:
    """The LeRobot datasets in an export folder (or the folder itself, if it is one)."""
    if (export / "meta" / "info.json").exists():
        return [export]
    return sorted(p for p in export.iterdir() if (p / "meta" / "info.json").exists())


def _check_stats(dataset: Any) -> list[str]:  # noqa: ANN401
    """What meta/stats.json lacks: every non-text feature's stats, each shaped like the feature
    (cameras per channel, (3, 1, 1)), with the quantiles that quantile normalization reads."""
    problems: list[str] = []
    stats = dataset.meta.stats or {}
    for key, feature in dataset.meta.features.items():
        if feature["dtype"] in ("string", "language"):
            continue
        if key not in stats:
            problems.append(f"stats.json has no {key}")
            continue
        missing = [s for s in STATS if s not in stats[key]]
        if missing:
            problems.append(f"stats.json {key} lacks {missing}")
        want = (3, 1, 1) if feature["dtype"] in ("video", "image") else tuple(feature["shape"])
        for stat in set(STATS) - {"count", *missing}:
            if tuple(stats[key][stat].shape) != want:
                problems.append(f"stats.json {key}/{stat} is {stats[key][stat].shape}, not {want}")
    return problems


def _episode_frames(dataset: Any, episode: int) -> tuple[int, list[int]]:  # noqa: ANN401
    """The Episode's first frame, and its first, middle and last."""
    row = dataset.meta.episodes[episode]
    start, end = int(row["dataset_from_index"]), int(row["dataset_to_index"])
    return start, sorted({start, (start + end - 1) // 2, end - 1})


def _same_frame(ours: Any, theirs: Any) -> bool:  # noqa: ANN401
    return bool(torch.allclose(ours, theirs, atol=1 / 255))


def _check_item(item: dict[str, Any], dataset: Any, camera: str = "", window: int = 0) -> None:  # noqa: ANN401
    """Each camera's frame is shaped as info.json says; `camera`'s and the action are windows
    of `window` frames."""
    for key in dataset.meta.camera_keys:
        height, width, channels = dataset.meta.features[key]["shape"]
        frame = (channels, height, width)
        want = (window, *frame) if key == camera else frame
        if tuple(item[key].shape) != want:
            raise AssertionError(f"{key} frame is {tuple(item[key].shape)}, not {want}")
    action = (window, *dataset.meta.features["action"]["shape"]) if window else None
    if action and tuple(item["action"].shape) != action:
        raise AssertionError(f"action is {tuple(item['action'].shape)}, not {action}")


def read_frames(root: Path, backend: str | None) -> list[str]:
    """Read the first, middle and last frame of every Episode, plain and with a window of the
    frames before on one camera and the action; returns what stats.json lacks."""
    plain = LeRobotDataset(REPO_ID, root=root, video_backend=backend)
    fps = plain.meta.fps
    camera = plain.meta.camera_keys[0]
    deltas = [-2 / fps, -1 / fps, 0.0]  # [-0.1, 0] isn't a multiple of 1/fps at 15 fps
    windowed = LeRobotDataset(
        REPO_ID,
        root=root,
        video_backend=backend,
        delta_timestamps={camera: deltas, "action": deltas},
    )
    _say(
        f"  loaded: {plain.meta.total_episodes} Episodes, {plain.num_frames} frames, "
        f"{fps} fps, cameras {plain.meta.camera_keys}, decoder {plain._video_backend}"
    )
    problems = _check_stats(plain)
    for problem in problems:
        _say(f"  stats: {problem}")
    read = 0
    for episode in range(plain.meta.total_episodes):
        tasks = list(plain.meta.episodes[episode]["tasks"])
        start, indices = _episode_frames(plain, episode)
        for index in indices:
            item, window = plain[index], windowed[index]
            _check_item(item, plain)
            _check_item(window, windowed, camera, len(deltas))
            if item["task"] not in tasks:
                raise AssertionError(f"frame {index}'s task {item['task']!r} isn't in {tasks}")
            # The window's frames are the frames before, from the video and the data alike.
            before = plain[index - 1] if index > start else item
            if not _same_frame(window[camera][-1], item[camera]) or not _same_frame(
                window[camera][-2], before[camera]
            ):
                raise AssertionError(f"Episode {episode} frame {index}: {camera} window is off")
            if not torch.equal(window["action"][-2], before["action"]):
                raise AssertionError(f"Episode {episode} frame {index}: action window is off")
            read += 2
    _say(f"  read: {read} items, first, middle and last frame of every Episode")
    return problems


def train(root: Path, steps: int, device: str, backend: str | None) -> list[float]:
    """Train ACT for `steps` steps with lerobot-train; returns each logged loss."""
    with tempfile.TemporaryDirectory(prefix="winnow-lerobot-train-") as scratch:
        command = [
            *(sys.executable, "-m", "lerobot.scripts.lerobot_train"),
            f"--dataset.repo_id={REPO_ID}", f"--dataset.root={root}",
            *([f"--dataset.video_backend={backend}"] if backend else []),
            "--policy.type=act", f"--policy.device={device}", "--policy.push_to_hub=false",
            "--policy.chunk_size=10", "--policy.n_action_steps=10",
            f"--steps={steps}", "--batch_size=2", "--num_workers=0", "--log_freq=1",
            "--save_checkpoint=false", "--wandb.enable=false",
            f"--output_dir={Path(scratch) / 'out'}",
        ]  # fmt: skip
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    losses = [float(m) for m in re.findall(r"\bloss:(\d+\.?\d*(?:e[-+]?\d+)?)", output)]
    if result.returncode != 0:
        tail = "\n".join(output.splitlines()[-30:])
        raise RuntimeError(f"lerobot-train exited {result.returncode}:\n{tail}")
    _say(f"  trained: {steps} steps of ACT on {device}, losses {losses}")
    return losses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", type=Path, help="an export folder, or one dataset in it")
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    parser.add_argument("--video-backend", help="torchcodec or pyav (default: LeRobot's)")
    args = parser.parse_args(argv)
    _say(f"lerobot {lerobot.__version__}, torch {torch.__version__}")
    roots = _datasets(args.export.resolve())
    if not roots:
        sys.stderr.write(f"no LeRobot dataset in {args.export}\n")
        return 2
    failed: list[str] = []
    for root in roots:
        info = json.loads((root / "meta" / "info.json").read_text())
        _say(f"{root.name}: {info['total_episodes']} Episodes")
        try:
            problems = read_frames(root, args.video_backend)
            train(root, args.steps, args.device, args.video_backend)
            if problems:
                raise AssertionError(f"stats.json: {len(problems)} problems")
        except Exception as error:  # report every dataset, then fail
            _say(f"  FAILED: {type(error).__name__}: {error}")
            failed.append(root.name)
    _say(f"{len(roots) - len(failed)} of {len(roots)} datasets passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
