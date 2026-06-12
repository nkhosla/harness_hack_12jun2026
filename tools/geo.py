"""WS-2.3 — Area -> lat/long resolver (static lookup, never raises).

Maps the demo region's area names (Florida HD-21: Alachua + Marion counties)
to coordinates for the weather client. Unknown areas fall back to keyword
matching, then to the district center, so every Scout-emitted area resolves.
"""
from __future__ import annotations

GAINESVILLE = (29.6516, -82.3248)
NORTH_GAINESVILLE = (29.7016, -82.3320)
EAST_GAINESVILLE = (29.6520, -82.2920)
OCALA = (29.1872, -82.1401)
WESTERN_MARION = (29.0492, -82.4609)  # Dunnellon
DISTRICT_CENTER = (29.4200, -82.2300)  # midpoint of the HD-21 demo district

_EXACT: dict[str, tuple[float, float]] = {
    "gainesville, alachua county": GAINESVILLE,
    "north gainesville, alachua county": NORTH_GAINESVILLE,
    "east gainesville, alachua county": EAST_GAINESVILLE,
    "ocala, marion county": OCALA,
    "western marion county": WESTERN_MARION,
}

# Checked in order: most specific keyword combos first.
_KEYWORDS: list[tuple[tuple[str, ...], tuple[float, float]]] = [
    (("north", "gainesville"), NORTH_GAINESVILLE),
    (("east", "gainesville"), EAST_GAINESVILLE),
    (("western", "marion"), WESTERN_MARION),
    (("gainesville",), GAINESVILLE),
    (("alachua",), GAINESVILLE),
    (("ocala",), OCALA),
    (("marion",), OCALA),
    (("dunnellon",), WESTERN_MARION),
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
