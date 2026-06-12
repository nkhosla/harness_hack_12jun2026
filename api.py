"""FastAPI application entrypoint for campaign-copilot."""

from __future__ import annotations

# WS-4.3 owns run endpoints. When wiring orchestrator.run(), integrate Guild via:
#
#   from guild_adapter import setup_guild_run
#
#   hooks = await setup_guild_run(run_id, region=region, horizon=horizon)
#   emit = make_emitter(run_id, store, extra_sinks=hooks.extra_sinks)
#   try:
#       slate = await run(region, horizon, emit)
#       await hooks.close("completed", slate_summary=f"{len(slate.ranked_events)} events")
#   except Exception:
#       await hooks.close("failed")
#       raise
#
# Guild is never in the request path — failures degrade to NullGuildClient.
