"""HTTP client for Guild control plane — wire details localized here."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from schemas.models import ProgressEvent

from guild_adapter.client import GuildSession
from guild_adapter.config import GuildConfig
from guild_adapter.manifest import AgentManifest

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(2.0)

# CONFIRM AGAINST GUILD DOCS AT INTEGRATION — provisional
_STATUS_TO_GUILD: dict[str, str] = {
    "started": "span_start",
    "tool_call": "tool_call",
    "done": "span_end",
    "failed": "span_error",
}


def _auth_headers(cfg: GuildConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }


def _event_payload(session: GuildSession, event: ProgressEvent) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "run_id": event.run_id,
        "seq": event.seq,
        "agent": event.agent,
        "status": event.status,
        "guild_status": _STATUS_TO_GUILD.get(event.status, event.status),
        "detail": event.detail,
    }


class HttpGuildClient:
    def __init__(self, cfg: GuildConfig) -> None:
        self._cfg = cfg
        self._client = httpx.AsyncClient(
            base_url=cfg.base_url.rstrip("/"),
            headers=_auth_headers(cfg),
            timeout=_TIMEOUT,
        )

    async def register_agents(self, manifest: AgentManifest) -> None:
        try:
            response = await self._client.post(
                f"/v1/workspaces/{self._cfg.workspace}/agents",
                json={"agents": manifest.agents},
            )
            response.raise_for_status()
        except Exception:
            log.warning("guild register_agents failed", exc_info=True)

    async def open_session(
        self, run_id: str, *, region: str, horizon: str
    ) -> GuildSession:
        try:
            response = await self._client.post(
                f"/v1/workspaces/{self._cfg.workspace}/sessions",
                json={"run_id": run_id, "region": region, "horizon": horizon},
            )
            response.raise_for_status()
            data = response.json()
            return GuildSession(id=str(data.get("id", run_id)), run_id=run_id)
        except Exception:
            log.warning("guild open_session failed for run=%s", run_id, exc_info=True)
            return GuildSession(id="null", run_id=run_id)

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        try:
            response = await self._client.post(
                f"/v1/workspaces/{self._cfg.workspace}/sessions/{session.id}/events",
                json=_event_payload(session, event),
            )
            response.raise_for_status()
        except Exception:
            log.warning(
                "guild report_event failed for run=%s seq=%s",
                event.run_id,
                event.seq,
                exc_info=True,
            )

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None:
        try:
            payload: dict[str, Any] = {"status": status}
            if slate_summary is not None:
                payload["slate_summary"] = slate_summary
            response = await self._client.post(
                f"/v1/workspaces/{self._cfg.workspace}/sessions/{session.id}/close",
                json=payload,
            )
            response.raise_for_status()
        except Exception:
            log.warning(
                "guild close_session failed for session=%s", session.id, exc_info=True
            )

    async def aclose(self) -> None:
        await self._client.aclose()
