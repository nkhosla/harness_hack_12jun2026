from __future__ import annotations

import json

import pytest

import orchestrator
from mocks.fixtures import mock_event, mock_progress_events
from orchestrator import CacheMiss, run
from schemas.models import EventRecommendation, Issue, Slate


@pytest.fixture
def cache_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CAMPAIGN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("CAMPAIGN_USE_MOCKS", raising=False)
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "auto")


async def _build_events_dropping_last(issues: list[Issue]) -> list[EventRecommendation]:
    return [mock_event(issue=issue, rank=i) for i, issue in enumerate(issues[:-1])]


def _statuses_by_agent(events: list) -> dict[str, list[str]]:
    by_agent: dict[str, list[str]] = {}
    for event in events:
        by_agent.setdefault(event.agent, []).append(event.status)
    return by_agent


@pytest.mark.asyncio
async def test_run_emits_full_sequence(cache_env) -> None:
    events = []
    slate = await run(
        "NC HD-50: Caswell + Orange",
        "next 14 days",
        run_id="test-run",
        emit=events.append,
    )

    assert isinstance(slate, Slate) and len(slate.ranked_events) == 5
    assert [event.seq for event in events] == list(range(len(events)))
    assert all(event.run_id == "test-run" for event in events)
    assert events[0].agent == "scout" and events[0].status == "started"
    assert events[-1].agent == "strategist" and events[-1].status == "done"
    assert len(events) == 3 + 4 * len(slate.ranked_events) + 2
    assert slate.ranked_events == sorted(
        slate.ranked_events,
        key=lambda event: event.issue.salience,
        reverse=True,
    )


@pytest.mark.asyncio
async def test_run_without_emit_returns_valid_slate(cache_env) -> None:
    slate = await run("NC HD-50", "next 14 days")
    assert isinstance(slate, Slate)
    assert len(slate.ranked_events) == 5
    assert slate.region == "NC HD-50"
    assert slate.horizon == "next 14 days"


@pytest.mark.asyncio
async def test_run_agent_names_follow_convention(cache_env) -> None:
    events = []
    await run("NC HD-50", "next 14 days", emit=events.append)

    scout_events = [event for event in events if event.agent == "scout"]
    architect_events = [
        event for event in events if event.agent.startswith("architect:")
    ]
    strategist_events = [event for event in events if event.agent == "strategist"]

    assert len(scout_events) == 3
    assert len(architect_events) == 4 * 5
    assert len(strategist_events) == 2
    assert all(event.agent.startswith("architect:issue-") for event in architect_events)


@pytest.mark.asyncio
async def test_run_event_shape_matches_fixture(cache_env) -> None:
    run_id = "shape-check"
    live_events = []
    await run("NC HD-50", "next 14 days", run_id=run_id, emit=live_events.append)
    fixture_events = mock_progress_events(run_id)

    assert len(live_events) == len(fixture_events)
    assert {event.agent for event in live_events} == {
        event.agent for event in fixture_events
    }
    assert _statuses_by_agent(live_events) == _statuses_by_agent(fixture_events)


@pytest.mark.asyncio
async def test_run_emits_failed_for_dropped_architects(cache_env) -> None:
    events = []
    slate = await run(
        "NC HD-50",
        "next 14 days",
        build_events=_build_events_dropping_last,
        emit=events.append,
    )

    assert len(slate.ranked_events) == 4

    failed = [event for event in events if event.status == "failed"]
    assert len(failed) == 1
    assert failed[0].agent == "architect:issue-transit-005"

    by_agent = _statuses_by_agent(events)
    for agent, statuses in by_agent.items():
        if not agent.startswith("architect:"):
            continue
        assert statuses == ["started", "tool_call", "tool_call", statuses[-1]]
        assert statuses[-1] in ("done", "failed")


@pytest.mark.asyncio
async def test_run_returns_schema_valid_slate_on_mocks(cache_env):
    slate = await run("NC HD-50", "next two weeks")

    assert slate.region == "NC HD-50"
    assert slate.horizon == "next two weeks"
    assert len(slate.ranked_events) == 5

    saliences = [event.issue.salience for event in slate.ranked_events]
    assert saliences == sorted(saliences, reverse=True)


@pytest.mark.asyncio
async def test_run_emits_progress_feed(cache_env):
    events = []

    await run("NC HD-50", "next two weeks", emit=events.append)

    assert events
    assert events[0].agent == "scout" and events[0].status == "started"
    assert any(
        event.agent == "scout" and event.status == "done" for event in events
    )

    architect_agents = {
        event.agent for event in events if event.agent.startswith("architect:")
    }
    assert len(architect_agents) == 5

    assert any(
        event.agent == "strategist" and event.status == "done" for event in events
    )

    seq_values = [event.seq for event in events]
    assert seq_values == list(range(len(events)))
    assert all(
        event.status in {"started", "tool_call", "done", "failed"} for event in events
    )


