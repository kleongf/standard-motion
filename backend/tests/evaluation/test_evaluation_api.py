"""The evaluation report over fixture Episodes, their Reference labels and Spark alone's samples:
served by a route, returned identically by `winnow eval`, and logged for every Test set run."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.helpers import app_context, ask_visual, track_cleanly, wait_for_job
from winnow.baseline.models import BaselineAnswer
from winnow.baseline.prompts import FROZEN
from winnow.cli import main
from winnow.core.settings import Settings
from winnow.evaluation.models import EvaluationReport, Proportion

FIRST_TRY, NEVER_DROPS = FROZEN.phrases[0], FROZEN.phrases[1]
# Winnow keeps fixture Episode 0, routes 1 to Needs review and rejects 2 (three grasp attempts).
EPISODES = ["droid_100:0", "droid_100:1", "droid_100:2", "droid_100:4"]


def reference_label(
    api: TestClient,
    episode_id: str,
    *fails: str,
    interval: tuple[float, float] = (0.5, 1.0),
    relabel: bool = False,
) -> None:
    phrases = [
        {
            "phrase": p,
            "passed": p not in fails,
            "interval": {"start_s": interval[0], "end_s": interval[1]} if p in fails else None,
        }
        for p in FROZEN.phrases
    ]
    body = {
        "phrases": phrases,
        "elapsed_s": 30,
        "instruction": "Put the block in the bowl",
        "relabel": relabel,
    }
    response = api.post(f"/api/episodes/{episode_id}/reference-labels", json=body)
    assert response.status_code == 201, response.text


def spark_alone(
    api: TestClient,
    episode_id: str,
    *decisions: str | None,
    failure_type: str | None = None,
    times: tuple[float, ...] = (),
) -> None:
    store = app_context(api).baseline
    for sample, decision in enumerate(decisions):
        answer = (
            None
            if decision is None
            else BaselineAnswer(
                decision=decision,  # type: ignore[arg-type]
                failure_type=failure_type,
                time_s=times[sample] if times else None,
                reason="",
                confidence=0.9,
            )
        )
        store.save_sample(
            episode_id, FROZEN.text, sample, answer, "timeout" if not answer else None
        )


def labelled(api: TestClient, set_name: str) -> TestClient:
    job = api.post("/api/episodes/ingest", json={"source": "droid_100", "indices": [0, 1, 2, 4]})
    wait_for_job(api, job.json()["job_id"])
    track_cleanly(api, "droid_100:0")  # kept only once its tracked Criteria can pass
    ask_visual(api)  # Spark sees each object placed on its target
    api.post(f"/api/sets/{set_name}/episodes", json={"episode_ids": EPISODES})
    reference_label(api, "droid_100:0")
    reference_label(api, "droid_100:1", NEVER_DROPS)  # a failure Winnow can't see yet
    reference_label(api, "droid_100:2", FIRST_TRY, interval=(0.0, 2.9))  # the whole Episode
    # droid_100:4 waits for its Reference label, so the report leaves it out.
    spark_alone(api, "droid_100:0", "keep", "keep", "reject")
    # Spark alone says it drops the object, at a median of 0.2 s: 0.3 s before the interval.
    times = (0.0, 0.2, 2.5)
    spark_alone(
        api, "droid_100:1", "reject", "reject", "reject", failure_type=NEVER_DROPS, times=times
    )
    spark_alone(api, "droid_100:2", "keep", "keep", None)
    return api


@pytest.fixture
def test_set(asked_api: TestClient) -> TestClient:
    return labelled(asked_api, "test")


def run(api: TestClient, set_name: str, **body: object) -> dict[str, object]:
    response = api.post("/api/evaluation/runs", json={"set_name": set_name} | body)
    assert response.status_code == 200, response.text
    return response.json()


def rows(report: dict[str, object]) -> dict[str, dict[str, object]]:
    comparison = report["comparison"]
    assert isinstance(comparison, dict)
    return {row["system"]: row for row in comparison["rows"]}  # type: ignore[index]


def interval(count: int, of: int, low: float, high: float) -> dict[str, object]:
    return {
        "count": count,
        "of": of,
        "low": pytest.approx(low, abs=1e-4),
        "high": pytest.approx(high, abs=1e-4),
    }


def test_the_report_scores_only_labelled_episodes_against_their_reference_labels(
    test_set: TestClient,
):
    report = run(test_set, "test")

    assert (report["set_name"], report["rubric_version"]) == ("test", 1)
    assert (report["episodes"], report["labelled"], report["description_failures"]) == (4, 3, 2)
    winnow = rows(report)["winnow"]
    assert (winnow["keeps"], winnow["rejects"], winnow["undecided"]) == (1, 1, 1)
    assert winnow["false_keeps"] == interval(0, 2, 0.0, 0.6576)
    assert winnow["false_rejects"] == interval(0, 1, 0.0, 0.7935)
    assert winnow["coverage"] == interval(2, 3, 0.2077, 0.9385)
    kept = rows(report)["winnow_review_kept"]
    assert (kept["keeps"], kept["rejects"], kept["undecided"]) == (2, 1, 0)
    assert kept["false_keeps"] == interval(1, 2, 0.0945, 0.9055)  # it keeps droid_100:1
    spark = rows(report)["spark_alone"]
    assert (spark["keeps"], spark["rejects"], spark["undecided"]) == (2, 1, 0)
    assert spark["false_keeps"] == interval(1, 2, 0.0945, 0.9055)  # it keeps droid_100:2
    assert spark["false_rejects"] == interval(0, 1, 0.0, 0.7935)


def typed(report: dict[str, object]) -> EvaluationReport:
    return EvaluationReport.model_validate(report)


def counts(p: Proportion | None) -> tuple[int, int] | None:
    return None if p is None else (p.count, p.of)


def test_right_reason_is_scored_at_the_slack_measured_from_the_relabel_pass(
    test_set: TestClient,
):
    # The relabel moves droid_100:1's interval end from 1.0 s to 2.0 s: edges differ by 0 and 1.
    reference_label(test_set, "droid_100:1", NEVER_DROPS, interval=(0.5, 2.0), relabel=True)

    right = typed(run(test_set, "test")).right_reason

    assert right.slack.seconds == pytest.approx(0.95)
    assert (right.slack.edges, right.slack.episodes) == (2, 1)
    rows = {row.system: row for row in right.rows}
    # Winnow rejects droid_100:2 for its grasp attempts, inside the labelled interval.
    assert counts(rows["winnow"].at_slack) == (1, 1)
    spark = rows["spark_alone"]
    assert counts(spark.at_slack) == (1, 1)
    curve = {p.slack_s: p.right for p in spark.curve}
    assert (curve[0.0], curve[0.25], curve[0.5]) == (0, 0, 1)  # 0.3 s early


def test_risk_coverage_ranks_spark_alone_by_sample_agreement(test_set: TestClient):
    curves = {c.system: c for c in typed(run(test_set, "test")).risk_coverage}

    # P_keep = (keeps + 1) / (answers + 2): droid_100:1 0.2, droid_100:2 0.75, droid_100:0 0.6.
    spark = [(p.confidence, p.covered, p.errors) for p in curves["spark_alone"].points]
    assert spark == [(pytest.approx(0.8), 1, 0), (0.75, 2, 1), (0.6, 3, 1)]
    assert curves["winnow"].episodes == 3
    assert curves["winnow"].points[-1].covered == 3


def test_the_report_compares_keep_precision_at_winnows_coverage(test_set: TestClient):
    report = typed(run(test_set, "test"))

    matched = report.matched_coverage
    assert matched.target == 2
    rows = {row.system: row for row in matched.rows}
    assert counts(rows["winnow"].keep_precision) == (1, 1)
    spark = rows["spark_alone"]  # its two most confident: it keeps droid_100:2, a failure
    assert (spark.covered, counts(spark.keep_precision)) == (2, (0, 1))
    m = report.mcnemar
    assert (m.compared, m.winnow_only_right, m.spark_alone_only_right) == (2, 1, 0)

    # (failures, Winnow rejects, Spark alone rejects, too few to score)
    failures = {
        p.phrase: (p.failures, p.winnow_rejects, p.spark_alone_rejects, p.too_few)
        for p in report.phrase_failures
    }
    assert failures[FIRST_TRY] == (1, 1, 0, True)
    assert failures[NEVER_DROPS] == (1, 0, 1, True)


def test_the_cli_returns_the_same_report_as_the_route(
    test_set: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    from_route = run(test_set, "test", rubric_version=1)

    assert main(["eval", "test", "--rubric-version", "1", "--json"], settings=settings) == 0
    assert json.loads(capsys.readouterr().out) == from_route


def test_the_cli_prints_the_comparison_table(
    test_set: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    assert main(["eval", "test"], settings=settings) == 0

    out = capsys.readouterr().out
    assert "Test set · Rubric v1 · 3 of 4 Episodes labelled · 2 description failures" in out
    assert "Spark alone" in out and "1 of 2 (0.09–0.91)" in out
    assert "±" not in out


def test_the_cli_prints_right_reason_matched_coverage_and_failures_per_phrase(
    test_set: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    reference_label(test_set, "droid_100:1", NEVER_DROPS, interval=(0.5, 2.0), relabel=True)

    assert main(["eval", "test"], settings=settings) == 0

    out = capsys.readouterr().out
    assert "Right reason on correct Rejects, at 0.95 s slack" in out
    assert "Winnow 1 of 1 (0.21–1.00) · Spark alone 1 of 1 (0.21–1.00)" in out
    assert "Keep precision at matched coverage (Winnow decides 2 of 3)" in out
    assert "Spark alone 0 of 1 (0.00–0.79), covering 2" in out
    assert (
        "McNemar, on 2 Episodes both decided: only Winnow right 1 · only Spark alone right 0" in out
    )
    assert f"{FIRST_TRY}: 1 failure, Winnow rejects 1, Spark alone 0 (too few to score)" in out


def test_each_test_set_run_appends_one_dated_log_entry(test_set: TestClient, settings: Settings):
    assert test_set.get("/api/evaluation/test-runs").json() == []

    report = run(test_set, "test")
    main(["eval", "test"], settings=settings)

    log = test_set.get("/api/evaluation/test-runs").json()
    assert len(log) == 2
    assert [entry["rubric_version"] for entry in log] == [1, 1]
    assert log[1]["report"] == report  # newest first
    assert log[0]["run_at"] >= log[1]["run_at"]


def test_dev_set_runs_are_not_logged(asked_api: TestClient):
    api = labelled(asked_api, "dev")

    run(api, "dev")

    assert api.get("/api/evaluation/test-runs").json() == []


def test_an_unknown_rubric_version_is_not_found(test_set: TestClient):
    response = test_set.post("/api/evaluation/runs", json={"set_name": "test", "rubric_version": 9})

    assert response.status_code == 404


def fail_first_try(api: TestClient) -> None:
    """Interview and review labels that would reject every labelled Episode they touched."""
    for episode_id, source in zip(EPISODES[:3], ("review", "interview", "review"), strict=True):
        response = api.post(
            f"/api/episodes/{episode_id}/labels",
            json={"phrase": FIRST_TRY, "value": "fail", "source": source},
        )
        assert response.status_code == 201, response.text


def test_interview_and_review_labels_never_touch_test_set_episodes(test_set: TestClient):
    before = run(test_set, "test")

    fail_first_try(test_set)

    assert run(test_set, "test")["comparison"] == before["comparison"]
    assert rows(before)["winnow"]["keeps"] == 1


def test_interview_and_review_labels_apply_to_dev_set_episodes(asked_api: TestClient):
    dev = labelled(asked_api, "dev")
    fail_first_try(dev)

    winnow = rows(run(dev, "dev"))["winnow"]

    assert (winnow["keeps"], winnow["rejects"]) == (0, 3)


def test_the_report_crosses_the_dataset_outcome_and_times_review(test_set: TestClient):
    report = typed(run(test_set, "test"))

    # Fixture Episode 2 ships a failing Dataset outcome, 0 and 1 a success; 1 fails a Phrase.
    outcome = report.dataset_outcome
    assert (outcome.success_meets, outcome.success_fails, outcome.failure_fails) == (1, 1, 1)
    assert [(d.episode_id, d.failed_phrases) for d in outcome.disagreements] == [
        ("droid_100:1", [NEVER_DROPS])
    ]
    # Each label took 30 s; Winnow decided 2 of the 3 Episodes.
    time = report.review_time
    assert (time.minutes_per_episode, time.decided, time.minutes_saved) == (0.5, 2, 1.0)
    assert [row.kind for row in report.tracking_health] == ["wrist", "exterior"]


def test_the_cli_prints_the_ablation_cost_and_dataset_outcome(
    test_set: TestClient, settings: Settings, capsys: pytest.CaptureFixture[str]
):
    assert main(["eval", "test"], settings=settings) == 0

    out = capsys.readouterr().out
    assert "Source ablation ($0, re-scored from the cache)" in out
    assert "  Robot data only (3 of 7 Criteria): " in out
    assert "Cost per 1,000 Episodes (extrapolated from 4 Episodes' cost log)" in out
    assert "Review minutes saved: 0.5 min per Episode x 2 decided automatically = 1.0 min" in out
    assert "  droid_100:1: Dataset success, Reference label fails never drops it" in out
    assert "±" not in out
