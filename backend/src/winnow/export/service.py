"""The export as a job: a work item per exported Episode, in order, then one that writes the
tables, rejections.jsonl (the Reason for each Episode decided and left out) and manifest.json, so
the job shows each Episode's progress. Which Episodes, see plan.py; how, see run.py. The Test set
is never exported, its Reasons neither.

An export's plan is fixed when its job is made, and its run kept here, by folder, while the job
runs: the runner is in-process, and a job left by a process that's gone fails as interrupted."""

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from winnow.core.context import AppContext
from winnow.export.models import Include
from winnow.export.plan import export_plan
from winnow.export.run import ExportError, ExportRun
from winnow.jobs.models import Step, WorkItem

_RUNS: dict[str, ExportRun] = {}  # out folder -> its run, while its job runs


def export_kept(ctx: AppContext, out: Path, include: Include = "keep") -> str:
    """The export, written at once (blocking)."""
    return ExportRun(ctx.sources, export_plan(ctx, include), out).write_all()


def _run(args: Mapping[str, object]) -> ExportRun:
    run = _RUNS.get(str(args["out"]))
    if run is None:
        raise ExportError("this export's plan is gone: export again")
    return run


async def _discarding_on_failure[T](run: ExportRun, work: Callable[[], T]) -> T:
    """Do one item's work off the loop; if it fails, the export is over: the items after it are
    skipped, so its folders go now."""
    try:
        return await asyncio.to_thread(work)
    except Exception:  # cancelled, its thread may still be writing: left as interrupted
        _RUNS.pop(str(run.out), None)
        run.discard()
        raise


def export_steps() -> dict[str, Step]:
    async def episode(args: Mapping[str, object]) -> None:
        run = _run(args)
        source, index = str(args["source"]), int(str(args["index"]))
        await _discarding_on_failure(run, lambda: run.write(source, index))

    async def finish(args: Mapping[str, object]) -> str:
        run = _run(args)
        summary = await _discarding_on_failure(run, run.finish)
        _RUNS.pop(str(run.out), None)
        return summary

    return {"export_episode": episode, "export_finish": finish}


def export_items(ctx: AppContext, out: Path, include: Include = "keep") -> list[WorkItem]:
    """Plan the export to `out` (on the loop: it reads the database) and hold its run for the
    items: one per Episode, each after the one before, then the finish."""
    run = ExportRun(ctx.sources, export_plan(ctx, include), out)
    _RUNS[str(out)] = run
    args = {"out": str(out)}
    items = [
        WorkItem("export_episode", args | {"source": source, "index": index}, f"{source}:{index}",
                 after=i - 1 if i else None)
        for i, (source, index) in enumerate(run.plan.episodes())
    ]  # fmt: skip
    finish = WorkItem("export_finish", args, "Tables and manifest", after=len(items) - 1)
    return [*items, finish if items else WorkItem("export_finish", args, finish.label)]


def start_export(ctx: AppContext, include: Include = "keep") -> int:
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
    try:
        items = export_items(ctx, out, include)
    except Exception:
        out.rmdir()
        raise
    return ctx.runner.submit("export", items)
