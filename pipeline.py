"""Real (non-mock) pipeline wiring: live news + Claude agents + NOAA/turnout tools.

Exposes a `run(region, horizon, emit)` with the same shape as `orchestrator.run`,
but with the real scout/architect/strategist plugged in.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from agents.architect import build_events as _architect_build_events
from agents.architect import draft
from agents.scout import SourceDoc, cluster
from agents.strategist import rank
from orchestrator import EventSink
from orchestrator import run as _orchestrate
from schemas.models import EventRecommendation, Issue, Slate
from tools.news import fetch_news
from tools.turnout import turnout_summary
from tools.weather import get_weather

logger = logging.getLogger(__name__)

_PROPOSED_DATE_OFFSET_DAYS = 5


def _scout_sync(region: str) -> list[Issue]:
    articles = fetch_news(region)
    docs = [SourceDoc(title=a.title, text=a.text, url=a.url) for a in articles]
    return cluster(docs, region)


async def scout(region: str) -> list[Issue]:
    # Sync httpx + anthropic calls; keep them off the event loop so the API
    # stays responsive to polling while a run is in flight.
    return await asyncio.to_thread(_scout_sync, region)


async def build_events(issues: list[Issue]) -> list[EventRecommendation]:
    events = await _architect_build_events(
        issues,
        proposed_date=date.today() + timedelta(days=_PROPOSED_DATE_OFFSET_DAYS),
        get_weather=get_weather,
        get_turnout=turnout_summary,
    )

    async def _safe_draft(event: EventRecommendation) -> EventRecommendation:
        try:
            return await draft(event)
        except Exception:
            logger.warning("Outreach draft failed for %s", event.issue.id, exc_info=True)
            return event

    return list(await asyncio.gather(*(_safe_draft(event) for event in events)))


async def run(
    region: str,
    horizon: str,
    emit: EventSink | None = None,
) -> Slate:
    return await _orchestrate(
        region,
        horizon,
        emit,
        scout=scout,
        build_events=build_events,
        rank=rank,
    )
