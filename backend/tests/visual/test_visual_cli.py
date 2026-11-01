"""`winnow ask`: the latest Rubric's visual Criteria asked from the command line."""

import pytest

from tests.visual.scripted import ScriptedVisual
from winnow.cli import main
from winnow.core.settings import Settings


def test_the_cli_asks_the_latest_rubrics_visual_criteria(
    settings: Settings, capsys: pytest.CaptureFixture[str]
):
    spark = ScriptedVisual()
    assert main(["ingest", "droid_100", "0"], settings=settings, transport=spark) == 0

    assert main(["ask"], settings=settings, transport=spark) == 0

    out = capsys.readouterr().out
    assert "droid_100:0 placed-on-target crop: done" in out
    assert "droid_100:0 placed-on-target visual: done" in out
    assert len(spark.calls) == 3


def test_asking_needs_the_meta_api(settings: Settings, capsys: pytest.CaptureFixture[str]):
    assert main(["ask"], settings=settings) == 2
    assert "MODEL_API_KEY" in capsys.readouterr().err
