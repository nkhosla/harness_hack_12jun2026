"""Run-level Guild hooks for api.py integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from guild_adapter.client import GuildClient, GuildSession, NullGuildClient
from guild_adapter.config import GuildConfig, build_guild_client
from guild_adapter.sink import GuildSink, Sink, make_guild_sink

log = logging.getLogger(__name__)

CloseFn = Callable[[str, str | None], Awaitable[None]]
GUILD_TEARDOWN_DRAIN_TIMEOUT_SECONDS = 1.0
_teardown_tasks: set[asyncio.Task[None]] = set()


async def _noop_close(_status: str, _summary: str | None = None) -> None:
    return


def _track_teardown_task(task: asyncio.Task[None]) -> asyncio.Task[None]:
    _teardown_tasks.add(task)
    task.add_done_callback(_teardown_tasks.discard)
    return task


@dataclass
class GuildRunHooks:
    client: GuildClient
    session: GuildSession
    extra_sinks: list[Sink]
    close: CloseFn
    _teardown_task: asyncio.Task[None] | None = field(default=None, repr=False)


def _guild_active(cfg: GuildConfig, client: GuildClient) -> bool:
    return cfg.is_active() and not isinstance(client, NullGuildClient)


def _session_active(session: GuildSession) -> bool:
    return session.id != "null"


async def _close_client(client: GuildClient) -> None:
    aclose = getattr(client, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:
        log.warning("guild client aclose failed", exc_info=True)


async def _guild_teardown(
    guild_sink: GuildSink | None,
    client: GuildClient,
    session: GuildSession,
    cfg: GuildConfig,
    status: str,
    slate_summary: str | None,
) -> None:
    try:
        if guild_sink is not None:
            await guild_sink.shutdown(
                drain_timeout=GUILD_TEARDOWN_DRAIN_TIMEOUT_SECONDS
            )
        if _guild_active(cfg, client) and _session_active(session):
            try:
                await client.close_session(
                    session, status=status, slate_summary=slate_summary
                )
            except Exception:
                log.warning("guild close_session failed", exc_info=True)
    except Exception:
        log.warning("guild teardown failed", exc_info=True)
    finally:
        await _close_client(client)


async def setup_guild_run(
    run_id: str, *, region: str, horizon: str
) -> GuildRunHooks:
    cfg = GuildConfig.from_env()
    client = build_guild_client(cfg)
    session = GuildSession(id="null", run_id=run_id)
    extra_sinks: list[Sink] = []
    guild_sink: GuildSink | None = None

    if _guild_active(cfg, client):
        try:
            session = await client.open_session(run_id, region=region, horizon=horizon)
            if _session_active(session):
                guild_sink = make_guild_sink(client, session)
                extra_sinks = [guild_sink]
            else:
                log.warning(
                    "guild open_session returned inactive session for run=%s; "
                    "proceeding without sink",
                    run_id,
                )
        except Exception:
            log.warning("guild setup failed; proceeding without sink", exc_info=True)
            session = GuildSession(id="null", run_id=run_id)

    hooks = GuildRunHooks(
        client=client,
        session=session,
        extra_sinks=extra_sinks,
        close=_noop_close,
    )

    async def close(status: str, slate_summary: str | None = None) -> None:
        hooks._teardown_task = _track_teardown_task(
            asyncio.create_task(
                _guild_teardown(
                    guild_sink,
                    client,
                    session,
                    cfg,
                    status,
                    slate_summary,
                ),
                name=f"guild-teardown-{run_id}",
            )
        )

    hooks.close = close
    return hooks
