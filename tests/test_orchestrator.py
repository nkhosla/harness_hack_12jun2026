from __future__ import annotations

import pytest

from mocks.fixtures import mock_event, mock_issues, mock_progress_events
from orchestrator import run
from schemas.models import EventRecommendation, Issue, Slate


async def _build_events_dropping_last(issues: list[Issue]) -> list[EventRecommendation]:
    return [mock_event(issue=issue, rank=i) for i, issue in enumerate(issues[:-1])]


@pytest.mark.asyncio
async def test_run_emits_full_sequence() -> None:
    events = []
    slate = await run(
        "Florida HD-21: Marion + Alachua",
        "next 14 days",
        run_id="test-run",
        emit=events.append,
    )

    assert isinstance(slate, Slate) and len(slate.ranked_events) == 5
    assert [e.seq for e in events] == list(range(len(events)))
    assert all(e.run_id == "test-run" for e in events)
    assert events[0].agent == "scout" and events[0].status == "started"
    assert events[-1].agent == "strategist" and events[-1].status == "done"
    assert len(events) == 3 + 4 * len(slate.ranked_events) + 2
    assert slate.ranked_events == sorted(
        slate.ranked_events,
        key=lambda e: e.issue.salience,
        reverse=True,
    )


@pytest.mark.asyncio
async def test_run_without_emit_returns_valid_slate() -> None:
    slate = await run("Florida HD-21", "next 14 days")
    assert isinstance(slate, Slate)
    assert len(slate.ranked_events) == 5
    assert slate.region == "Florida HD-21"
    assert slate.horizon == "next 14 days"


@pytest.mark.asyncio
async def test_run_agent_names_follow_convention() -> None:
    events = []
    await run("Florida HD-21", "next 14 days", emit=events.append)

    scout_events = [e for e in events if e.agent == "scout"]
    architect_events = [e for e in events if e.agent.startswith("architect:")]
    strategist_events = [e for e in events if e.agent == "strategist"]

    assert len(scout_events) == 3
    assert len(architect_events) == 4 * 5
    assert len(strategist_events) == 2
    assert all(e.agent.startswith("architect:issue-") for e in architect_events)


def _statuses_by_agent(events: list) -> dict[str, list[str]]:
    by_agent: dict[str, list[str]] = {}
    for event in events:
        by_agent.setdefault(event.agent, []).append(event.status)
    return by_agent


@pytest.mark.asyncio
async def test_run_event_shape_matches_fixture() -> None:
    run_id = "shape-check"
    live_events = []
    await run("Florida HD-21", "next 14 days", run_id=run_id, emit=live_events.append)
    fixture_events = mock_progress_events(run_id)

    assert len(live_events) == len(fixture_events)
    assert {e.agent for e in live_events} == {e.agent for e in fixture_events}
    assert _statuses_by_agent(live_events) == _statuses_by_agent(fixture_events)


@pytest.mark.asyncio
async def test_run_emits_failed_for_dropped_architects() -> None:
    events = []
    slate = await run(
        "Florida HD-21",
        "next 14 days",
        build_events=_build_events_dropping_last,
        emit=events.append,
    )

    assert len(slate.ranked_events) == 4

    failed = [e for e in events if e.status == "failed"]
    assert len(failed) == 1
    assert failed[0].agent == "architect:issue-transit-005"

    by_agent = _statuses_by_agent(events)
    for agent, statuses in by_agent.items():
        if not agent.startswith("architect:"):
            continue
        assert statuses == ["started", "tool_call", "tool_call", statuses[-1]]
        assert statuses[-1] in ("done", "failed")
