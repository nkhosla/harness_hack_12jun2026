"""Guild client protocol and no-op default implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from schemas.models import ProgressEvent

from guild_adapter.manifest import AgentManifest


@dataclass(frozen=True)
class GuildSession:
    id: str
    run_id: str


class GuildClient(Protocol):
    async def register_agents(self, manifest: AgentManifest) -> None: ...

    async def open_session(
        self, run_id: str, *, region: str, horizon: str
    ) -> GuildSession: ...

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None: ...

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None: ...


class NullGuildClient:
    """No-op client used when Guild is disabled or initialization fails."""

    async def register_agents(self, manifest: AgentManifest) -> None:
        return None

    async def open_session(
        self, run_id: str, *, region: str, horizon: str
    ) -> GuildSession:
        return GuildSession(id="null", run_id=run_id)

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        return None

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None:
        return None
