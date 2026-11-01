"""The export: every kept Episode (see plan.py for which), written per source as a LeRobot v3.0
dataset, with the Reason for each one not kept in rejections.jsonl and, in manifest.json, where
each kept Episode came from and what decided it. The Test set is never exported, its Reasons
neither."""

import asyncio
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from winnow.core.context import AppContext
from winnow.episodes.droid100 import Droid100
from winnow.episodes.droid101 import Droid101
from winnow.episodes.sources import Source
from winnow.export.droid100 import Droid100Export
from winnow.export.droid101 import Droid101Export
from winnow.export.lerobot import ExportSource, write_lerobot
from winnow.export.plan import ExportPlan, export_plan
from winnow.jobs.models import Step, WorkItem

REJECTIONS = "rejections.jsonl"
MANIFEST = "manifest.json"  # what the export holds and what it was decided with


class ExportError(Exception):
    pass


def _exporter(source: Source) -> ExportSource:
    if isinstance(source, Droid100):
        return Droid100Export(source)
    if isinstance(source, Droid101):
        return Droid101Export(source)
    raise ExportError(f"{source.name} can't be exported")


def write_export(sources: Mapping[str, Source], plan: ExportPlan, out: Path) -> None:
    """Blocking (parquet, ffmpeg). Written beside `out` and moved there once complete, so `out`
    never holds half an export."""
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ExportError(f"{out} already exists and isn't empty")
    partial = out.with_name(f"{out.name}.partial")
    shutil.rmtree(partial, ignore_errors=True)  # left by an export that was interrupted
    partial.mkdir(parents=True)
    for name, indices in plan.kept.items():
        write_lerobot(_exporter(sources[name]), indices, partial / name)
    lines = "".join(f"{r.model_dump_json()}\n" for r in plan.rejections)
    (partial / REJECTIONS).write_text(lines)
    manifest = plan.manifest(datetime.now(UTC)).model_dump_json(indent=2)
    (partial / MANIFEST).write_text(manifest + "\n")
    partial.replace(out)


def export_kept(ctx: AppContext, out: Path) -> str:
    plan = export_plan(ctx)
    write_export(ctx.sources, plan, out)
    return plan.summary(str(out))


def export_step(ctx: AppContext) -> Step:
    async def step(args: Mapping[str, object]) -> str:
        out = Path(str(args["out"]))
        plan = export_plan(ctx)  # reads the database, so on the loop
        await asyncio.to_thread(write_export, ctx.sources, plan, out)
        return plan.summary(str(out))

    return step


def export_items(out: Path) -> list[WorkItem]:
    return [WorkItem("export", {"out": str(out)}, "Kept Episodes")]


def start_export(ctx: AppContext) -> int:
    """Export in the background to a new folder under the data dir's exports/, made empty now
    so no other export takes its name."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    exports = ctx.settings.data_dir / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    out, taken = exports / stamp, 1
    while True:
        try:
            out.mkdir()
            break
        except FileExistsError:
            taken += 1
            out = exports / f"{stamp}-{taken}"
    return ctx.runner.submit("export", export_items(out))
