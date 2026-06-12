from __future__ import annotations

from datetime import date

from agents.strategist import rank, score_event
from mocks.fixtures import mock_issues, mock_slate
from schemas.models import EventRecommendation, Slate, Weather


def test_rank_orders_by_salience() -> None:
    shuffled = list(reversed(mock_slate().ranked_events))
    slate = rank(shuffled)
    scores = [score_event(e) for e in slate.ranked_events]
    assert scores == sorted(scores, reverse=True)
    assert slate.ranked_events[0].issue.salience == max(e.issue.salience for e in shuffled)


def test_rank_preserves_all_events() -> None:
    events = mock_slate().ranked_events
    shuffled = list(reversed(events))
    slate = rank(shuffled)
    assert len(slate.ranked_events) == len(events)
    assert {e.issue.id for e in slate.ranked_events} == {e.issue.id for e in events}


def test_score_event_bounded() -> None:
    for event in mock_slate().ranked_events:
        score = score_event(event)
        assert 0.0 <= score <= 1.0


def test_feasibility_indoor_vs_outdoor() -> None:
    issue = mock_issues()[0]
    indoor = EventRecommendation(
        issue=issue.model_copy(deep=True),
        area=issue.area,
        proposed_date=date(2026, 6, 15),
        weather=Weather(
            summary="Heavy rain",
            condition="rain",
            temp_f=75.0,
            precip_chance=0.9,
            recommended_format="indoor",
        ),
        format="indoor",
        venue_suggestion="Community center",
        target_voters="Test voters",
        talking_points=["Point one"],
        rationale="Test rationale",
    )
    outdoor = indoor.model_copy(
        update={
            "format": "outdoor",
            "weather": indoor.weather.model_copy(
                update={"recommended_format": "outdoor"}
            ),
        }
    )
    assert score_event(indoor) > score_event(outdoor)


def test_rank_empty_list() -> None:
    slate = rank([])
    assert isinstance(slate, Slate)
    assert slate.ranked_events == []


def test_rank_is_deterministic() -> None:
    events = list(reversed(mock_slate().ranked_events))
    first = rank(events)
    second = rank(events)
    assert [e.issue.id for e in first.ranked_events] == [
        e.issue.id for e in second.ranked_events
    ]
