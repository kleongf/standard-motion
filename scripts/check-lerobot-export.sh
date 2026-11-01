#!/usr/bin/env bash
# Opt-in check that an export works with the real `lerobot` library: loads each dataset, reads
# frames with timestamp windows, and trains ACT for 2 steps. Never part of `pnpm verify` or CI.
# `lerobot` (with PyTorch, about 1 GB) runs in a throwaway uv environment, never a dependency.
# See docs/lerobot-export-check.md.
#
#   scripts/check-lerobot-export.sh <export-dir> [--device cpu|mps] [--video-backend pyav]
#   scripts/check-lerobot-export.sh --episodes <new-dir> droid_100:3 droid_1.0.1:1 ... \
#       [-- <check options>]
set -euo pipefail
cd "$(dirname "$0")/.."

LEROBOT="${LEROBOT:-lerobot[training]==0.6.1}"

if [[ "${1:-}" == "--episodes" ]]; then
  # Write these Episodes first, ignoring Triage decisions (see backend/tools/export_episodes.py).
  [[ $# -ge 3 ]] || { echo "usage: $0 --episodes <new-dir> <source:index>..." >&2; exit 2; }
  out="$2"
  shift 2
  ids=()
  while [[ $# -gt 0 && "$1" != "--" ]]; do
    ids+=("$1")
    shift
  done
  [[ "${1:-}" == "--" ]] && shift
  uv run --project backend python backend/tools/export_episodes.py "$out" "${ids[@]}"
  set -- "$out" "$@"
fi

[[ $# -ge 1 ]] || { echo "usage: $0 <export-dir> [check options]" >&2; exit 2; }

# Offline: the dataset is read from its folder, never looked up on the Hub by its repo id.
HF_HUB_OFFLINE=1 uv run --no-project --python 3.13 --with "$LEROBOT" \
  python backend/tools/check_lerobot.py "$@"
