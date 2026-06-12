from __future__ import annotations

import asyncio
from typing import Literal

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from schemas.models import Issue, TurnoutSummary, Weather

load_dotenv()

SYSTEM_PROMPT = """\
You are an experienced campaign field and events organizer for local and state races.

Your job is to turn one local issue plus its weather forecast and voter-turnout picture \
into one concrete, credible campaign event proposal. Be specific to the geography and \
issue — generic advice is not useful.

Respond strictly through the provided structured output schema. Every field must be \
grounded in the inputs you receive."""


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
        model="claude-opus-4-8",
        max_tokens=2000,
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(issue, weather, turnout)}],
        output_format=EventIdeation,
    )
    return resp.parsed_output


if __name__ == "__main__":
    from mocks.fixtures import mock_issues

    issue = mock_issues()[0]
    weather = Weather(
        summary="Steady rain through Saturday afternoon",
        condition="rain",
        temp_f=78.0,
        precip_chance=0.65,
        recommended_format="indoor",
    )
    turnout = TurnoutSummary(
        area=issue.area,
        soft_precincts=["14", "22", "31"],
        target_segments=["infrequent midterm voters", "new registrants"],
        notes="Coalition-active neighborhoods near the creek.",
    )
    draft = asyncio.run(ideate(issue, weather, turnout))
    assert isinstance(draft, EventIdeation)
    assert draft.format == weather.recommended_format
    assert 3 <= len(draft.talking_points) <= 6
    assert draft.venue_suggestion and draft.target_voters and draft.rationale
    print(draft.model_dump_json(indent=2))
