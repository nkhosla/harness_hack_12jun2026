"""End-to-end driver for the real (non-mock) pipeline.

Wires live RSS news -> scout.cluster (Claude) -> architect.build_events
(NOAA weather + turnout data + Claude ideation) -> strategist.rank,
then drafts outreach copy for the top-ranked event.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from dotenv import load_dotenv

from agents.architect import build_events, draft
from agents.scout import SourceDoc, cluster
from agents.strategist import rank
from tools.news import fetch_news
from tools.turnout import turnout_summary
from tools.weather import get_weather

REGION = "NC HD-50"
HORIZON = "next two weeks"

logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s %(message)s")


async def main() -> None:
    load_dotenv()

    print(f"[1/4] scout: fetching news for {REGION} ...")
    articles = fetch_news(REGION)
    print(f"      {len(articles)} articles from {sorted({a.source for a in articles if a.source})}")

    docs = [SourceDoc(title=a.title, text=a.text, url=a.url) for a in articles]
    print(f"[2/4] scout: clustering {len(docs)} docs into issues (Claude) ...")
    issues = cluster(docs, REGION)
    print(f"      {len(issues)} issues:")
    for issue in issues:
        print(f"        - [{issue.salience:.2f}] {issue.title} ({issue.area})")

    proposed = date.today() + timedelta(days=5)
    print(f"[3/4] architect: building events for {proposed} (weather + turnout + Claude) ...")
    events = await build_events(
        issues,
        proposed_date=proposed,
        get_weather=get_weather,
        get_turnout=turnout_summary,
    )
    print(f"      {len(events)}/{len(issues)} events built")

    print("[4/4] strategist: ranking slate ...")
    slate = rank(events, REGION, HORIZON)

    print(f"\n=== SLATE: {slate.region} / {slate.horizon} ===")
    for i, ev in enumerate(slate.ranked_events, 1):
        print(f"\n#{i} {ev.issue.title}")
        print(f"   area: {ev.area} | {ev.format} | {ev.proposed_date}")
        print(f"   weather: {ev.weather.condition}, {ev.weather.temp_f:.0f}F")
        print(f"   venue: {ev.venue_suggestion}")
        print(f"   target: {ev.target_voters}")
        for tp in ev.talking_points:
            print(f"     * {tp}")
        print(f"   rationale: {ev.rationale}")

    if slate.ranked_events:
        top = slate.ranked_events[0]
        print("\n--- drafting outreach for top event ---")
        drafted = await draft(top)
        print(drafted.draft_outreach)


if __name__ == "__main__":
    asyncio.run(main())
