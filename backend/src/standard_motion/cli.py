"""`standard-motion`: the pipeline from the command line, for bulk precompute without the browser.

standard-motion ingest droid_100 3 16 42
standard-motion select droid_1.0.1 [--size 300] [--seed 0]
standard-motion sets add dev droid_100:3 droid_100:16 | remove dev droid_100:3
                 | freeze dev [--yes] | show
standard-motion fixtures <dir> [--episodes N]
standard-motion eval test [--rubric-version N] [--json]
standard-motion ask [droid_100:42 ...]  (the latest Rubric's visual Criteria; default every Episode)
standard-motion reasons  (Spark's Reason for every Reject and Needs review whose results changed;
                 run it after `standard-motion ask`, which, unlike the API, doesn't queue them)
standard-motion export <dir> [--include keep|keep_and_review]  (the kept Episodes, or the Keeps
                 and Needs review, as LeRobot datasets, the rest's Reasons beside them)
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import get_args

from standard_motion.core.context import AppContext, build_context
from standard_motion.core.settings import Settings, get_settings
from standard_motion.episodes.droid101 import Droid101
from standard_motion.episodes.fixtures import write_fixture_source
from standard_motion.episodes.service import ingest_items
from standard_motion.evaluation.models import EvaluationRequest
from standard_motion.evaluation.service import UnknownRubricVersionError, run_evaluation
from standard_motion.evaluation.text import report_text
from standard_motion.export.models import Include
from standard_motion.export.service import export_items
from standard_motion.jobs.models import WorkItem
from standard_motion.meta.transport import Transport
from standard_motion.selection.service import sample_indices, selection_items
from standard_motion.sets.models import SET_LABELS, SET_NAMES
from standard_motion.sets.service import (
    FreezeWarningsError,
    SetError,
    add_episodes,
    freeze,
    remove_episode,
)
from standard_motion.triage.reason_service import reason_items
from standard_motion.visual.steps import visual_items


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="standard-motion")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="ingest Episodes into the Dataset")
    ingest.add_argument("source", choices=["droid_100", "droid_1.0.1"])
    ingest.add_argument("indices", nargs="+", type=int)
    select = commands.add_parser("select", help="the droid_1.0.1 selection pass")
    select.add_argument("source", choices=["droid_1.0.1"])
    select.add_argument("--size", type=int, default=300)
    select.add_argument("--seed", type=int, default=0)
    sets = commands.add_parser("sets", help="define and freeze the Dev set and Test set")
    actions = sets.add_subparsers(dest="action", required=True)
    for action in ("add", "remove"):
        change = actions.add_parser(action, help=f"{action} Episodes, e.g. droid_100:42")
        change.add_argument("name", choices=SET_NAMES)
        change.add_argument("episode_ids", nargs="+")
    freeze_set = actions.add_parser("freeze", help="make a set's membership immutable")
    freeze_set.add_argument("name", choices=SET_NAMES)
    freeze_set.add_argument("--yes", action="store_true", help="freeze despite protocol warnings")
    actions.add_parser("show", help="each set's size, frozen state and Episodes")
    fixtures = commands.add_parser("fixtures", help="write synthetic droid_100-layout Episodes")
    fixtures.add_argument("root", type=Path)
    fixtures.add_argument("--episodes", type=int, default=3)
    evaluate = commands.add_parser("eval", help="score Standard Motion and the baselines on a set")
    evaluate.add_argument("set_name", choices=SET_NAMES)
    evaluate.add_argument("--rubric-version", type=int, help="default: the latest")
    evaluate.add_argument("--json", action="store_true", help="the report the route returns")
    ask = commands.add_parser("ask", help="ask Spark the latest Rubric's visual Criteria")
    ask.add_argument("episode_ids", nargs="*", help="default: every ingested Episode")
    commands.add_parser("reasons", help="have Spark write each out-of-date Reason")
    export = commands.add_parser("export", help="write the kept Episodes in LeRobot format")
    export.add_argument("out", type=Path, help="a new or empty folder")
    export.add_argument(
        "--include",
        choices=get_args(Include),
        default="keep",
        help="keep: the Keeps only; keep_and_review: the Needs review Episodes too",
    )
    return parser


async def _run(ctx: AppContext, kind: str, items: list[WorkItem]) -> int:
    job_id = ctx.jobs.create(kind, items)
    await ctx.runner.run(job_id)
    job = ctx.jobs.get(job_id)
    assert job is not None
    for item in job.items:
        note = f" ({item.detail})" if item.detail else ""
        sys.stdout.write(f"{item.label} {item.step}: {item.status}{note}\n")
    sys.stdout.write(f"job {job_id}: {job.done} done, {job.failed} failed\n")
    return 1 if job.failed else 0


def _confirmed(warnings: list[str]) -> bool:
    for warning in warnings:
        sys.stderr.write(f"warning: {warning}\n")
    sys.stderr.write("Frozen is permanent. Freeze anyway? [y/N] ")
    sys.stderr.flush()
    return sys.stdin.readline().strip().lower() in ("y", "yes")


def _freeze(ctx: AppContext, args: argparse.Namespace) -> bool:
    """False when the user declined the protocol warnings."""
    try:
        freeze(ctx.sets, args.name, force=args.yes)
    except FreezeWarningsError as warned:
        if not _confirmed(warned.warnings):
            return False
        freeze(ctx.sets, args.name, force=True)
    return True


def _sets(ctx: AppContext, args: argparse.Namespace) -> int:
    try:
        if args.action == "add":
            add_episodes(ctx.sets, ctx.episodes, args.name, args.episode_ids)
        elif args.action == "remove":
            for episode_id in args.episode_ids:
                remove_episode(ctx.sets, args.name, episode_id)
        elif args.action == "freeze" and not _freeze(ctx, args):
            sys.stderr.write("not frozen\n")
            return 1
    except SetError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    for episode_set in ctx.sets.list():
        frozen = f"frozen {episode_set.frozen_at}" if episode_set.frozen_at else "not frozen"
        label = SET_LABELS[episode_set.name]
        sys.stdout.write(f"{label}: {episode_set.size} Episodes, {frozen}\n")
        if args.action == "show" and episode_set.episode_ids:
            sys.stdout.write(f"  {' '.join(episode_set.episode_ids)}\n")
    return 0


def _eval(ctx: AppContext, args: argparse.Namespace) -> int:
    """The Evaluation page's report; a Test set run is logged like one from the page."""
    request = EvaluationRequest(set_name=args.set_name, rubric_version=args.rubric_version)
    try:
        report = run_evaluation(ctx, request)
    except UnknownRubricVersionError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(f"{report.model_dump_json()}\n" if args.json else report_text(report))
    return 0


