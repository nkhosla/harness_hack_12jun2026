"""WS-2.4 — Weather client: area + date -> Weather (incl. recommended_format).

Pluggable forecast layer (Jua-compatible seam): currently backed by NOAA/NWS,
which is free, keyless, and returns probabilityOfPrecipitation directly.
Live call is wrapped with a hard timeout and a disk cache so repeated demo
runs never hang on the network. Precip/heat map to indoor/outdoor.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import httpx

from schemas.models import Weather
from tools.geo import resolve

# NWS API policy requires a descriptive User-Agent.
_HEADERS = {
    "User-Agent": "campaign-copilot (hackathon demo)",
    "Accept": "application/geo+json",
}
_TIMEOUT = 10.0
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "weather"

# Outdoor events are a bad idea in rain or extreme heat.
_PRECIP_INDOOR_THRESHOLD = 0.35
_HEAT_INDOOR_THRESHOLD_F = 92.0


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _condition(short_forecast: str, temp_f: float) -> str:
    """Normalize NOAA shortForecast to the WS-0 fixture vocabulary the UI
    is built against: thunderstorms / rain / hot_humid / partly_cloudy / clear."""
    s = short_forecast.lower()
    if "thunder" in s:
        return "thunderstorms"
    if any(w in s for w in ("rain", "shower", "drizzle")):
        return "rain"
    if temp_f >= _HEAT_INDOOR_THRESHOLD_F:
        return "hot_humid"
    if any(w in s for w in ("partly", "mostly", "cloud")):
        return "partly_cloudy"
    if any(w in s for w in ("sunny", "clear", "fair")):
        return "clear"
    return "partly_cloudy"


def _build_weather(periods: list[dict], target: date) -> Weather:
    same_day = [p for p in periods if p["startTime"][:10] == target.isoformat()]
    if not same_day:
        # Target beyond the forecast horizon: use the furthest available day.
        last_day = max(p["startTime"][:10] for p in periods)
        same_day = [p for p in periods if p["startTime"][:10] == last_day]

    # Events run in the daytime — late-night rain shouldn't drive the format.
    daytime = [p for p in same_day if 8 <= int(p["startTime"][11:13]) < 20] or same_day

    hottest = max(daytime, key=lambda p: p["temperature"])
    temp_f = float(hottest["temperature"])
    precip = max((p["probabilityOfPrecipitation"]["value"] or 0) for p in daytime) / 100
    condition = _condition(hottest["shortForecast"], temp_f)

    fmt = (
        "indoor"
        if precip >= _PRECIP_INDOOR_THRESHOLD or temp_f >= _HEAT_INDOOR_THRESHOLD_F
        else "outdoor"
    )
    summary = (
        f"{hottest['shortForecast']}, high {temp_f:.0f}F, "
        f"{precip:.0%} chance of precipitation"
    )
    return Weather(
        summary=summary,
        condition=condition,
        temp_f=temp_f,
        precip_chance=precip,
        recommended_format=fmt,
    )


async def _fetch_periods(client: httpx.AsyncClient, lat: float, lon: float) -> list[dict]:
    points = await client.get(f"https://api.weather.gov/points/{lat},{lon}")
    points.raise_for_status()
    hourly_url = points.json()["properties"]["forecastHourly"]
    forecast = await client.get(hourly_url)
    forecast.raise_for_status()
    return forecast.json()["properties"]["periods"]


async def get_weather(
    area: str,
    target_date: date,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    cache_dir: Path | None = None,
) -> Weather:
    """Forecast for an area on a date. Cached to disk; raises on network failure
    so a failed event gets dropped rather than briefed with fake weather."""
    cache_dir = cache_dir or _DEFAULT_CACHE_DIR
    cache_file = cache_dir / f"{_slug(area)}_{target_date.isoformat()}.json"
    if cache_file.exists():
        return Weather.model_validate_json(cache_file.read_text())

    lat, lon = resolve(area)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, transport=transport
    ) as client:
        try:
            periods = await _fetch_periods(client, lat, lon)
        except httpx.HTTPError:
            # NWS throws intermittent 500s; one retry de-risks the live demo.
            periods = await _fetch_periods(client, lat, lon)

    weather = _build_weather(periods, target_date)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(weather.model_dump_json())
    return weather


if __name__ == "__main__":
    # Smoke test: one real NOAA call per demo area, then prove the cache hit.
    import asyncio
    import time
    from datetime import timedelta

    async def main() -> None:
        target = date.today() + timedelta(days=2)
        for area in [
            "north Gainesville, Alachua County",
            "east Gainesville, Alachua County",
            "Gainesville, Alachua County",
            "Ocala, Marion County",
            "western Marion County",
        ]:
            t0 = time.perf_counter()
            w = await get_weather(area, target)
            print(f"{area} @ {target}: {w.summary} -> {w.recommended_format} "
                  f"({time.perf_counter() - t0:.2f}s)")
        t0 = time.perf_counter()
        await get_weather("Ocala, Marion County", target)
        print(f"cache hit: {time.perf_counter() - t0:.3f}s")

    asyncio.run(main())
