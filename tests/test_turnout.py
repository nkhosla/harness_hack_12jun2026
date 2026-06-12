import pytest

from schemas.models import TurnoutSummary
from tools.turnout import load_turnout, turnout_summary


def test_load_turnout_has_expected_demo_scope() -> None:
    df = load_turnout()
    assert set(df["county"]) == {"CASWELL", "ORANGE"}
    assert set(df["election_date"]) == {"2020-11-03", "2022-11-08", "2024-11-05"}
    assert len(df) == 148


def test_turnout_summary_supports_counties_and_hd50() -> None:
    orange = turnout_summary("Orange", n_soft=3)
    caswell = turnout_summary("Caswell", n_soft=3)
    hd50 = turnout_summary("HD-50", n_soft=3)

    for summary in (orange, caswell, hd50):
        assert isinstance(summary, TurnoutSummary)
        assert len(summary.soft_precincts) == 3
        assert "presidential-only voters" in " ".join(summary.target_segments)
        assert "registered" in summary.notes

    assert orange.area == "Orange"
    assert caswell.area == "Caswell"
    assert hd50.area == "HD-50"


def test_turnout_summary_accepts_numeric_district() -> None:
    assert turnout_summary("50", n_soft=2).soft_precincts == turnout_summary(
        "HD-50",
        n_soft=2,
    ).soft_precincts


def test_turnout_summary_rejects_unknown_area() -> None:
    with pytest.raises(ValueError, match="no turnout data"):
        turnout_summary("Durham")


@pytest.mark.parametrize("n_soft", [0, -1])
def test_turnout_summary_rejects_non_positive_soft_count(n_soft: int) -> None:
    with pytest.raises(ValueError, match="n_soft must be >= 1"):
        turnout_summary("Orange", n_soft=n_soft)


def test_low_turnout_segment_checks_selected_soft_precincts() -> None:
    one_soft = turnout_summary("Orange", n_soft=1)
    assert "low-turnout precincts below area median" in one_soft.target_segments
