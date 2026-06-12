"""Turnout query tool — the Event Architect's one bounded turnout call.

Backed by data/turnout/processed/precinct_turnout.csv (built by
data/turnout/build.py from official NC State Board of Elections data for
Caswell + Orange counties / NC HD-50).

Usage:
    from tools.turnout import turnout_summary, load_turnout

    turnout_summary("Orange")   # county name, "Caswell", or "HD-50"
    load_turnout()              # full pandas DataFrame for custom cuts
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

from schemas.models import TurnoutSummary

DATA = Path(__file__).parent.parent / "data" / "turnout" / "processed" / "precinct_turnout.csv"

LATEST_PRESIDENTIAL = "2024-11-05"
LATEST_MIDTERM = "2022-11-08"


@lru_cache(maxsize=1)
def load_turnout() -> pd.DataFrame:
    return pd.read_csv(DATA, dtype={"precinct": str, "nc_house_district": "Int64"})


def _filter_area(df: pd.DataFrame, area: str) -> pd.DataFrame:
    """area: a county name ("Orange", "Caswell") or a house district ("HD-50", "50")."""
    a = area.strip()
    if a.upper().startswith("HD-") or a.isdigit():
        district = int(a.upper().removeprefix("HD-"))
        return df[df["nc_house_district"] == district]
    return df[df["county"].str.casefold() == a.casefold()]


def turnout_summary(area: str, n_soft: int = 6) -> TurnoutSummary:
    """Summarize turnout for an area and surface its softest precincts.

    A "soft" precinct has a large pool of registered voters but a big drop-off
    from presidential to midterm turnout — the people who show up for the big
    race but skip everything else, i.e. the highest-leverage targets for
    community events. Ranked by drop-off weighted by registration.
    """
    if n_soft < 1:
        raise ValueError("n_soft must be >= 1")

    df = _filter_area(load_turnout(), area)
    if df.empty:
        raise ValueError(
            f"no turnout data for area {area!r} (try 'Orange', 'Caswell', or 'HD-50')"
        )

    keys = ["county", "precinct"]
    pres = df[df["election_date"] == LATEST_PRESIDENTIAL].set_index(keys)
    mid = df[df["election_date"] == LATEST_MIDTERM].set_index(keys)
    both = pres.join(mid[["turnout_pct"]], rsuffix="_midterm", how="inner")

    both["dropoff"] = both["turnout_pct"] - both["turnout_pct_midterm"]
    both["leverage"] = both["dropoff"].clip(lower=0) / 100 * both["registered_total"]
    soft = both.sort_values("leverage", ascending=False).head(n_soft)
    soft_precincts = [
        f"{p} ({name.title() if len(name) > 3 else name})"
        for (_, p), name in soft["precinct_name"].items()
    ]

    segments: list[str] = []
    young_share = soft["reg_age_18_25"].sum() / soft["registered_total"].sum()
    senior_share = soft["reg_age_over_66"].sum() / soft["registered_total"].sum()
    if young_share > 0.25:
        segments.append("students and young voters (18-25 heavy precincts)")
    if senior_share > 0.25:
        segments.append("seniors (66+ heavy precincts)")
    segments.append("presidential-only voters who skip midterms (drop-off targets)")
    if (soft["turnout_pct"] < both["turnout_pct"].median()).any():
        segments.append("low-turnout precincts below area median")

    notes = (
        f"{area}: {len(pres)} precincts, "
        f"{int(pres['registered_total'].sum()):,} registered. "
        f"Turnout {pres['turnout_pct'].mean():.0f}% (2024 presidential) vs "
        f"{mid['turnout_pct'].mean():.0f}% (2022 midterm); "
        f"mean drop-off {both['dropoff'].mean():.0f} pts. "
        f"Soft precincts ranked by registered voters x midterm drop-off."
    )

    return TurnoutSummary(
        area=area,
        soft_precincts=soft_precincts,
        target_segments=segments,
        notes=notes,
    )


if __name__ == "__main__":
    for area in ("Orange", "Caswell", "HD-50"):
        s = turnout_summary(area)
        print(f"== {area}\n  soft: {s.soft_precincts}\n  segments: {s.target_segments}\n  {s.notes}\n")
