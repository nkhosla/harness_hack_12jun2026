"""WS-2.3 — Area -> lat/long resolver (static lookup, never raises).

Maps the demo region's area names (NC HD-50: Caswell + Orange counties)
to coordinates for the weather client. Unknown areas fall back to keyword
matching, then to the district center, so every Scout-emitted area resolves.
"""
from __future__ import annotations

CHAPEL_HILL = (35.9132, -79.0558)
CARRBORO = (35.9101, -79.0753)
NORTHSIDE = (35.9163, -79.0612)
YANCEYVILLE = (36.4040, -79.3361)
MILTON = (36.5382, -79.2086)
DISTRICT_CENTER = (36.1500, -79.1900)  # midpoint of the HD-50 demo region

_EXACT: dict[str, tuple[float, float]] = {
    "chapel hill, orange county": CHAPEL_HILL,
    "carrboro, orange county": CARRBORO,
    "northside, chapel hill, orange county": NORTHSIDE,
    "yanceyville, caswell county": YANCEYVILLE,
    "milton, caswell county": MILTON,
    "northern caswell county": MILTON,
}

# Checked in order: most specific keyword combos first.
_KEYWORDS: list[tuple[tuple[str, ...], tuple[float, float]]] = [
    (("northside",), NORTHSIDE),
    (("chapel", "hill"), CHAPEL_HILL),
    (("carrboro",), CARRBORO),
    (("yanceyville",), YANCEYVILLE),
    (("northern", "caswell"), MILTON),
    (("milton",), MILTON),
    (("caswell",), YANCEYVILLE),
    (("orange",), CHAPEL_HILL),
]


def resolve(area: str) -> tuple[float, float]:
    """Resolve an area name to (lat, lon). Always returns coordinates."""
    key = area.strip().lower()
    if key in _EXACT:
        return _EXACT[key]
    for keywords, coords in _KEYWORDS:
        if all(word in key for word in keywords):
            return coords
    return DISTRICT_CENTER
