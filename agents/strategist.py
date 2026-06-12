from __future__ import annotations

from schemas.models import EventRecommendation, Slate, TurnoutSummary

# Tunables — kept as module constants so they're easy to find/adjust during the demo.
INDOOR_FEASIBILITY = 0.9  # indoor events are weather-proof; the architect already adapted to weather
DEFAULT_REGION = "NC HD-50"
DEFAULT_HORIZON = "next two weeks"


def _feasibility(event: EventRecommendation) -> float:
    # Indoor = weatherproof. Outdoor = penalized by rain risk.
    if event.format == "indoor":
        return INDOOR_FEASIBILITY
    return max(0.0, 1.0 - event.weather.precip_chance)


def _turnout_opportunity(
    event: EventRecommendation,
    turnout_lookup: dict[str, TurnoutSummary] | None,
) -> float:
    # EventRecommendation has no structured turnout; use an optional lookup, else neutral 1.0.
    if not turnout_lookup:
        return 1.0
    summary = turnout_lookup.get(event.area)
    if summary is None:
        return 1.0
    raw = 0.2 * len(summary.soft_precincts) + 0.1 * len(summary.target_segments)
    return min(1.0, raw)  # bounded to [0,1]


def score_event(
    event: EventRecommendation,
    turnout_lookup: dict[str, TurnoutSummary] | None = None,
) -> float:
    return (
        event.issue.salience
        * _turnout_opportunity(event, turnout_lookup)
        * _feasibility(event)
    )


def rank(
    events: list[EventRecommendation],
    region: str = DEFAULT_REGION,
    horizon: str = DEFAULT_HORIZON,
    turnout_lookup: dict[str, TurnoutSummary] | None = None,
) -> Slate:
    ordered = sorted(
        events,
        key=lambda e: (
            -score_event(e, turnout_lookup),
            -e.issue.salience,
            e.proposed_date,
            e.issue.id,
        ),
    )
    return Slate(region=region, horizon=horizon, ranked_events=ordered)


if __name__ == "__main__":
    from mocks.fixtures import mock_slate

    shuffled = list(reversed(mock_slate().ranked_events))
    slate = rank(shuffled)

    assert isinstance(slate, Slate)
    assert len(slate.ranked_events) == len(shuffled)

    scores = [score_event(e) for e in slate.ranked_events]
    assert scores == sorted(scores, reverse=True)
    assert slate.ranked_events[0].issue.id == max(shuffled, key=lambda e: e.issue.salience).issue.id

    for event in slate.ranked_events:
        score = score_event(event)
        assert 0.0 <= score <= 1.0

    print(f"Slate: {slate.region} · {slate.horizon}\n")
    for i, event in enumerate(slate.ranked_events, start=1):
        print(
            f"{i}. {event.issue.title[:50]:50} · "
            f"{event.area[:30]:30} · "
            f"salience={event.issue.salience:.2f} · "
            f"score={score_event(event):.3f}"
        )
