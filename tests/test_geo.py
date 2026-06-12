"""WS-2.3 — every demo area must resolve to coords for the weather client."""
from mocks.fixtures import mock_issues

from tools.geo import resolve


def _in_north_carolina(lat: float, lon: float) -> bool:
    return 33.5 <= lat <= 37.5 and -84.5 <= lon <= -75.0


def test_known_demo_areas_resolve_to_distinct_coords():
    chapel_hill = resolve("Chapel Hill, Orange County")
    yanceyville = resolve("Yanceyville, Caswell County")
    assert chapel_hill != yanceyville
    assert _in_north_carolina(*chapel_hill)
    assert _in_north_carolina(*yanceyville)


def test_lookup_is_case_insensitive():
    assert resolve("YANCEYVILLE, CASWELL COUNTY") == resolve(
        "Yanceyville, Caswell County"
    )


def test_keyword_fallback_matches_partial_area_names():
    # Scout-invented phrasing should still land in the right county
    assert resolve("rural northern Caswell") == resolve("northern Caswell County")
    assert resolve("Carrboro neighborhoods") == resolve(
        "Carrboro, Orange County"
    )


def test_unknown_area_returns_district_default_not_error():
    lat, lon = resolve("some precinct nobody has heard of")
    assert _in_north_carolina(lat, lon)


def test_every_fixture_area_resolves():
    for issue in mock_issues():
        lat, lon = resolve(issue.area)
        assert _in_north_carolina(lat, lon), issue.area
