"""Orchestration logic for campaign-copilot agents."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from mocks.fixtures import mock_event, mock_issues
from schemas.models import EventRecommendation, Issue, ProgressEvent, Slate

CACHE_VERSION = "1"

ProgressStatus = Literal["started", "tool_call", "done", "failed"]
EventSink = Callable[..., None]
ScoutFn = Callable[[str], Any]
BuildEventsFn = Callable[[list[Issue]], Any]
RankFn = Callable[[list[EventRecommendation], str, str], Slate]


class CacheMiss(Exception):
    """Raised when replay mode is active but no cached run exists."""


class _Emitter:
    def __init__(self, run_id: str, sink: EventSink | None) -> None:
        self.run_id = run_id
        self.seq = 0
        self.sink = sink
        self._sink_accepts_event: bool | None = None

    def _send(self, event: ProgressEvent) -> None:
        if self.sink is None:
            return
        if self._sink_accepts_event is not False:
            try:
                self.sink(event)
                self._sink_accepts_event = True
                return
            except TypeError:
                if self._sink_accepts_event is True:
                    raise
                self._sink_accepts_event = False
        self.sink(event.agent, event.status, event.detail)

    def emit(self, agent: str, status: ProgressStatus, detail: str) -> ProgressEvent:
        event = ProgressEvent(
            run_id=self.run_id,
            seq=self.seq,
            agent=agent,
            status=status,
            detail=detail,
        )
        self.seq += 1
        self._send(event)
        return event

    def replay(self, event: ProgressEvent) -> ProgressEvent:
        replayed = event.model_copy(update={"run_id": self.run_id})
        self.seq = max(self.seq, replayed.seq + 1)
        self._send(replayed)
        return replayed


def _mock_scout(region: str) -> list[Issue]:
    return mock_issues()


async def _mock_build_events(issues: list[Issue]) -> list[EventRecommendation]:
    return [mock_event(issue=issue, rank=i) for i, issue in enumerate(issues)]


def _mock_rank(events: list[EventRecommendation], region: str, horizon: str) -> Slate:
    ranked = sorted(events, key=lambda event: event.issue.salience, reverse=True)
    return Slate(region=region, horizon=horizon, ranked_events=ranked)


async def _invoke(fn: Callable[..., Any], /, *args: Any) -> Any:
    result = fn(*args)
    if inspect.isawaitable(result):
        return await result
    return result


def _cache_root() -> Path:
    return Path(os.environ.get("CAMPAIGN_CACHE_DIR", ".cache/runs"))


def _cache_file(key: str) -> Path:
    return _cache_root() / f"{key}.json"


def _ensure_cache_dir() -> None:
    _cache_root().mkdir(parents=True, exist_ok=True)


def _cache_dir() -> Path:
    """Return the cache directory, creating it if needed (write path only)."""
    _ensure_cache_dir()
    return _cache_root()


def _cache_mode() -> str:
    return os.environ.get("CAMPAIGN_CACHE_MODE", "auto")


def _use_mocks() -> bool:
    return os.environ.get("CAMPAIGN_USE_MOCKS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _callable_id(fn: Callable[..., Any]) -> str:
    module = getattr(fn, "__module__", type(fn).__module__)
    qualname = getattr(fn, "__qualname__", type(fn).__qualname__)
    return f"{module}.{qualname}"


def _run_key(
    region: str,
    horizon: str,
    *,
    scout: ScoutFn = _mock_scout,
    build_events: BuildEventsFn = _mock_build_events,
    rank: RankFn = _mock_rank,
) -> str:
    payload = json.dumps(
        {
            "v": CACHE_VERSION,
            "region": region,
            "horizon": horizon,
            "pipeline": {
                "scout": _callable_id(scout),
                "architect": _callable_id(build_events),
                "strategist": _callable_id(rank),
            },
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_cached(
    key: str,
    *,
    strict: bool = False,
) -> tuple[Slate, list[ProgressEvent]] | None:
    path = _cache_file(key)
    if not path.is_file():
        return None

    try:
        data = json.loads(path.read_text())
        slate = Slate.model_validate(data["slate"])
        events = [ProgressEvent.model_validate(event) for event in data["events"]]
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
        if strict:
            raise CacheMiss(
                f"Cached run at {path} is missing or invalid",
            ) from exc
        return None

    return slate, events


def _store_cached(key: str, slate: Slate, events: list[ProgressEvent]) -> None:
    payload = {
        "slate": json.loads(slate.model_dump_json()),
        "events": [json.loads(event.model_dump_json()) for event in events],
    }
    _ensure_cache_dir()
    _cache_file(key).write_text(json.dumps(payload, indent=2))


def _replay_events(events: list[ProgressEvent], emitter: _Emitter) -> None:
    for event in events:
        emitter.replay(event)


async def _scout_step(
    region: str,
    emitter: _Emitter,
    scout: ScoutFn,
) -> list[Issue]:
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

    issues = await _invoke(scout, region)

    emitter.emit(
        "scout",
        "done",
        f"Identified {len(issues)} issues across {region}",
    )
    return issues


async def _architect_step(
    issues: list[Issue],
    emitter: _Emitter,
    build_events: BuildEventsFn,
) -> list[EventRecommendation]:
    for issue in issues:
        agent = f"architect:{issue.id}"
        emitter.emit(agent, "started", f"Event Architect spinning up for '{issue.title}'")
        emitter.emit(agent, "tool_call", f"Pulling Jua weather forecast for {issue.area}")
        emitter.emit(
            agent,
            "tool_call",
            f"Querying turnout history for soft precincts in {issue.area}",
        )

    events = await _invoke(build_events, issues)
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

    return events


def _strategist_step(
    events: list[EventRecommendation],
    region: str,
    horizon: str,
    emitter: _Emitter,
    rank: RankFn,
) -> Slate:
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


async def run(
    region: str,
    horizon: str,
    emit: EventSink | None = None,
    *,
    run_id: str | None = None,
    scout: ScoutFn | None = None,
    build_events: BuildEventsFn | None = None,
    rank: RankFn | None = None,
) -> Slate:
    run_id = run_id or uuid.uuid4().hex
    emitter = _Emitter(run_id, emit)

    if _use_mocks():
        scout_fn = _mock_scout
        build_events_fn = _mock_build_events
        rank_fn = _mock_rank
    else:
        scout_fn = scout or _mock_scout
        build_events_fn = build_events or _mock_build_events
        rank_fn = rank or _mock_rank

    mode = _cache_mode()
    key = _run_key(
        region,
        horizon,
        scout=scout_fn,
        build_events=build_events_fn,
        rank=rank_fn,
    )

    if mode in ("auto", "replay"):
        cached = _load_cached(key, strict=(mode == "replay"))
        if cached is not None:
            slate, events = cached
            _replay_events(events, emitter)
            return slate
        if mode == "replay":
            raise CacheMiss(
                f"No cached run for region={region!r}, horizon={horizon!r}",
            )

    recorded_events: list[ProgressEvent] = []
    original_send = emitter._send

    def recording_send(event: ProgressEvent) -> None:
        recorded_events.append(event)
        original_send(event)

    emitter._send = recording_send

    try:
        issues = await _scout_step(region, emitter, scout_fn)
        events = await _architect_step(issues, emitter, build_events_fn)
        slate = _strategist_step(events, region, horizon, emitter, rank_fn)
    except Exception as exc:
        emitter.emit("orchestrator", "failed", str(exc))
        raise

    if mode != "off":
        _store_cached(key, slate, recorded_events)

    return slate


async def _smoke_test() -> None:
    region = os.environ.get("CAMPAIGN_REGION", "Florida HD-21")
    horizon = os.environ.get("CAMPAIGN_HORIZON", "next two weeks")

    start = time.perf_counter()
    slate1 = await run(region, horizon, run_id="smoke-a")
    first_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    slate2 = await run(region, horizon, run_id="smoke-b")
    second_elapsed = time.perf_counter() - start

    print(f"Run 1 (record): {first_elapsed:.3f}s")
    print(f"Run 2 (replay): {second_elapsed:.3f}s")
    print(
        f"Slate: {len(slate1.ranked_events)} ranked events for "
        f"{slate1.region} / {slate1.horizon}",
    )
    print(f"Replay identical: {slate1 == slate2}")


if __name__ == "__main__":
    asyncio.run(_smoke_test())
