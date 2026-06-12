"""In-memory run store, emit seam, and mock runner for campaign-copilot."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from mocks.fixtures import mock_progress_events, mock_slate
from schemas.models import ProgressEvent, Slate

RunStatus = Literal["pending", "running", "done", "failed"]
EmitFn = Callable[[str, str, str], None]
ProgressSink = Callable[[ProgressEvent], None]


@dataclass
class Run:
    run_id: str
    region: str
    horizon: str
    status: RunStatus = "pending"
    events: list[ProgressEvent] = field(default_factory=list)
    slate: Slate | None = None
    error: str | None = None
    _next_seq: int = 0
    task: asyncio.Task | None = None


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def create(self, region: str, horizon: str) -> Run:
        run = Run(run_id=uuid.uuid4().hex, region=region, horizon=horizon)
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def events_since(self, run: Run, since: int) -> list[ProgressEvent]:
        return [event for event in run.events if event.seq > since]

    def make_emit(
        self,
        run: Run,
        extra_sinks: Sequence[ProgressSink] = (),
    ) -> EmitFn:
        def emit(agent: str, status: str, detail: str) -> None:
            event = ProgressEvent(
                run_id=run.run_id,
                seq=run._next_seq,
                agent=agent,
                status=status,  # type: ignore[arg-type]
                detail=detail,
            )
            run._next_seq += 1
            run.events.append(event)
            for sink in extra_sinks:
                sink(event)

        return emit


async def mock_run(
    region: str,
    horizon: str,
    emit: EmitFn,
    step_delay: float | None = None,
) -> Slate:
    if step_delay is None:
        step_delay = float(os.getenv("CAMPAIGN_MOCK_STEP_DELAY", "1.0"))

    for event in mock_progress_events(run_id=""):
        emit(event.agent, event.status, event.detail)
        if step_delay > 0:
            await asyncio.sleep(step_delay)

    return mock_slate(region, horizon)
