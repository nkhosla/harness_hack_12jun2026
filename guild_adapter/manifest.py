"""Static agent identity manifest for Guild registration (stretch)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentManifest:
    agents: list[dict[str, str]] = field(default_factory=list)


DEFAULT_MANIFEST = AgentManifest(
    agents=[
        {"name": "scout", "role": "Issue discovery and local signal scanning"},
        {"name": "architect", "role": "Per-issue event recommendation architect"},
        {"name": "strategist", "role": "Slate ranking and campaign prioritization"},
    ]
)
