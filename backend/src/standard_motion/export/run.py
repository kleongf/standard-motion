"""Writing one export an Episode at a time, so its job reports each: `<out>.partial/` fills up
beside `out` and is moved there once complete, so `out` never holds half an export, and a failed
export removes both."""

import shutil
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from standard_motion.episodes.droid100 import Droid100
from standard_motion.episodes.droid101 import Droid101
from standard_motion.episodes.sources import Source
from standard_motion.export.droid100 import Droid100Export
from standard_motion.export.droid101 import Droid101Export
from standard_motion.export.lerobot import ExportSource, LerobotWriter
from standard_motion.export.plan import ExportPlan

REJECTIONS = "rejections.jsonl"
MANIFEST = "manifest.json"  # what the export holds and what it was decided with


class ExportError(Exception):
    pass


def exporter(source: Source) -> ExportSource:
    if isinstance(source, Droid100):
        return Droid100Export(source)
    if isinstance(source, Droid101):
        return Droid101Export(source)
    raise ExportError(f"{source.name} can't be exported")


class ExportRun:
    """One export in progress. Blocking (parquet, ffmpeg): its job runs it off the loop."""

    def __init__(
        self,
        sources: Mapping[str, Source],
        plan: ExportPlan,
        out: Path,
        exporter: Callable[[Source], ExportSource] = exporter,
    ) -> None:
        self.plan, self.out = plan, out
        self._sources, self._exporter = sources, exporter
        self._partial = out.with_name(f"{out.name}.partial")
        self._writers: dict[str, LerobotWriter] = {}
        self._started = False

    def _start(self) -> None:
        if self._started:
            return
        if self.out.exists() and (not self.out.is_dir() or any(self.out.iterdir())):
            raise ExportError(f"{self.out} already exists and isn't empty")
        shutil.rmtree(self._partial, ignore_errors=True)  # left by an interrupted export
        self._partial.mkdir(parents=True)
        self._started = True

    def write(self, source: str, index: int) -> None:
        """The next Episode, which must be `source:index`: they're written in the plan's order."""
        self._start()
        writer = self._writers.get(source)
        if writer is None:
            exported = self._exporter(self._sources[source])
            writer = LerobotWriter(exported, self.plan.kept[source], self._partial / source)
            self._writers[source] = writer
        expected = self.plan.kept[source][writer.written]
        if index != expected:
            raise ExportError(f"{source}:{index} came before {source}:{expected}")
        writer.write()

    def finish(self) -> str:
        """Every source's tables, rejections.jsonl and manifest.json, then the move into `out`;
        returns the export's summary."""
        self._start()
        for writer in self._writers.values():
            writer.finish()
        lines = "".join(f"{r.model_dump_json()}\n" for r in self.plan.rejections)
        (self._partial / REJECTIONS).write_text(lines)
        manifest = self.plan.manifest(datetime.now(UTC)).model_dump_json(indent=2)
        (self._partial / MANIFEST).write_text(manifest + "\n")
        self._partial.replace(self.out)
        return self.plan.summary(str(self.out))

    def discard(self) -> None:
        """After a failure: remove what this export wrote, and `out` if it's still the empty
        folder held for it. An `out` that held something already is left alone."""
        if self._started:
            shutil.rmtree(self._partial, ignore_errors=True)
        if self.out.is_dir() and not any(self.out.iterdir()):
            self.out.rmdir()

    def write_all(self) -> str:
        try:
            for source, index in self.plan.episodes():
                self.write(source, index)
            return self.finish()
        except Exception:
            self.discard()
            raise


def write_export(sources: Mapping[str, Source], plan: ExportPlan, out: Path) -> str:
    return ExportRun(sources, plan, out).write_all()
