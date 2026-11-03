"""The exports written under the data dir's exports/, newest first, read from their manifests: a
folder without one is an export still being written, or one from before manifests."""

from pathlib import Path

from pydantic import ValidationError

from standard_motion.export.models import Manifest, PastExport
from standard_motion.export.run import MANIFEST


def past_exports(exports: Path) -> list[PastExport]:
    found: list[PastExport] = []
    manifests: list[Path] = sorted(exports.glob(f"*/{MANIFEST}")) if exports.is_dir() else []
    for path in manifests:
        try:
            manifest = Manifest.model_validate_json(path.read_text())
        except (OSError, ValidationError):
            continue
        found.append(
            PastExport(
                path=str(path.parent),
                created_at=manifest.created_at,
                episodes=len(manifest.exported),
                include=manifest.include,
            )
        )
    return sorted(found, key=lambda e: e.created_at, reverse=True)
