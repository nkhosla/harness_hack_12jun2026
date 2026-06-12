from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from schemas.models import EventRecommendation, Issue

logger = logging.getLogger(__name__)

DEFAULT_EVENT_TIMEOUT_S = 45.0  # one shot per event; no retry


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
                raise RuntimeError("boom")          # dropped: exception
            if idx == 2:
                await asyncio.sleep(10)             # dropped: exceeds tiny timeout
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
