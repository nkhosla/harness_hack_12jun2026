"""WS-2.3 — Area -> lat/long resolver (static lookup, never raises).

Maps the demo region's area names (NC HD-50: Caswell + Orange counties)
to coordinates for the weather client. Unknown areas fall back to keyword
matching, then to the district center, so every Scout-emitted area resolves.
"""
from __future__ import annotations

HILLSBOROUGH = (36.0754, -79.0997)
EFLAND = (36.0810, -79.1692)
CEDAR_GROVE = (36.1743, -79.1670)
YANCEYVILLE = (36.4040, -79.3361)
MILTON = (36.5382, -79.2086)
DISTRICT_CENTER = (36.1500, -79.1900)  # midpoint of the HD-50 demo region

_EXACT: dict[str, tuple[float, float]] = {
    "hillsborough, orange county": HILLSBOROUGH,
    "efland, orange county": EFLAND,
    "cedar grove, orange county": CEDAR_GROVE,
    "yanceyville, caswell county": YANCEYVILLE,
    "milton, caswell county": MILTON,
    "northern caswell county": MILTON,
}

# Checked in order: most specific keyword combos first.
_KEYWORDS: list[tuple[tuple[str, ...], tuple[float, float]]] = [
    (("hillsborough",), HILLSBOROUGH),
    (("efland",), EFLAND),
    (("cedar", "grove"), CEDAR_GROVE),
    (("yanceyville",), YANCEYVILLE),
    (("northern", "caswell"), MILTON),
    (("milton",), MILTON),
    (("caswell",), YANCEYVILLE),
    (("orange",), HILLSBOROUGH),
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
