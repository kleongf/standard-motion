"""The in-process asyncio job runner. A queue can replace it later by consuming the same work
items; the steps don't change."""

import asyncio
from collections.abc import Callable, Mapping

from winnow.jobs.models import Step, WorkItem
from winnow.jobs.store import JobStore


class JobRunner:
    def __init__(self, store: JobStore, steps: Mapping[str, Step], concurrency: int = 4) -> None:
        self._store = store
        self._steps = steps
        self._slots = asyncio.Semaphore(concurrency)
        self._tasks: set[asyncio.Task[None]] = set()

    def submit(
        self, kind: str, items: list[WorkItem], then: Callable[[], object] | None = None
    ) -> int:
        """Record the job and start it in the background, calling `then` once it finishes;
        returns its id."""
        job_id = self._store.create(kind, items)
        task = asyncio.create_task(self._run_then(job_id, then))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def _run_then(self, job_id: int, then: Callable[[], object] | None) -> None:
        await self.run(job_id)
        if then is not None:
            then()

    async def run(self, job_id: int) -> None:
        """Run every queued item of a job; one failing item never stops the others, but an item
        waits for the one it comes `after`, and is skipped if that one fails."""
        items = self._store.queued(job_id)
        finished = {pos: asyncio.Event() for pos, _ in items}
        succeeded: set[int] = set()
        labels = {pos: item.label for pos, item in items}

        async def run_one(position: int, item: WorkItem) -> None:
            try:
                if item.after in finished:
                    await finished[item.after].wait()
                    if item.after not in succeeded:
                        skipped = f"skipped: {labels[item.after]} failed"
                        self._store.set_status(job_id, position, "failed", skipped)
                        return
                if await self._run_item(job_id, position, item):
                    succeeded.add(position)
            finally:
                finished[position].set()

        await asyncio.gather(*(run_one(pos, item) for pos, item in items))

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _run_item(self, job_id: int, position: int, item: WorkItem) -> bool:
        async with self._slots:
            self._store.set_status(job_id, position, "running", None)
            try:
                detail = await self._steps[item.step](item.args)
            except asyncio.CancelledError:
                self._store.set_status(job_id, position, "failed", "interrupted; run it again")
                raise
            except Exception as error:  # the item fails; the job goes on
                self._store.set_status(job_id, position, "failed", f"{error}")
                return False
            self._store.set_status(job_id, position, "done", detail)
            return True
