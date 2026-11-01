"""For the LeRobot format check only (scripts/check-lerobot-export.sh): write the Episodes named
on the command line as an export, with the exporter the app uses, ignoring Triage decisions.

The app and `winnow export` only export Episodes by decision. This tool exists so the format can
be checked on real Episodes before any are kept; it isn't part of the app and never should be.
It builds no app context: no database, no Meta API.

    uv run --project backend python backend/tools/export_episodes.py <new-dir> \\
        droid_100:3 droid_100:16 droid_1.0.1:1
"""

import argparse
import sys
from pathlib import Path

from winnow.core.settings import get_settings
from winnow.episodes.sources import sources_from
from winnow.export.plan import ExportPlan
from winnow.export.run import write_export


def _kept(episode_ids: list[str]) -> dict[str, list[int]]:
    kept: dict[str, list[int]] = {}
    for episode_id in episode_ids:
        source, _, index = episode_id.rpartition(":")
        kept.setdefault(source, []).append(int(index))
    return {source: sorted(set(indices)) for source, indices in kept.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="a new or empty folder")
    parser.add_argument("episode_ids", nargs="+", help="e.g. droid_100:3 droid_1.0.1:1")
    args = parser.parse_args(argv)
    kept = _kept(args.episode_ids)
    sources = sources_from(get_settings())
    unknown = sorted(set(kept) - set(sources))
    if unknown:
        sys.stderr.write(f"unknown source {unknown[0]}: one of {', '.join(sources)}\n")
        return 2
    plan = ExportPlan(kept=kept, rejections=[], unlabelled=0, test_set=0, rubric_version=0, s=1.0)
    write_export(sources, plan, args.out.resolve())
    sys.stdout.write(f"wrote {sum(map(len, kept.values()))} Episodes to {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
