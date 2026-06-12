"""Orchestration logic for campaign-copilot agents."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from mocks.fixtures import mock_event, mock_issues
from schemas.models import EventRecommendation, Issue, ProgressEvent, Slate


def _load_agent_callable(module_name: str, attr_name: str):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name
        if missing is None:
            raise
        if missing == module_name or module_name.startswith(f"{missing}."):
            return None
        raise
    return getattr(module, attr_name)


_scout_run = _load_agent_callable("agents.scout", "run")
_build_events = _load_agent_callable("agents.architect", "build_events")
_rank = _load_agent_callable("agents.strategist", "rank")

CACHE_VERSION = "1"

EmitFn = Callable[[ProgressEvent], None]
ProgressStatus = Literal["started", "tool_call", "done", "failed"]


class CacheMiss(Exception):
    """Raised when replay mode is active but no cached run exists."""


class _Seq:
    def __init__(self, start: int = 0) -> None:
        self._next = start

    def next(self) -> int:
        value = self._next
        self._next += 1
        return value


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


def _agent_mode(agent_callable) -> str:
    if _use_mocks():
        return "mock"
    return "live" if agent_callable is not None else "mock"


def _agent_modes() -> dict[str, str]:
    return {
        "scout": _agent_mode(_scout_run),
        "architect": _agent_mode(_build_events),
        "strategist": _agent_mode(_rank),
    }


def _run_key(region: str, horizon: str) -> str:
    payload = json.dumps(
        {
            "v": CACHE_VERSION,
            "region": region,
            "horizon": horizon,
            "agent_modes": _agent_modes(),
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


def _replay_events(
    events: list[ProgressEvent],
    run_id: str,
    emit: EmitFn,
) -> None:
    for event in events:
        emit(event.model_copy(update={"run_id": run_id}))


def _emit(
    run_id: str,
    seq: _Seq,
    agent: str,
    status: ProgressStatus,
    detail: str,
    emit: EmitFn,
) -> ProgressEvent:
    event = ProgressEvent(
        run_id=run_id,
        seq=seq.next(),
        agent=agent,
        status=status,
        detail=detail,
    )
    emit(event)
    return event


async def _scout_step(
    region: str,
    run_id: str,
    seq: _Seq,
    emit: EmitFn,
) -> list[Issue]:
    _emit(
        run_id,
        seq,
        "scout",
        "started",
        f"Scanning local news and social signal across {region}",
        emit,
    )
    _emit(
        run_id,
        seq,
        "scout",
        "tool_call",
        "Fetching RSS feeds for Gainesville Sun, Ocala Star-Banner, and WUFT",
        emit,
    )

    if _use_mocks() or _scout_run is None:
        issues = mock_issues()
    else:
        issues = await _scout_run(region)

    _emit(
        run_id,
        seq,
        "scout",
        "done",
        f"Identified {len(issues)} issues across Gainesville, Marion, and Alachua counties",
        emit,
    )
    return issues


async def _architect_step(
    issues: list[Issue],
    run_id: str,
    seq: _Seq,
    emit: EmitFn,
) -> list[EventRecommendation]:
    use_mocks = _use_mocks() or _build_events is None
    recs: list[EventRecommendation] = []

    for issue in issues:
        agent = f"architect:{issue.id}"
        _emit(
            run_id,
            seq,
            agent,
            "started",
            f"Event Architect spinning up for '{issue.title}'",
            emit,
        )
        _emit(
            run_id,
            seq,
            agent,
            "tool_call",
            f"Pulling Jua weather forecast for {issue.area}",
            emit,
        )
        _emit(
            run_id,
            seq,
            agent,
            "tool_call",
            f"Querying turnout history for soft precincts in {issue.area}",
            emit,
        )

    if use_mocks:
        for rank, issue in enumerate(issues):
            recs.append(mock_event(issue=issue, rank=rank))
            agent = f"architect:{issue.id}"
            _emit(
                run_id,
                seq,
                agent,
                "done",
                f"Briefed event recommendation for {issue.area}",
                emit,
            )
    else:
        recs = await _build_events(issues)
        recs_by_issue_id = {rec.issue.id: rec for rec in recs}
        for issue in issues:
            agent = f"architect:{issue.id}"
            if issue.id in recs_by_issue_id:
                _emit(
                    run_id,
                    seq,
                    agent,
                    "done",
                    f"Briefed event recommendation for {issue.area}",
                    emit,
                )
            else:
                _emit(
                    run_id,
                    seq,
                    agent,
                    "failed",
                    f"No event recommendation produced for '{issue.title}'",
                    emit,
                )

    return recs


def _strategist_step(
    recs: list[EventRecommendation],
    region: str,
    horizon: str,
    run_id: str,
    seq: _Seq,
    emit: EmitFn,
) -> Slate:
    _emit(
        run_id,
        seq,
        "strategist",
        "started",
        f"Ranking {len(recs)} event recommendations by salience × turnout opportunity × feasibility",
        emit,
    )

    if _use_mocks() or _rank is None:
        slate = Slate(
            region=region,
            horizon=horizon,
            ranked_events=sorted(recs, key=lambda rec: rec.issue.salience, reverse=True),
        )
    else:
        slate = _rank(recs, region, horizon)

    _emit(
        run_id,
        seq,
        "strategist",
        "done",
        f"Slate ranked: {len(slate.ranked_events)} events ready for review",
        emit,
    )
    return slate


async def run(
    region: str,
    horizon: str,
    *,
    run_id: str | None = None,
    emit: EmitFn | None = None,
) -> Slate:
    run_id = run_id or uuid.uuid4().hex
    emit = emit or (lambda _event: None)
    mode = _cache_mode()
    key = _run_key(region, horizon)

    if mode in ("auto", "replay"):
        cached = _load_cached(key, strict=(mode == "replay"))
        if cached is not None:
            slate, events = cached
            _replay_events(events, run_id, emit)
            return slate
        if mode == "replay":
            raise CacheMiss(
                f"No cached run for region={region!r}, horizon={horizon!r}",
            )

    recorded_events: list[ProgressEvent] = []

    def recording_emit(event: ProgressEvent) -> None:
        recorded_events.append(event)
        emit(event)

    seq = _Seq(0)
    issues = await _scout_step(region, run_id, seq, recording_emit)
    recs = await _architect_step(issues, run_id, seq, recording_emit)
    slate = _strategist_step(recs, region, horizon, run_id, seq, recording_emit)

    if mode != "off":
        _store_cached(key, slate, recorded_events)

    return slate


async def _smoke_test() -> None:
    region = os.environ.get("CAMPAIGN_REGION", "Florida HD-21")
    horizon = os.environ.get("CAMPAIGN_HORIZON", "next two weeks")

    start = time.perf_counter()
    slate1 = await run(region, horizon)
    first_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    slate2 = await run(region, horizon)
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
