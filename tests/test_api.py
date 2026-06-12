import asyncio

import httpx
import pytest

from api import app
from schemas.models import Slate


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _wait_for_done(client: httpx.AsyncClient, run_id: str) -> dict:
    for _ in range(50):
        response = await client.get(f"/runs/{run_id}")
        body = response.json()
        if body["status"] in ("done", "failed"):
            return body
        await asyncio.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not complete in time")


@pytest.mark.asyncio
async def test_create_slate_returns_run_id(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/slate",
        json={"region": "Florida HD-21", "horizon": "next two weeks"},
    )
    assert response.status_code == 202
    body = response.json()
    assert "run_id" in body
    assert len(body["run_id"]) == 32


@pytest.mark.asyncio
async def test_run_completes_with_slate(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/slate",
        json={"region": "Florida HD-21", "horizon": "next two weeks"},
    )
    run_id = response.json()["run_id"]

    body = await _wait_for_done(client, run_id)
    assert body["status"] == "done"
    assert body["error"] is None

    slate = Slate.model_validate(body["slate"])
    assert slate.region == "Florida HD-21"
    assert slate.horizon == "next two weeks"
    assert len(slate.ranked_events) == 5


@pytest.mark.asyncio
async def test_events_sequencing_and_since_cursor(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/slate",
        json={"region": "Florida HD-21", "horizon": "next two weeks"},
    )
    run_id = response.json()["run_id"]

    await _wait_for_done(client, run_id)

    events_response = await client.get(f"/runs/{run_id}/events?since=-1")
    assert events_response.status_code == 200
    events = events_response.json()
    assert len(events) == 25
    assert events[0]["seq"] == 0
    assert events[-1]["seq"] == 24
    assert all(event["run_id"] == run_id for event in events)

    since_response = await client.get(f"/runs/{run_id}/events?since=4")
    since_events = since_response.json()
    assert len(since_events) == 20
    assert all(event["seq"] > 4 for event in since_events)


@pytest.mark.asyncio
async def test_unknown_run_returns_404(client: httpx.AsyncClient) -> None:
    bogus_id = "0" * 32

    status_response = await client.get(f"/runs/{bogus_id}")
    assert status_response.status_code == 404

    events_response = await client.get(f"/runs/{bogus_id}/events")
    assert events_response.status_code == 404


@pytest.mark.asyncio
async def test_runner_selection_failure_marks_run_failed(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_import_error() -> None:
        raise ImportError("orchestrator.run not available")

    monkeypatch.setattr("api._select_runner", _raise_import_error)

    response = await client.post(
        "/slate",
        json={"region": "Florida HD-21", "horizon": "next two weeks"},
    )
    run_id = response.json()["run_id"]

    body = await _wait_for_done(client, run_id)
    assert body["status"] == "failed"
    assert body["error"] == "ImportError: orchestrator.run not available"
    assert body["slate"] is None


@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
