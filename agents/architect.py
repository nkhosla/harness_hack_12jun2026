from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from schemas.models import EventRecommendation, Issue, TurnoutSummary, Weather

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"
DEFAULT_EVENT_TIMEOUT_S = 45.0  # one shot per event; no retry

SYSTEM_PROMPT = """\
You are an experienced campaign field and events organizer for local and state races.

Your job is to turn one local issue plus its weather forecast and voter-turnout picture \
into one concrete, credible campaign event proposal. Be specific to the geography and \
issue — generic advice is not useful.

Respond strictly through the provided structured output schema. Every field must be \
grounded in the inputs you receive."""

DRAFT_SYSTEM_PROMPT = (
    "You are a campaign field organizer. Given the details of a planned "
    "community event, write one short, ready-to-send outreach message (a "
    "social post or email body) that a volunteer could send in thirty "
    "seconds. Address the target audience directly, name the issue, include "
    "the venue and date when given, and end with a clear call to action. "
    "Keep it under 80 words. Return ONLY the message text - no preamble, no "
    "subject line, no surrounding quotation marks."
)


class EventIdeation(BaseModel):
    """The Claude-generated portion of an EventRecommendation (task 3.1 output).

    3.2 build_event merges this with issue/area/weather/proposed_date.
    """

    model_config = ConfigDict(extra="forbid")

    format: Literal["indoor", "outdoor"]
    venue_suggestion: str
    target_voters: str
    talking_points: list[str]
    rationale: str


def _build_user_message(
    issue: Issue,
    weather: Weather,
    turnout: TurnoutSummary,
) -> str:
    required_format = weather.recommended_format
    return f"""\
Design one campaign event for the issue, weather, and turnout data below.

## Issue
{issue.model_dump_json(indent=2)}

## Weather
{weather.model_dump_json(indent=2)}

## Turnout
{turnout.model_dump_json(indent=2)}

## Field instructions

- format: MUST be exactly "{required_format}" (matches weather.recommended_format).
- venue_suggestion: Name a specific, plausible venue in {issue.area} suited to a \
{required_format} event (indoor → community center, library, or school cafeteria; \
outdoor → park, plaza, or fairground).
- target_voters: Describe who to mobilize, grounded in turnout.soft_precincts and \
turnout.target_segments.
- talking_points: Provide 3–5 concrete, issue-specific points drawn from issue.summary.
- rationale: Write 1–2 sentences tying issue.salience, turnout opportunity, and weather \
feasibility together."""


def _draft_prompt(event: EventRecommendation) -> str:
    points = "\n".join(f"- {p}" for p in event.talking_points)
    return (
        f"Issue: {event.issue.title}\n"
        f"Summary: {event.issue.summary}\n"
        f"Area: {event.area}\n"
        f"Date: {event.proposed_date.strftime('%A, %B %d')}\n"
        f"Format: {event.format}\n"
        f"Venue: {event.venue_suggestion}\n"
        f"Target voters: {event.target_voters}\n"
        f"Talking points:\n{points}"
    )


async def ideate(
    issue: Issue,
    weather: Weather,
    turnout: TurnoutSummary,
    *,
    client: AsyncAnthropic | None = None,
) -> EventIdeation:
    """Generate the Claude-authored portion of an EventRecommendation."""
    client = client or AsyncAnthropic()
    resp = await client.with_options(timeout=30).messages.parse(
        model=MODEL,
        max_tokens=2000,
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(issue, weather, turnout)}],
        output_format=EventIdeation,
    )
    return resp.parsed_output


async def draft(
    event: EventRecommendation,
    client: AsyncAnthropic | None = None,
) -> EventRecommendation:
    """Generate sendable outreach copy and return a copy with draft_outreach filled."""
    client = client or AsyncAnthropic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=DRAFT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _draft_prompt(event)}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    return event.model_copy(update={"draft_outreach": text})


async def build_events(
    issues: list[Issue],
    *,
    timeout_s: float = DEFAULT_EVENT_TIMEOUT_S,
    builder: Callable[[Issue], Awaitable[EventRecommendation]] | None = None,
) -> list[EventRecommendation]:
    """Fan out one bounded Event Architect per issue; drop failures, keep the slate.

    Each event is bounded by `timeout_s` (one shot, no retry). A timeout or any
    exception in a single build is logged and dropped — never fatal to the slate.
    Result order follows `issues` (minus drops).
    """
    if builder is None:
        try:
            builder = build_event  # WS-3.2, same module  # noqa: F821
        except NameError as e:
            raise RuntimeError(
                "build_events needs build_event (WS-3.2) defined, "
                "or an explicit builder= argument."
            ) from e

    resolved = builder  # bind for the closure

    async def _safe(issue: Issue) -> EventRecommendation | None:
        try:
            return await asyncio.wait_for(resolved(issue), timeout_s)
        except TimeoutError:
            logger.warning("Event build timed out for %s after %.0fs", issue.id, timeout_s)
            return None
        except Exception:  # degrade gracefully — never fatal. (CancelledError still propagates.)
            logger.warning("Event build failed for %s", issue.id, exc_info=True)
            return None

    # No concurrency cap: only ~5 events. Add an asyncio.Semaphore here if fan-out grows.
    results = await asyncio.gather(*(_safe(issue) for issue in issues))
    return [event for event in results if event is not None]


if __name__ == "__main__":
    import sys

    from mocks.fixtures import mock_event, mock_issues

    async def _smoke() -> None:
        issues = mock_issues()  # 5

        async def ok_builder(issue: Issue) -> EventRecommendation:
            return mock_event(issue=issue)

        happy = await build_events(issues, builder=ok_builder)
        assert len(happy) == len(issues), happy
        assert [e.issue.id for e in happy] == [i.id for i in issues]  # order preserved

        async def flaky_builder(issue: Issue) -> EventRecommendation:
            idx = next(n for n, i in enumerate(issues) if i.id == issue.id)
            if idx == 1:
                raise RuntimeError("boom")  # dropped: exception
            if idx == 2:
                await asyncio.sleep(10)  # dropped: exceeds tiny timeout
            return mock_event(issue=issue)

        mixed = await build_events(issues, builder=flaky_builder, timeout_s=0.05)
        assert len(mixed) == len(issues) - 2, mixed
        dropped = {issues[1].id, issues[2].id}
        assert all(e.issue.id not in dropped for e in mixed)

        assert await build_events([], builder=ok_builder) == []  # empty input

        print("OK: build_events smoke passed")

    try:
        asyncio.run(_smoke())
    except AssertionError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
