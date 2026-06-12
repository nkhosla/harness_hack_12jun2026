"""FastAPI application entrypoint for campaign-copilot."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from guild_adapter import setup_guild_run
from runstore import RunStore, mock_run
from schemas.models import ProgressEvent, Slate

app = FastAPI(title="Campaign Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SlateRequest(BaseModel):
    region: str
    horizon: str


class RunCreated(BaseModel):
    run_id: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: Literal["pending", "running", "done", "failed"]
    region: str
    horizon: str
    slate: Slate | None
    error: str | None


store = RunStore()


def _select_runner() -> Callable[..., Awaitable[Slate]]:
    if os.getenv("CAMPAIGN_USE_MOCK", "1") != "0":
        return mock_run

    from orchestrator import run

    return run


async def _execute(
    run_id: str,
    region: str,
    horizon: str,
) -> None:
    run = store.get(run_id)
    if run is None:
        return

    run.status = "running"
    guild_hooks = await setup_guild_run(
        run_id,
        region=region,
        horizon=horizon,
    )
    emit = store.make_emit(run, extra_sinks=guild_hooks.extra_sinks)

    try:
        runner = _select_runner()
        slate = await runner(region, horizon, emit)
        run.slate = slate
        run.status = "done"
        await guild_hooks.close("completed", f"{len(slate.ranked_events)} events")
    except Exception as exc:
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        await guild_hooks.close("failed", None)


@app.post("/slate", status_code=202, response_model=RunCreated)
async def create_slate(request: SlateRequest) -> RunCreated:
    run = store.create(request.region, request.horizon)
    run.task = asyncio.create_task(
        _execute(
            run.run_id,
            request.region,
            request.horizon,
        )
    )
    return RunCreated(run_id=run.run_id)


@app.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str) -> RunStatusResponse:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunStatusResponse(
        run_id=run.run_id,
        status=run.status,
        region=run.region,
        horizon=run.horizon,
        slate=run.slate,
        error=run.error,
    )


@app.get("/runs/{run_id}/events", response_model=list[ProgressEvent])
async def get_run_events(
    run_id: str,
    since: int = Query(default=-1),
) -> list[ProgressEvent]:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return store.events_since(run, since)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
