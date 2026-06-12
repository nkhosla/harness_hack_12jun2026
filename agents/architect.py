from __future__ import annotations

import asyncio
import inspect
import logging
import sys
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, Literal

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from schemas.models import EventRecommendation, Issue, TurnoutSummary, Weather

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"
DEFAULT_EVENT_TIMEOUT_S = 45.0  # one shot per event; no retry
_DEFAULT_PROPOSED_DATE = date(2026, 6, 17)
_DEFAULT_TIMEOUT_S = 20.0
_FAILED_EMIT_TIMEOUT_S = 1.0

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


async def _invoke(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run sync or async callables without blocking the event loop."""
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    result = await asyncio.to_thread(fn, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _invoke_all(*coros: Any) -> tuple[Any, ...]:
    """Run awaitables concurrently; cancel siblings when one fails or is cancelled."""
    tasks = [asyncio.create_task(coro) for coro in coros]
    try:
        return tuple(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def _field(src: Any, name: str) -> Any:
    return src[name] if isinstance(src, dict) else getattr(src, name)


def _talking_points(value: Any) -> list[str]:
    if isinstance(value, str):
        raise TypeError("talking_points must be a sequence of strings, not a bare string")
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            f"talking_points must be a sequence of strings, got {type(value).__name__}"
        )
    points = list(value)
    if not all(isinstance(point, str) for point in points):
        raise TypeError("talking_points must contain only strings")
    return points


def _assemble(
    issue: Issue,
    when: date,
    weather: Weather,
    partial: Any,
) -> EventRecommendation:
    return EventRecommendation(
        issue=issue,
        area=issue.area,
        proposed_date=when,
        weather=weather,
        format=weather.recommended_format,
        venue_suggestion=_field(partial, "venue_suggestion"),
        target_voters=_field(partial, "target_voters"),
        talking_points=_talking_points(_field(partial, "talking_points")),
        rationale=_field(partial, "rationale"),
        draft_outreach=None,
    )


async def build_event(
    issue: Issue,
    *,
    proposed_date: date | None = None,
    get_weather: Callable[..., Any] | None = None,
    get_turnout: Callable[..., Any] | None = None,
    ideate: Callable[..., Any] | None = None,
    emit: Callable[[str, str], Any] | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> EventRecommendation:
    when = proposed_date or _DEFAULT_PROPOSED_DATE

    if get_weather is None:
        raise NotImplementedError(
            "get_weather (WS-2) is not available; pass get_weather= explicitly"
        )
    if get_turnout is None:
        raise NotImplementedError(
            "get_turnout (WS-2) is not available; pass get_turnout= explicitly"
        )
    if ideate is None:
        ideate = globals()["ideate"]

    async def _emit(status: str, detail: str) -> None:
        if emit is not None:
            await _invoke(emit, status, detail)

    async def _emit_failed_best_effort(exc: Exception) -> None:
        if emit is None:
            return
        try:
            await asyncio.wait_for(
                _emit("failed", f"Event Architect failed for {issue.area}: {exc}"),
                timeout=min(_FAILED_EMIT_TIMEOUT_S, timeout_s),
            )
        except Exception:
            return

    async def _run() -> EventRecommendation:
        await _emit("started", f"Event Architect spinning up for '{issue.title}'")
        await _emit("tool_call", f"Pulling Jua weather forecast for {issue.area}")
        await _emit(
            "tool_call",
            f"Querying turnout history for soft precincts in {issue.area}",
        )

        weather, turnout = await _invoke_all(
            _invoke(get_weather, issue.area, when),
            _invoke(get_turnout, issue.area),
        )
        partial = await _invoke(ideate, issue, weather, turnout)
        event = _assemble(issue, when, weather, partial)
        await _emit("done", f"Briefed event recommendation for {issue.area}")
        return event

    try:
        return await asyncio.wait_for(_run(), timeout=timeout_s)
    except Exception as exc:
        await _emit_failed_best_effort(exc)
        raise


async def build_events(
    issues: list[Issue],
    *,
    timeout_s: float = DEFAULT_EVENT_TIMEOUT_S,
    builder: Callable[[Issue], Awaitable[EventRecommendation]] | None = None,
    proposed_date: date | None = None,
    get_weather: Callable[..., Any] | None = None,
    get_turnout: Callable[..., Any] | None = None,
    ideate: Callable[..., Any] | None = None,
    emit: Callable[[str, str], Any] | None = None,
) -> list[EventRecommendation]:
    """Fan out one bounded Event Architect per issue; drop failures, keep the slate.

    Each event is bounded by `timeout_s` (one shot, no retry). A timeout or any
    exception in a single build is logged and dropped — never fatal to the slate.
    Result order follows `issues` (minus drops).

    Pass an explicit ``builder=`` or inject WS-2 ``get_weather=`` / ``get_turnout=``
    callables; bare ``build_events(issues)`` raises until tools are wired.
    """
    use_build_event = False
    if builder is None:
        if get_weather is None or get_turnout is None:
            raise RuntimeError(
                "build_events needs an explicit builder= argument, or "
                "get_weather= and get_turnout= (WS-2) callables."
            )
        use_build_event = True

        async def _build_event_builder(issue: Issue) -> EventRecommendation:
            return await build_event(
                issue,
                proposed_date=proposed_date,
                get_weather=get_weather,
                get_turnout=get_turnout,
                ideate=ideate,
                emit=emit,
                timeout_s=timeout_s,
            )

        resolved = _build_event_builder
    else:
        resolved = builder

    async def _safe(issue: Issue) -> EventRecommendation | None:
        try:
            if use_build_event:
                return await resolved(issue)
            return await asyncio.wait_for(resolved(issue), timeout=timeout_s)
        except TimeoutError:
            logger.warning("Event build timed out for %s after %.0fs", issue.id, timeout_s)
            return None
        except Exception:  # degrade gracefully — never fatal. (CancelledError still propagates.)
            logger.warning("Event build failed for %s", issue.id, exc_info=True)
            return None

    # No concurrency cap: only ~5 events. Add an asyncio.Semaphore here if fan-out grows.
    results = await asyncio.gather(*(_safe(issue) for issue in issues))
    return [event for event in results if event is not None]


async def _smoke_build_event() -> None:
    import time

    from mocks.fixtures import mock_event, mock_issues

    issue = mock_issues()[0]
    weather = mock_event(rank=0).weather
    emitted: list[tuple[str, str]] = []

    async def fake_weather(area: str, when: date) -> Weather:
        return weather

    def fake_turnout(area: str) -> TurnoutSummary:
        return TurnoutSummary(
            area=area,
            soft_precincts=["14", "22", "31"],
            target_segments=["environmentally engaged homeowners"],
            notes="Mock turnout for smoke test",
        )

    async def fake_ideate(
        issue: Issue, weather: Weather, turnout: TurnoutSummary
    ) -> dict[str, Any]:
        return {
            "venue_suggestion": "Test venue",
            "target_voters": "Test voters",
            "talking_points": ["Point A", "Point B"],
            "rationale": "Test rationale",
        }

    ev = await build_event(
        issue,
        get_weather=fake_weather,
        get_turnout=fake_turnout,
        ideate=fake_ideate,
        emit=lambda status, detail: emitted.append((status, detail)),
    )

    assert isinstance(ev, EventRecommendation)
    assert ev.area == issue.area
    assert ev.weather == weather
    assert ev.format == weather.recommended_format
    assert ev.proposed_date == _DEFAULT_PROPOSED_DATE
    assert ev.draft_outreach is None
    assert [status for status, _ in emitted] == [
        "started",
        "tool_call",
        "tool_call",
        "done",
    ]
    assert emitted[1][1] == f"Pulling Jua weather forecast for {issue.area}"

    emitted_timeout: list[tuple[str, str]] = []

    async def slow_weather(area: str, when: date) -> Weather:
        await asyncio.sleep(10)
        return weather

    try:
        await build_event(
            issue,
            get_weather=slow_weather,
            get_turnout=fake_turnout,
            ideate=fake_ideate,
            emit=lambda status, detail: emitted_timeout.append((status, detail)),
            timeout_s=0.2,
        )
        raise AssertionError("expected TimeoutError from slow_weather")
    except TimeoutError:
        pass

    assert any(status == "failed" for status, _ in emitted_timeout)

    emitted_sync_timeout: list[tuple[str, str]] = []

    def slow_turnout(area: str) -> TurnoutSummary:
        time.sleep(1)
        return TurnoutSummary(
            area=area,
            soft_precincts=["14"],
            target_segments=["test"],
            notes="should not finish",
        )

    try:
        await build_event(
            issue,
            get_weather=fake_weather,
            get_turnout=slow_turnout,
            ideate=fake_ideate,
            emit=lambda status, detail: emitted_sync_timeout.append((status, detail)),
            timeout_s=0.1,
        )
        raise AssertionError("expected TimeoutError from slow_turnout")
    except TimeoutError:
        pass

    assert any(status == "failed" for status, _ in emitted_sync_timeout)

    sibling_completed = False

    async def fail_weather(area: str, when: date) -> Weather:
        raise ValueError("weather failed")

    async def slow_turnout_task(area: str) -> TurnoutSummary:
        nonlocal sibling_completed
        try:
            await asyncio.sleep(10)
            sibling_completed = True
        except asyncio.CancelledError:
            raise
        return TurnoutSummary(
            area=area,
            soft_precincts=["14"],
            target_segments=["test"],
            notes="should be cancelled",
        )

    try:
        await build_event(
            issue,
            get_weather=fail_weather,
            get_turnout=slow_turnout_task,
            ideate=fake_ideate,
            timeout_s=1.0,
        )
        raise AssertionError("expected ValueError from fail_weather")
    except ValueError:
        pass

    await asyncio.sleep(0.05)
    assert not sibling_completed

    try:
        _assemble(
            issue,
            _DEFAULT_PROPOSED_DATE,
            weather,
            {
                "venue_suggestion": "Test venue",
                "target_voters": "Test voters",
                "talking_points": "single talking point",
                "rationale": "Test rationale",
            },
        )
        raise AssertionError("expected TypeError for string talking_points")
    except TypeError:
        pass

    emitted_hanging_failed: list[tuple[str, str]] = []

    async def hanging_failed_emit(status: str, detail: str) -> None:
        if status == "failed":
            await asyncio.sleep(10)
        emitted_hanging_failed.append((status, detail))

    t0 = time.monotonic()
    try:
        await build_event(
            issue,
            get_weather=slow_weather,
            get_turnout=fake_turnout,
            ideate=fake_ideate,
            emit=hanging_failed_emit,
            timeout_s=0.2,
        )
        raise AssertionError("expected TimeoutError with hanging failed emit")
    except TimeoutError:
        pass

    assert time.monotonic() - t0 < 0.5

    try:
        await build_event(issue, ideate=fake_ideate)
        raise AssertionError("expected NotImplementedError for missing WS-2 tools")
    except NotImplementedError:
        pass


async def _smoke_build_events() -> None:
    from mocks.fixtures import mock_event, mock_issues

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

    try:
        await build_events(issues)
        raise AssertionError("expected RuntimeError for missing builder/tools")
    except RuntimeError:
        pass


async def _smoke() -> None:
    await _smoke_build_event()
    await _smoke_build_events()


if __name__ == "__main__":
    try:
        asyncio.run(_smoke())
    except AssertionError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("3.2 build_event smoke OK")
    print("OK: build_events smoke passed")
