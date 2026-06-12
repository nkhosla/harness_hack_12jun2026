from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Weather(_StrictModel):
    summary: str
    condition: str
    temp_f: float
    precip_chance: float = Field(ge=0, le=1)
    recommended_format: Literal["indoor", "outdoor"]


class TurnoutSummary(_StrictModel):
    area: str
    soft_precincts: list[str]
    target_segments: list[str]
    notes: str


class Article(_StrictModel):
    title: str
    text: str
    url: str
    source: str | None = None
    published: date | None = None


class Issue(_StrictModel):
    id: str
    title: str
    area: str
    summary: str
    source_links: list[str]
    salience: float = Field(ge=0, le=1)


class EventRecommendation(_StrictModel):
    issue: Issue
    area: str
    proposed_date: date
    weather: Weather
    format: Literal["indoor", "outdoor"]
    venue_suggestion: str
    target_voters: str
    talking_points: list[str]
    rationale: str
    draft_outreach: str | None = None


class Slate(_StrictModel):
    region: str
    horizon: str
    ranked_events: list[EventRecommendation]


class ProgressEvent(_StrictModel):
    run_id: str
    seq: int = Field(ge=0)
    agent: str
    status: Literal["started", "tool_call", "done", "failed"]
    detail: str
