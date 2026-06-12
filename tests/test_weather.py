"""WS-2.4 — forecast -> Weather with timeout + cache, precip -> indoor/outdoor."""
import asyncio
from datetime import date

import httpx

from schemas.models import Weather
from tools.weather import get_weather

TARGET = date(2026, 6, 15)


def _periods(day: str, temps: list[int], pop: int) -> list[dict]:
    return [
        {
            "startTime": f"{day}T{8 + i:02d}:00:00-04:00",
            "temperature": t,
            "probabilityOfPrecipitation": {"value": pop},
            "shortForecast": "Partly Sunny",
        }
        for i, t in enumerate(temps)
    ]


def _transport(periods: list[dict], calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "/points/" in str(request.url):
            return httpx.Response(
                200,
                json={"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/TEST/1,1/forecast/hourly"}},
            )
        return httpx.Response(200, json={"properties": {"periods": periods}})

    return httpx.MockTransport(handler)


def _get(periods, tmp_path, calls, target=TARGET):
    return asyncio.run(
        get_weather(
            "Ocala, Marion County",
            target,
            transport=_transport(periods, calls),
            cache_dir=tmp_path,
        )
    )


def test_returns_valid_weather_for_target_date(tmp_path):
    w = _get(_periods("2026-06-15", [78, 82, 85], pop=20), tmp_path, [])
    assert isinstance(w, Weather)
    assert w.temp_f == 85.0
    assert w.precip_chance == 0.2
    assert w.condition == "partly_cloudy"


def test_condition_normalized_to_fixture_vocabulary(tmp_path):
    periods = _periods("2026-06-15", [80, 84], pop=50)
    for p in periods:
        p["shortForecast"] = "Chance Showers And Thunderstorms"
    w = _get(periods, tmp_path, [])
    assert w.condition == "thunderstorms"


def test_high_precip_maps_to_indoor(tmp_path):
    w = _get(_periods("2026-06-15", [80, 82], pop=70), tmp_path, [])
    assert w.recommended_format == "indoor"


def test_extreme_heat_maps_to_indoor(tmp_path):
    w = _get(_periods("2026-06-15", [90, 95], pop=10), tmp_path, [])
    assert w.recommended_format == "indoor"


def test_mild_day_maps_to_outdoor(tmp_path):
    w = _get(_periods("2026-06-15", [80, 84], pop=10), tmp_path, [])
    assert w.recommended_format == "outdoor"


def test_second_call_hits_cache_not_network(tmp_path):
    calls: list[str] = []
    first = _get(_periods("2026-06-15", [78, 85], pop=20), tmp_path, calls)
    network_calls_after_first = len(calls)
    second = _get(_periods("2026-06-15", [78, 85], pop=20), tmp_path, calls)
    assert len(calls) == network_calls_after_first
    assert second == first


def test_date_beyond_forecast_range_uses_furthest_day(tmp_path):
    # NOAA hourly only covers ~6 days; a far-out proposed_date must still work
    w = _get(_periods("2026-06-15", [78, 85], pop=20), tmp_path, [], target=date(2026, 6, 28))
    assert isinstance(w, Weather)
    assert w.temp_f == 85.0


def test_nighttime_precip_does_not_force_indoor(tmp_path):
    # Events happen in the daytime: 90% rain at 10pm must not flag an
    # afternoon event indoor.
    periods = [
        {
            "startTime": "2026-06-15T14:00:00-04:00",
            "temperature": 84,
            "probabilityOfPrecipitation": {"value": 10},
            "shortForecast": "Partly Sunny",
        },
        {
            "startTime": "2026-06-15T22:00:00-04:00",
            "temperature": 78,
            "probabilityOfPrecipitation": {"value": 90},
            "shortForecast": "Showers",
        },
    ]
    w = _get(periods, tmp_path, [])
    assert w.precip_chance == 0.1
    assert w.recommended_format == "outdoor"


def _flaky_transport(periods: list[dict], fail_first_n: int, calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) <= fail_first_n:
            return httpx.Response(500)
        if "/points/" in str(request.url):
            return httpx.Response(
                200,
                json={"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/TEST/1,1/forecast/hourly"}},
            )
        return httpx.Response(200, json={"properties": {"periods": periods}})

    return httpx.MockTransport(handler)


def test_retries_once_on_transient_server_error(tmp_path):
    calls: list[str] = []
    transport = _flaky_transport(_periods("2026-06-15", [78, 85], pop=20), 1, calls)
    w = asyncio.run(
        get_weather("Ocala, Marion County", TARGET, transport=transport, cache_dir=tmp_path)
    )
    assert w.temp_f == 85.0


def test_raises_when_both_attempts_fail(tmp_path):
    import pytest

    calls: list[str] = []
    transport = _flaky_transport([], 99, calls)
    with pytest.raises(httpx.HTTPError):
        asyncio.run(
            get_weather("Ocala, Marion County", TARGET, transport=transport, cache_dir=tmp_path)
        )
