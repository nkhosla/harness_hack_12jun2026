"""Guild.ai passive progress mirror for campaign-copilot runs."""

from guild_adapter.client import GuildClient, GuildSession, NullGuildClient
from guild_adapter.config import GuildConfig, build_guild_client
from guild_adapter.file_client import FileGuildClient
from guild_adapter.http_client import HttpGuildClient
from guild_adapter.integration import GuildRunHooks, setup_guild_run
from guild_adapter.manifest import DEFAULT_MANIFEST, AgentManifest
from guild_adapter.sink import GuildSink, Sink, make_guild_sink

__all__ = [
    "AgentManifest",
    "DEFAULT_MANIFEST",
    "FileGuildClient",
    "GuildClient",
    "GuildConfig",
    "GuildSink",
    "GuildRunHooks",
    "GuildSession",
    "HttpGuildClient",
    "NullGuildClient",
    "Sink",
    "build_guild_client",
    "make_guild_sink",
    "setup_guild_run",
]
