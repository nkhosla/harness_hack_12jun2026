"""Bridge sync progress funnel to async Guild client."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

from schemas.models import ProgressEvent

from guild_adapter.client import GuildClient, GuildSession

log = logging.getLogger(__name__)

Sink = Callable[[ProgressEvent], None]

_SHUTDOWN = object()


async def _safe_report(
    client: GuildClient, session: GuildSession, event: ProgressEvent
) -> None:
    try:
        await client.report_event(session, event)
    except Exception:
        log.warning(
            "guild report_event failed for run=%s seq=%s",
            event.run_id,
            event.seq,
            exc_info=True,
        )


class GuildSink:
    """Callable sink with a per-session queue worker for in-order delivery."""

    def __init__(self, client: GuildClient, session: GuildSession) -> None:
        self._client = client
        self._session = session
        self._queue: asyncio.Queue[ProgressEvent | object] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._closed = False

    def _ensure_worker(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._worker is None or self._worker.done():
            self._worker = loop.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item is _SHUTDOWN:
                    return
                await _safe_report(self._client, self._session, item)  # type: ignore[arg-type]
            finally:
                self._queue.task_done()

    def __call__(self, event: ProgressEvent) -> None:
        if self._closed:
            return
        try:
            loop = asyncio.get_running_loop()
            self._ensure_worker(loop)
            self._queue.put_nowait(event)
        except Exception:
            log.warning("guild sink schedule failed", exc_info=True)

    async def drain(self) -> None:
        """Wait for all queued events, then stop the worker. For tests/harnesses."""
        await self._queue.join()
        if self._worker is None or self._worker.done():
            self._closed = True
            self._worker = None
            return
        self._closed = True
        await self._queue.put(_SHUTDOWN)
        await self._worker
        self._worker = None

    async def shutdown(self, *, drain_timeout: float = 0.0) -> None:
        """Stop the worker. drain_timeout=0 cancels immediately without blocking."""
        self._closed = True
        if self._worker is None or self._worker.done():
            self._worker = None
            return

        if drain_timeout > 0:
            try:
                await asyncio.wait_for(self._queue.join(), timeout=drain_timeout)
            except asyncio.TimeoutError:
                log.debug("guild sink drain timed out after %.1fs", drain_timeout)

        if self._worker.done():
            self._worker = None
            return

        if drain_timeout > 0:
            await self._queue.put(_SHUTDOWN)
            try:
                await asyncio.wait_for(self._worker, timeout=0.5)
            except asyncio.TimeoutError:
                self._worker.cancel()
        else:
            self._worker.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await self._worker
        self._worker = None


def make_guild_sink(client: GuildClient, session: GuildSession) -> GuildSink:
    return GuildSink(client, session)
