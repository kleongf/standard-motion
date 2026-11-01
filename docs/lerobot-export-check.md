# Checking an export with real LeRobot

The tests read exports with pyarrow and Winnow's own readers. `scripts/check-lerobot-export.sh` checks an export with the real `lerobot` library instead. It is opt-in and never part of `pnpm verify` or CI.

For each dataset in an export folder (`droid_100/`, `droid_1.0.1/`), it:

1. loads `LeRobotDataset(repo_id="local/winnow-export", root=<dataset>)`;
2. checks that `meta/stats.json` has min, max, mean, std, count and q01–q99 for every non-text feature, shaped like the feature (cameras `(3, 1, 1)`);
3. reads the first, middle and last frame of every Episode, with every camera's image. It reads each frame twice: once plain, and once with `delta_timestamps` of `[-2/fps, -1/fps, 0]` on one camera and the action. Decoding enforces LeRobot's 1e-4 s timestamp tolerance. The check also confirms that each window holds the frames before it and that the task matches the Episode's;
4. trains ACT for 2 steps with `lerobot-train` (`--policy.chunk_size=10`, batch size 2), on MPS when available, else CPU.

The issue asked for `[-0.1, 0]`. LeRobot rejects any delta that isn't a multiple of 1/fps, and DROID runs at 15 fps, so the check uses whole frames instead.

## Run it

```sh
# an export the app or `winnow export` wrote
scripts/check-lerobot-export.sh data/exports/<stamp>

# or write chosen Episodes first, then check them
DATA_DIR=/tmp/winnow-check scripts/check-lerobot-export.sh --episodes /tmp/winnow-check/export \
  droid_100:3 droid_100:16 droid_1.0.1:1 droid_1.0.1:9
```

Options after the export folder (after `--` when using `--episodes`):

- `--device cpu|mps`
- `--video-backend torchcodec|pyav` (default: LeRobot's, which is torchcodec on Apple silicon)
- `--steps N`

It exits non-zero if any dataset fails. To try another LeRobot release, set `LEROBOT='lerobot[training]==X.Y.Z'`.

**`--episodes` ignores Triage decisions.** The app and `winnow export` export Episodes by decision: the Keeps, or with Keep + Needs review (`--include keep_and_review`) the Needs review Episodes too. With no Spark or tracks, most real Episodes end up Needs review, so Keep only would export nothing. This mode lets you check the format on real Episodes anyway. It calls the exporter directly through `backend/tools/export_episodes.py`, which exists only for this check and is not part of the app. It builds no app context, so it uses no database and makes no Meta API calls. droid_100 is downloaded into `$DATA_DIR/droid_100`, and droid_1.0.1 is range-read from the Hub. Point `DATA_DIR` at a scratch folder to keep it out of your real data.

## Cost

`lerobot[training]` and PyTorch (CPU and MPS wheels, no CUDA) are installed into uv's cache through `uv run --with`. They take about 1 GB and are never added to `pyproject.toml`. The first run also downloads ResNet-18 weights (45 MB) to `~/.cache/torch`. After that, a check of a few Episodes per source takes under a minute.

On macOS you may see `objc[…]: Class AVF… is implemented in both …` warnings. They appear because PyAV and torchcodec each load their own FFmpeg. They are harmless.

## Last run

lerobot 0.6.1 and torch 2.11.0, on 2026-10-31. The export held 5 real droid_100 Episodes (3, 16, 42, 48, 49: 1,100 frames, AV1) and 4 real droid_1.0.1 Episodes (1, 9, 17, 1500: 1,003 frames, AV1 stream copies). Both datasets loaded, all 54 items were read with no timestamp-tolerance error, and both trained for 2 steps:

| dataset     | torchcodec, MPS: loss | pyav, CPU: loss |
| ----------- | --------------------- | --------------- |
| droid_100   | 84.2 → 66.1           | 92.9 → 72.0     |
| droid_1.0.1 | 81.9 → 79.0           | 85.9 → 77.3     |

The first run found one format bug. droid_100's `stats.json` had no camera stats, so `lerobot-train` failed with a `KeyError` while setting ImageNet stats on each camera. Cameras whose source has no stats now get them from the exported clip, computed as LeRobot's `compute_episode_stats` does (`export/video_stats.py`). On those 5 Episodes, the computed stats match the Hub's own per-Episode stats for droid_100 to within 0.01.
