"""Orchestration logic for campaign-copilot agents."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from mocks.fixtures import mock_event, mock_issues
from schemas.models import EventRecommendation, Issue, ProgressEvent, Slate

ProgressStatus = Literal["started", "tool_call", "done", "failed"]
EventSink = Callable[[ProgressEvent], None]


class _Emitter:
    def __init__(self, run_id: str, sink: EventSink | None) -> None:
        self.run_id = run_id
        self.seq = 0
        self.sink = sink

    def emit(self, agent: str, status: ProgressStatus, detail: str) -> ProgressEvent:
        evt = ProgressEvent(
            run_id=self.run_id,
            seq=self.seq,
            agent=agent,
            status=status,
            detail=detail,
        )
        self.seq += 1
        if self.sink is not None:
            self.sink(evt)
        return evt


def _mock_scout(region: str) -> list[Issue]:
    return mock_issues()


async def _mock_build_events(issues: list[Issue]) -> list[EventRecommendation]:
    return [mock_event(issue=issue, rank=i) for i, issue in enumerate(issues)]


def _mock_rank(events: list[EventRecommendation], region: str, horizon: str) -> Slate:
    ranked = sorted(events, key=lambda e: e.issue.salience, reverse=True)
    return Slate(region=region, horizon=horizon, ranked_events=ranked)


async def run(
    region: str,
    horizon: str,
    *,
    run_id: str = "local",
    emit: EventSink | None = None,
    scout: Callable[[str], list[Issue]] = _mock_scout,
    build_events: Callable[[list[Issue]], Awaitable[list[EventRecommendation]]] = _mock_build_events,
    rank: Callable[[list[EventRecommendation], str, str], Slate] = _mock_rank,
) -> Slate:
    emitter = _Emitter(run_id, emit)
    try:
        emitter.emit(
            "scout",
            "started",
            f"Scanning local news and social signal across {region}",
        )
        emitter.emit(
            "scout",
            "tool_call",
            f"Fetching local news + social feeds for {region}",
        )
        issues = scout(region)
        emitter.emit(
            "scout",
            "done",
            f"Identified {len(issues)} issues across {region}",
        )

        for issue in issues:
            agent = f"architect:{issue.id}"
            emitter.emit(agent, "started", f"Event Architect spinning up for '{issue.title}'")
            emitter.emit(agent, "tool_call", f"Pulling Jua weather forecast for {issue.area}")
            emitter.emit(
                agent,
                "tool_call",
                f"Querying turnout history for soft precincts in {issue.area}",
            )

        events = await build_events(issues)
        events_by_issue = {event.issue.id: event for event in events}

        for issue in issues:
            agent = f"architect:{issue.id}"
            event = events_by_issue.get(issue.id)
            if event is not None:
                emitter.emit(agent, "done", f"Briefed event recommendation for {event.issue.area}")
            else:
                emitter.emit(
                    agent,
                    "failed",
                    f"Failed to brief event recommendation for {issue.area}",
                )

        emitter.emit(
            "strategist",
            "started",
            f"Ranking {len(events)} event recommendations by salience × turnout opportunity × feasibility",
        )
        slate = rank(events, region, horizon)
        emitter.emit(
            "strategist",
            "done",
            f"Slate ranked: {len(slate.ranked_events)} events ready for {region}",
        )
        return slate
    except Exception as exc:
        emitter.emit("orchestrator", "failed", str(exc))
        raise


if __name__ == "__main__":
    events: list[ProgressEvent] = []
    slate = asyncio.run(
        run(
            "Florida HD-21: Marion + Alachua",
            "next 14 days",
            run_id="smoke",
            emit=events.append,
        )
    )
    assert isinstance(slate, Slate) and len(slate.ranked_events) == 5
    assert [e.seq for e in events] == list(range(len(events)))
    assert all(e.run_id == "smoke" for e in events)
    assert events[0].agent == "scout" and events[0].status == "started"
    assert events[-1].agent == "strategist" and events[-1].status == "done"
    assert len(events) == 3 + 4 * len(slate.ranked_events) + 2
    assert slate.ranked_events == sorted(
        slate.ranked_events,
        key=lambda e: e.issue.salience,
        reverse=True,
    )
    print(f"smoke ok: {len(events)} events, {len(slate.ranked_events)} ranked")
