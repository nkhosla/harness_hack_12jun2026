"""Guild configuration and client factory."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from guild_adapter.client import GuildClient, NullGuildClient

log = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True)
class GuildConfig:
    enabled: bool = False
    api_key: str = ""
    workspace: str = ""
    base_url: str = "https://api.guild.ai"

    @classmethod
    def from_env(cls) -> GuildConfig:
        enabled_raw = os.getenv("GUILD_ENABLED", "").strip().lower()
        return cls(
            enabled=enabled_raw in _TRUTHY,
            api_key=os.getenv("GUILD_API_KEY", "").strip(),
            workspace=os.getenv("GUILD_WORKSPACE", "").strip(),
            base_url=os.getenv("GUILD_BASE_URL", "https://api.guild.ai").strip()
            or "https://api.guild.ai",
        )

    def is_active(self) -> bool:
        return self.enabled and bool(self.api_key) and bool(self.workspace)


def build_guild_client(cfg: GuildConfig | None = None) -> GuildClient:
    cfg = cfg or GuildConfig.from_env()
    if not cfg.is_active():
        return NullGuildClient()
    try:
        from guild_adapter.http_client import HttpGuildClient

        return HttpGuildClient(cfg)
    except Exception:
        log.warning("Guild init failed; using NullGuildClient", exc_info=True)
        return NullGuildClient()
