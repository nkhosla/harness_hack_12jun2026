from __future__ import annotations

import json

import pytest

import orchestrator
from orchestrator import CacheMiss, run


@pytest.fixture
def cache_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("CAMPAIGN_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("CAMPAIGN_USE_MOCKS", "1")
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "auto")


@pytest.mark.asyncio
async def test_run_returns_schema_valid_slate_on_mocks(cache_env):
    slate = await run("Florida HD-21", "next two weeks")

    assert slate.region == "Florida HD-21"
    assert slate.horizon == "next two weeks"
    assert len(slate.ranked_events) == 5

    saliences = [event.issue.salience for event in slate.ranked_events]
    assert saliences == sorted(saliences, reverse=True)


@pytest.mark.asyncio
async def test_run_emits_progress_feed(cache_env):
    events = []

    await run("Florida HD-21", "next two weeks", emit=events.append)

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
    assert all(event.status in {"started", "tool_call", "done", "failed"} for event in events)


@pytest.mark.asyncio
async def test_second_identical_run_replays_from_cache(cache_env, monkeypatch):
    call_count = 0
    original_scout = orchestrator._scout_step

    async def counting_scout(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_scout(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "_scout_step", counting_scout)

    first = await run("Florida HD-21", "next two weeks")
    cache_file = orchestrator._cache_dir() / f"{orchestrator._run_key('Florida HD-21', 'next two weeks')}.json"
    assert cache_file.is_file()
    assert call_count == 1

    second = await run("Florida HD-21", "next two weeks")
    assert second == first
    assert call_count == 1


@pytest.mark.asyncio
async def test_replay_restamps_run_id(cache_env):
    await run("Florida HD-21", "next two weeks", run_id="run-a")

    events = []
    await run("Florida HD-21", "next two weeks", run_id="run-b", emit=events.append)

    assert events
    assert all(event.run_id == "run-b" for event in events)
    assert [event.seq for event in events] == list(range(len(events)))


@pytest.mark.asyncio
async def test_cache_mode_refresh_recomputes_and_overwrites(cache_env, monkeypatch):
    first = await run("Florida HD-21", "next two weeks")

    call_count = 0
    original_scout = orchestrator._scout_step

    async def counting_scout(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_scout(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "_scout_step", counting_scout)
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "refresh")

    second = await run("Florida HD-21", "next two weeks")
    assert call_count == 1
    assert second == first


@pytest.mark.asyncio
async def test_cache_mode_off_bypasses_cache(cache_env, monkeypatch):
    await run("Florida HD-21", "next two weeks")

    call_count = 0
    original_scout = orchestrator._scout_step

    async def counting_scout(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_scout(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "_scout_step", counting_scout)
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "off")

    await run("Florida HD-21", "next two weeks")
    assert call_count == 1


@pytest.mark.asyncio
async def test_cache_mode_replay_raises_on_miss(cache_env, monkeypatch):
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "replay")

    with pytest.raises(CacheMiss):
        await run("Florida HD-21", "next two weeks")


@pytest.mark.asyncio
async def test_replay_mode_does_not_create_cache_dir(monkeypatch, tmp_path):
    cache_root = tmp_path / "readonly-cache"
    monkeypatch.setenv("CAMPAIGN_CACHE_DIR", str(cache_root))
    monkeypatch.setenv("CAMPAIGN_USE_MOCKS", "1")
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "replay")

    with pytest.raises(CacheMiss):
        await run("Florida HD-21", "next two weeks")

    assert not cache_root.exists()


@pytest.mark.asyncio
async def test_auto_mode_recomputes_on_corrupt_cache(cache_env, monkeypatch):
    key = orchestrator._run_key("Florida HD-21", "next two weeks")
    cache_file = orchestrator._cache_file(key)
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{ not valid json")

    slate = await run("Florida HD-21", "next two weeks")

    assert len(slate.ranked_events) == 5
    assert "slate" in json.loads(cache_file.read_text())


@pytest.mark.asyncio
async def test_replay_mode_raises_on_corrupt_cache(cache_env, monkeypatch):
    key = orchestrator._run_key("Florida HD-21", "next two weeks")
    cache_file = orchestrator._cache_file(key)
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text("{ not valid json")
    monkeypatch.setenv("CAMPAIGN_CACHE_MODE", "replay")

    with pytest.raises(CacheMiss):
        await run("Florida HD-21", "next two weeks")


@pytest.mark.asyncio
async def test_mock_cache_not_replayed_in_live_mode(cache_env, monkeypatch):
    await run("Florida HD-21", "next two weeks")
    mock_key = orchestrator._run_key("Florida HD-21", "next two weeks")
    assert orchestrator._cache_file(mock_key).is_file()

    monkeypatch.delenv("CAMPAIGN_USE_MOCKS", raising=False)

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
        from schemas.models import Slate

        return Slate(
            region=region,
            horizon=horizon,
            ranked_events=sorted(recs, key=lambda rec: rec.issue.salience, reverse=True),
        )

    monkeypatch.setattr(orchestrator, "_scout_run", live_scout)
    monkeypatch.setattr(orchestrator, "_build_events", live_build_events)
    monkeypatch.setattr(orchestrator, "_rank", live_rank)

    live_key = orchestrator._run_key("Florida HD-21", "next two weeks")
    assert live_key != mock_key
    assert orchestrator._agent_modes() == {
        "scout": "live",
        "architect": "live",
        "strategist": "live",
    }

    await run("Florida HD-21", "next two weeks")

    assert scout_calls == 1
    assert orchestrator._cache_file(live_key).is_file()
    assert orchestrator._cache_file(mock_key).is_file()


@pytest.mark.asyncio
async def test_partial_live_does_not_replay_full_mock_cache(cache_env, monkeypatch):
    await run("Florida HD-21", "next two weeks")
    mock_key = orchestrator._run_key("Florida HD-21", "next two weeks")

    monkeypatch.delenv("CAMPAIGN_USE_MOCKS", raising=False)

    scout_calls = 0

    async def live_scout(_region: str):
        nonlocal scout_calls
        scout_calls += 1
        from mocks.fixtures import mock_issues

        return mock_issues()

    monkeypatch.setattr(orchestrator, "_scout_run", live_scout)
    monkeypatch.setattr(orchestrator, "_build_events", None)
    monkeypatch.setattr(orchestrator, "_rank", None)

    partial_key = orchestrator._run_key("Florida HD-21", "next two weeks")
    assert partial_key != mock_key
    assert orchestrator._agent_modes() == {
        "scout": "live",
        "architect": "mock",
        "strategist": "mock",
    }

    await run("Florida HD-21", "next two weeks")

    assert scout_calls == 1


@pytest.mark.asyncio
async def test_architect_emits_failed_for_dropped_recommendations(
    cache_env,
    monkeypatch,
):
    monkeypatch.delenv("CAMPAIGN_USE_MOCKS", raising=False)

    async def live_scout(_region: str):
        from mocks.fixtures import mock_issues

        return mock_issues()

    async def partial_build_events(issues):
        from mocks.fixtures import mock_event

        return [mock_event(issue=issues[0], rank=0)]

    def live_rank(recs, region, horizon):
        from schemas.models import Slate

        return Slate(region=region, horizon=horizon, ranked_events=recs)

    monkeypatch.setattr(orchestrator, "_scout_run", live_scout)
    monkeypatch.setattr(orchestrator, "_build_events", partial_build_events)
    monkeypatch.setattr(orchestrator, "_rank", live_rank)

    events = []
    slate = await run("Florida HD-21", "next two weeks", emit=events.append)

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