@pytest.mark.asyncio
async def test_second_identical_run_replays_from_cache(cache_env, monkeypatch):
    call_count = 0
    original_scout = orchestrator._scout_step

    async def counting_scout(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_scout(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "_scout_step", counting_scout)

    first = await run("NC HD-50", "next two weeks")
    cache_file = (
        orchestrator._cache_dir()
        / f"{orchestrator._run_key('NC HD-50', 'next two weeks')}.json"
    )
    assert cache_file.is_file()
    assert call_count == 1

    second = await run("NC HD-50", "next two weeks")
    assert second == first
    assert call_count == 1


@pytest.mark.asyncio
async def test_replay_restamps_run_id(cache_env):
    await run("NC HD-50", "next two weeks", run_id="run-a")

    events = []
    await run("NC HD-50", "next two weeks", run_id="run-b", emit=events.append)

    assert events
    assert all(event.run_id == "run-b" for event in events)
    assert [event.seq for event in events] == list(range(len(events)))


@pytest.mark.asyncio
async def test_cache_mode_refresh_recomputes_and_overwrites(cache_env, monkeypatch):
    first = await run("NC HD-50", "next two weeks")

    call_count = 0
    original_scout = orchestrator._scout_step

    async def counting_scout(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_scout(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "_scout_step", counting_scout)
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "refresh")

    second = await run("NC HD-50", "next two weeks")
    assert call_count == 1
    assert second == first


@pytest.mark.asyncio
async def test_cache_mode_off_bypasses_cache(cache_env, monkeypatch):
    await run("NC HD-50", "next two weeks")

    call_count = 0
    original_scout = orchestrator._scout_step

    async def counting_scout(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_scout(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "_scout_step", counting_scout)
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "off")

    await run("NC HD-50", "next two weeks")
    assert call_count == 1


@pytest.mark.asyncio
async def test_cache_mode_replay_raises_on_miss(cache_env, monkeypatch):
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "replay")

    with pytest.raises(CacheMiss):
        await run("NC HD-50", "next two weeks")


@pytest.mark.asyncio
async def test_replay_mode_does_not_create_cache_dir(monkeypatch, tmp_path):
    cache_root = tmp_path / "readonly-cache"
    monkeypatch.setenv("CAMPAIGN_CACHE_DIR", str(cache_root))
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "replay")

    with pytest.raises(CacheMiss):
        await run("NC HD-50", "next two weeks")

    assert not cache_root.exists()


@pytest.mark.asyncio
async def test_auto_mode_recomputes_on_corrupt_cache(cache_env):
    key = orchestrator._run_key("NC HD-50", "next two weeks")
    cache_file = orchestrator._cache_file(key)
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{ not valid json")

    slate = await run("NC HD-50", "next two weeks")

    assert len(slate.ranked_events) == 5
    assert "slate" in json.loads(cache_file.read_text())


@pytest.mark.asyncio
async def test_replay_mode_raises_on_corrupt_cache(cache_env, monkeypatch):
    key = orchestrator._run_key("NC HD-50", "next two weeks")
    cache_file = orchestrator._cache_file(key)
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{ not valid json")
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "replay")

    with pytest.raises(CacheMiss):
        await run("NC HD-50", "next two weeks")


@pytest.mark.asyncio
async def test_custom_pipeline_does_not_replay_default_cache(cache_env):
    await run("NC HD-50", "next two weeks")
    mock_key = orchestrator._run_key("NC HD-50", "next two weeks")
    assert orchestrator._cache_file(mock_key).is_file()

    scout_calls = 0

    async def live_scout(_region: str):
        nonlocal scout_calls
        scout_calls += 1
        from mocks.fixtures import mock_issues

        return mock_issues()

    async def live_build_events(issues):
        from mocks.fixtures import mock_event

        return [mock_event(issue=issue, rank=rank) for rank, issue in enumerate(issues)]

    def live_rank(recs, region, horizon):
        return Slate(
            region=region,
            horizon=horizon,
            ranked_events=sorted(recs, key=lambda rec: rec.issue.salience, reverse=True),
        )

    live_key = orchestrator._run_key(
        "NC HD-50",
        "next two weeks",
        scout=live_scout,
        build_events=live_build_events,
        rank=live_rank,
    )
    assert live_key != mock_key

    await run(
        "NC HD-50",
        "next two weeks",
        scout=live_scout,
        build_events=live_build_events,
        rank=live_rank,
    )

    assert scout_calls == 1
    assert orchestrator._cache_file(live_key).is_file()
    assert orchestrator._cache_file(mock_key).is_file()


@pytest.mark.asyncio
async def test_partial_custom_pipeline_does_not_replay_default_cache(cache_env):
    await run("NC HD-50", "next two weeks")
    mock_key = orchestrator._run_key("NC HD-50", "next two weeks")

    scout_calls = 0

    async def live_scout(_region: str):
        nonlocal scout_calls
        scout_calls += 1
        from mocks.fixtures import mock_issues

        return mock_issues()

    partial_key = orchestrator._run_key(
        "NC HD-50",
        "next two weeks",
        scout=live_scout,
    )
    assert partial_key != mock_key

    await run("NC HD-50", "next two weeks", scout=live_scout)

    assert scout_calls == 1


@pytest.mark.asyncio
async def test_architect_emits_failed_for_dropped_recommendations(cache_env):
    async def partial_build_events(issues):
        return [mock_event(issue=issues[0], rank=0)]

    events = []
    slate = await run(
        "NC HD-50",
        "next two weeks",
        build_events=partial_build_events,
        emit=events.append,
    )

    assert len(slate.ranked_events) == 1

    architect_done = [
        event
        for event in events
        if event.agent.startswith("architect:") and event.status == "done"
    ]
    architect_failed = [
        event
        for event in events
        if event.agent.startswith("architect:") and event.status == "failed"
    ]

    assert len(architect_done) == 1
    assert len(architect_failed) == 4
    assert architect_done[0].agent == "architect:issue-water-001"


@pytest.mark.asyncio
async def test_run_accepts_triple_emit_sink(cache_env):
    events = []

    def emit(agent: str, status: str, detail: str) -> None:
        events.append((agent, status, detail))

    await run("NC HD-50", "next two weeks", emit=emit)

    assert events[0][0] == "scout"
    assert events[0][1] == "started"
    assert events[-1][0] == "strategist"
