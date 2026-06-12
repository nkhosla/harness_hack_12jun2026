"""File-based Guild client — JSONL escape hatch with zero network risk."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from schemas.models import ProgressEvent

from guild_adapter.client import GuildSession
from guild_adapter.manifest import AgentManifest

log = logging.getLogger(__name__)


class FileGuildClient:
    def __init__(self, output_path: str | Path) -> None:
        self._path = Path(output_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        except Exception:
            log.warning("file guild write failed", exc_info=True)

    async def register_agents(self, manifest: AgentManifest) -> None:
        self._append({"type": "register_agents", "agents": manifest.agents})

    async def open_session(
        self, run_id: str, *, region: str, horizon: str
    ) -> GuildSession:
        session = GuildSession(id=f"file-{run_id}", run_id=run_id)
        self._append(
            {
                "type": "open_session",
                "session_id": session.id,
                "run_id": run_id,
                "region": region,
                "horizon": horizon,
            }
        )
        return session

    async def report_event(
        self, session: GuildSession, event: ProgressEvent
    ) -> None:
        self._append(
            {
                "type": "report_event",
                "session_id": session.id,
                "event": event.model_dump(mode="json"),
            }
        )

    async def close_session(
        self,
        session: GuildSession,
        *,
        status: str,
        slate_summary: str | None = None,
    ) -> None:
        self._append(
            {
                "type": "close_session",
                "session_id": session.id,
                "status": status,
                "slate_summary": slate_summary,
            }
        )
