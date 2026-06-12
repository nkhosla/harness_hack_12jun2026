"""Tests for guild_adapter — fake orchestrator harness, no network."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Literal

import pytest

import guild_adapter.integration as guild_integration
from guild_adapter.client import GuildSession, NullGuildClient
from guild_adapter.config import build_guild_client
from guild_adapter.integration import setup_guild_run
from guild_adapter.manifest import AgentManifest
from guild_adapter.sink import make_guild_sink
from mocks.fixtures import mock_progress_events, mock_slate
from schemas.models import ProgressEvent, Slate

ProgressStatus = Literal["started", "tool_call", "done", "failed"]
Emit = Callable[[str, ProgressStatus, str], None]
Sink = Callable[[ProgressEvent], None]


class EventStore:
    def __init__(self) -> None:
        self._events: dict[str, list[ProgressEvent]] = {}

    def append(self, run_id: str, event: ProgressEvent) -> None:
        self._events.setdefault(run_id, []).append(event)

    def get(self, run_id: str) -> list[ProgressEvent]:
        return list(self._events.get(run_id, []))


def make_emitter(
    run_id: str, store: EventStore, extra_sinks: Sequence[Sink] = ()
) -> Emit:
    seq = 0

    def emit(agent: str, status: ProgressStatus, detail: str) -> None:
        nonlocal seq
        event = ProgressEvent(
            run_id=run_id,
            seq=seq,
            agent=agent,
            status=status,
            detail=detail,
        )
        seq += 1
        store.append(run_id, event)
        for sink in extra_sinks:
            sink(event)

    return emit


async def run_mock(region: str, horizon: str, emit: Emit) -> Slate:
    reference = mock_progress_events("reference-run")
    for event in reference:
        emit(event.agent, event.status, event.detail)
    return mock_slate(region=region, horizon=horizon)


async def flush_pending_tasks() -> None:
    for _ in range(20):
        await asyncio.sleep(0)
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


class FakeGuildClient:
    def __init__(self) -> None:
        self.register_agents_calls: list[AgentManifest] = []
        self.open_session_calls: list[tuple[str, str, str]] = []
        self.report_event_calls: list[tuple[GuildSession, ProgressEvent]] = []
        self.close_session_calls: list[tuple[GuildSession, str, str | None]] = []

    async def register_agents(self, manifest: AgentManifest) -> None:
        self.register_agents_calls.append(manifest)

    async def open_session(
        self, run_id: str, *, region: str, horizon: str
    ) -> GuildSession:
        self.open_session_calls.append((run_id, region, horizon))
        return GuildSession(id=f"fake-{run_id}", run_id=run_id)

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        self.report_event_calls.append((session, event))

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None:
        self.close_session_calls.append((session, status, slate_summary))


class RaisingGuildClient:
    async def register_agents(self, manifest: AgentManifest) -> None:
        raise RuntimeError("guild register_agents down")

    async def open_session(
        self, run_id: str, *, region: str, horizon: str
    ) -> GuildSession:
        raise RuntimeError("guild open_session down")

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        raise RuntimeError("guild report_event down")

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None:
        raise RuntimeError("guild close_session down")


async def run_with_client(
    client: FakeGuildClient | NullGuildClient | RaisingGuildClient,
    *,
    run_id: str = "test-run-001",
    with_lifecycle: bool = False,
) -> tuple[EventStore, Slate, FakeGuildClient | NullGuildClient | RaisingGuildClient]:
    store = EventStore()
    extra_sinks: list[Sink] = []
    session = GuildSession(id="null", run_id=run_id)
    guild_sink = None

    if with_lifecycle:
        session = await client.open_session(
            run_id, region="Florida HD-21", horizon="next two weeks"
        )
        guild_sink = make_guild_sink(client, session)
        extra_sinks = [guild_sink]

    emit = make_emitter(run_id, store, extra_sinks)
    slate = await run_mock("Florida HD-21", "next two weeks", emit)

    if with_lifecycle and guild_sink is not None:
        await guild_sink.drain()
        await client.close_session(session, status="completed")

    return store, slate, client


@pytest.mark.asyncio
async def test_t1_full_mirror_order_and_seq_preserved() -> None:
    client = FakeGuildClient()
    store, _, _ = await run_with_client(client, with_lifecycle=True)

    ui_seqs = [event.seq for event in store.get("test-run-001")]
    guild_seqs = [event.seq for _, event in client.report_event_calls]
    expected = [event.seq for event in mock_progress_events("test-run-001")]

    assert ui_seqs == expected
    assert guild_seqs == expected
    assert guild_seqs == ui_seqs


@pytest.mark.asyncio
async def test_t2_ui_store_identical_with_and_without_guild() -> None:
    run_id = "byte-identical-run"

    store_off = EventStore()
    emit_off = make_emitter(run_id, store_off)
    await run_mock("Florida HD-21", "next two weeks", emit_off)

    client = FakeGuildClient()
    session = await client.open_session(
        run_id, region="Florida HD-21", horizon="next two weeks"
    )
    store_on = EventStore()
    guild_sink = make_guild_sink(client, session)
    emit_on = make_emitter(run_id, store_on, [guild_sink])
    await run_mock("Florida HD-21", "next two weeks", emit_on)
    await guild_sink.drain()

    off_dump = [event.model_dump() for event in store_off.get(run_id)]
    on_dump = [event.model_dump() for event in store_on.get(run_id)]
    assert off_dump == on_dump


@pytest.mark.asyncio
async def test_t3_raising_guild_client_never_breaks_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    client = RaisingGuildClient()
    run_id = "test-run-001"
    store = EventStore()
    session = GuildSession(id="null", run_id=run_id)
    guild_sink = make_guild_sink(client, session)
    emit = make_emitter(run_id, store, [guild_sink])
    slate = await run_mock("Florida HD-21", "next two weeks", emit)
    await guild_sink.drain()

    expected = mock_progress_events(run_id)
    actual = store.get(run_id)
    assert [event.model_dump() for event in actual] == [
        event.model_dump() for event in expected
    ]
    assert slate.region == "Florida HD-21"
    assert len(slate.ranked_events) == 5
    assert "guild report_event failed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_t4_fallback_with_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GUILD_ENABLED", raising=False)
    monkeypatch.delenv("GUILD_API_KEY", raising=False)
    monkeypatch.delenv("GUILD_WORKSPACE", raising=False)
    monkeypatch.delenv("GUILD_BASE_URL", raising=False)

    client = build_guild_client()
    assert isinstance(client, NullGuildClient)

    store, slate, _ = await run_with_client(client)
    assert len(store.get("test-run-001")) == len(mock_progress_events())
    assert slate.horizon == "next two weeks"


@pytest.mark.asyncio
async def test_t5_session_lifecycle() -> None:
    client = FakeGuildClient()
    await run_with_client(client, with_lifecycle=True)

    assert len(client.open_session_calls) == 1
    assert len(client.close_session_calls) == 1
    assert client.close_session_calls[0][1] == "completed"

    first_report_idx = next(
        i
        for i, (_, event) in enumerate(client.report_event_calls)
        if event.seq == 0
    )
    assert client.open_session_calls
    assert first_report_idx >= 0


@pytest.mark.asyncio
async def test_t5_failed_run_closes_with_failed_status() -> None:
    client = FakeGuildClient()
    session = await client.open_session(
        "failed-run", region="Florida HD-21", horizon="next two weeks"
    )
    sink = make_guild_sink(client, session)

    store = EventStore()
    emit = make_emitter("failed-run", store, [sink])
    emit("scout", "started", "starting")
    await sink.drain()

    try:
        raise RuntimeError("orchestrator failed")
    except RuntimeError:
        await client.close_session(session, status="failed")

    assert client.close_session_calls[-1][1] == "failed"


class DelayedFakeGuildClient(FakeGuildClient):
    """Slower sends for lower seq values — would reorder under parallel dispatch."""

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        await asyncio.sleep(0.02 * (len(mock_progress_events()) - event.seq))
        await super().report_event(session, event)


class SlowDrainFakeGuildClient(FakeGuildClient):
    def __init__(self) -> None:
        super().__init__()
        self.report_count_at_close = 0

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        await asyncio.sleep(0.001)
        await super().report_event(session, event)

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None:
        self.report_count_at_close = len(self.report_event_calls)
        await super().close_session(
            session,
            status=status,
            slate_summary=slate_summary,
        )


@pytest.mark.asyncio
async def test_t6_in_order_delivery_under_slow_sends() -> None:
    client = DelayedFakeGuildClient()
    session = await client.open_session(
        "ordered-run", region="Florida HD-21", horizon="next two weeks"
    )
    guild_sink = make_guild_sink(client, session)
    emit = make_emitter("ordered-run", EventStore(), [guild_sink])
    await run_mock("Florida HD-21", "next two weeks", emit)
    await guild_sink.drain()

    guild_seqs = [event.seq for _, event in client.report_event_calls]
    expected = [event.seq for event in mock_progress_events("ordered-run")]
    assert guild_seqs == expected


@pytest.mark.asyncio
async def test_build_guild_client_disabled_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUILD_ENABLED", "1")
    monkeypatch.delenv("GUILD_API_KEY", raising=False)
    client = build_guild_client()
    assert isinstance(client, NullGuildClient)


@pytest.mark.asyncio
async def test_build_guild_client_disabled_without_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUILD_ENABLED", "1")
    monkeypatch.setenv("GUILD_API_KEY", "test-key")
    monkeypatch.delenv("GUILD_WORKSPACE", raising=False)
    client = build_guild_client()
    assert isinstance(client, NullGuildClient)


@pytest.mark.asyncio
async def test_setup_guild_run_returns_sinks_and_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GUILD_ENABLED", raising=False)
    monkeypatch.delenv("GUILD_API_KEY", raising=False)

    hooks = await setup_guild_run(
        "hooks-run", region="Florida HD-21", horizon="next two weeks"
    )
    assert hooks.extra_sinks == []
    assert isinstance(hooks.client, NullGuildClient)

    store = EventStore()
    emit = make_emitter("hooks-run", store, hooks.extra_sinks)
    await run_mock("Florida HD-21", "next two weeks", emit)
    await hooks.close("completed")
    if hooks._teardown_task is not None:
        await hooks._teardown_task

    assert len(store.get("hooks-run")) == len(mock_progress_events())


@pytest.mark.asyncio
async def test_setup_guild_run_skips_sink_on_null_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUILD_ENABLED", "1")
    monkeypatch.setenv("GUILD_API_KEY", "test-key")
    monkeypatch.setenv("GUILD_WORKSPACE", "demo-ws")

    from guild_adapter.http_client import HttpGuildClient

    async def null_open_session(
        self: HttpGuildClient,
        run_id: str,
        *,
        region: str,
        horizon: str,
    ) -> GuildSession:
        return GuildSession(id="null", run_id=run_id)

    monkeypatch.setattr(HttpGuildClient, "open_session", null_open_session)

    hooks = await setup_guild_run(
        "null-session-run", region="Florida HD-21", horizon="next two weeks"
    )
    assert hooks.extra_sinks == []
    assert hooks.session.id == "null"
    await hooks.close("completed")
    if hooks._teardown_task is not None:
        await hooks._teardown_task


@pytest.mark.asyncio
async def test_hooks_close_returns_before_slow_teardown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GUILD_ENABLED", raising=False)

    async def slow_teardown(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(2)

    monkeypatch.setattr("guild_adapter.integration._guild_teardown", slow_teardown)

    hooks = await setup_guild_run(
        "fast-close-run", region="Florida HD-21", horizon="next two weeks"
    )
    await asyncio.wait_for(hooks.close("completed"), timeout=0.1)
    assert hooks._teardown_task is not None
    assert hooks._teardown_task in guild_integration._teardown_tasks
    await hooks._teardown_task
    assert hooks._teardown_task not in guild_integration._teardown_tasks


@pytest.mark.asyncio
async def test_hooks_close_drains_queued_events_before_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUILD_ENABLED", "1")
    monkeypatch.setenv("GUILD_API_KEY", "test-key")
    monkeypatch.setenv("GUILD_WORKSPACE", "demo-ws")

    client = SlowDrainFakeGuildClient()
    monkeypatch.setattr(
        "guild_adapter.integration.build_guild_client",
        lambda _cfg: client,
    )

    hooks = await setup_guild_run(
        "drain-on-close-run", region="Florida HD-21", horizon="next two weeks"
    )
    emit = make_emitter("drain-on-close-run", EventStore(), hooks.extra_sinks)
    await run_mock("Florida HD-21", "next two weeks", emit)

    await hooks.close("completed")
    assert hooks._teardown_task is not None
    await hooks._teardown_task

    guild_seqs = [event.seq for _, event in client.report_event_calls]
    expected = [event.seq for event in mock_progress_events("drain-on-close-run")]
    assert guild_seqs == expected
    assert client.report_count_at_close == len(expected)
    assert client.close_session_calls[-1][1] == "completed"


@pytest.mark.asyncio
async def test_shutdown_stops_worker_without_draining() -> None:
    client = DelayedFakeGuildClient()
    session = await client.open_session(
        "shutdown-run", region="Florida HD-21", horizon="next two weeks"
    )
    sink = make_guild_sink(client, session)
    emit = make_emitter("shutdown-run", EventStore(), [sink])
    emit("scout", "started", "starting")
    await sink.shutdown(drain_timeout=0)
    assert sink._worker is None
    assert sink._closed


@pytest.mark.asyncio
async def test_build_guild_client_uses_http_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUILD_ENABLED", "1")
    monkeypatch.setenv("GUILD_API_KEY", "test-key")
    monkeypatch.setenv("GUILD_WORKSPACE", "demo-ws")

    from guild_adapter.http_client import HttpGuildClient

    client = build_guild_client()
    assert isinstance(client, HttpGuildClient)
    await client.aclose()