def _items(ctx: AppContext, args: argparse.Namespace) -> list[WorkItem]:
    if args.command == "ingest":
        return ingest_items(args.source, args.indices, with_meta=ctx.meta is not None)
    if args.command == "ask":
        ids = args.episode_ids or [e.id for e in ctx.episodes.list()]
        return visual_items(ctx.rubrics.latest(), ids)
    if args.command == "reasons":
        return reason_items(ctx)
    if args.command == "export":
        return export_items(ctx, args.out.resolve(), args.include)
    source = ctx.sources[args.source]
    assert isinstance(source, Droid101)
    sample = sample_indices([*source.index.values()], args.size, args.seed)
    return selection_items(source.name, sample, args.seed)


def main(
    argv: list[str] | None = None,
    settings: Settings | None = None,
    transport: Transport | None = None,
) -> int:
    args = _parser().parse_args(argv)
    if args.command == "fixtures":
        write_fixture_source(args.root, episodes=args.episodes)
        sys.stdout.write(f"wrote {args.episodes} fixture Episodes to {args.root}\n")
        return 0
    ctx = build_context(settings or get_settings(), transport)
    try:
        if args.command == "sets":
            return _sets(ctx, args)
        if args.command == "eval":
            return _eval(ctx, args)
        if args.command in ("select", "ask", "reasons") and ctx.meta is None:
            sys.stderr.write(
                f"`standard-motion {args.command}` calls Spark: set MODEL_API_KEY in .env\n"
            )
            return 2
        return asyncio.run(_run(ctx, args.command, _items(ctx, args)))
    finally:
        ctx.db.close()


if __name__ == "__main__":
    sys.exit(main())
