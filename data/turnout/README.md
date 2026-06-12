# Turnout data — NC HD-50 (Caswell + Orange counties)

Official precinct-level data from the [NC State Board of Elections](https://dl.ncsbe.gov/) for the 2020, 2022, and 2024 general elections, filtered to Caswell and Orange counties (the demo region: NC House District 50 — Hillsborough/Efland and rural Orange precincts plus Caswell County). All aggregate public election results — **no voter file, no PII**, safe to show on stage.

## What teammates should use

**`processed/precinct_turnout.csv`** — one row per election x county x precinct (148 rows). The only file the rest of the project should read. Or skip the CSV and call the tool:

```python
from tools.turnout import turnout_summary, load_turnout

turnout_summary("Orange")    # -> schemas.models.TurnoutSummary
turnout_summary("Caswell")   #    (soft precincts, target segments, notes)
turnout_summary("HD-50")
load_turnout()               # -> pandas DataFrame of the CSV
```

"Soft" precincts = big registered-voter pools with the biggest presidential-to-midterm drop-off — the highest-leverage event targets. For `HD-50`, the largest opportunities are Orange County precincts such as Cheeks and Grady Brown plus Caswell's larger rural precincts.

### Columns

| column | meaning |
|---|---|
| `election_date` | `2020-11-03`, `2022-11-08`, `2024-11-05` |
| `county` | `CASWELL` or `ORANGE` |
| `precinct` / `precinct_name` | NCSBE precinct code (string) and name, e.g. `H` / `HILLSBOROUGH` |
| `registered_total` | registered voters at that election |
| `reg_age_18_25` … `reg_age_over_66` | registered voters by age bucket (event-audience signal: students vs seniors) |
| `ballots_cast` | votes + overvotes + undervotes on the top-of-ticket contest (President; US Senate in 2022) — exact, every ballot has that contest |
| `top_dem_votes` / `top_rep_votes` | top-of-ticket votes by party |
| `nc_house_district` | NC House district of the precinct (50 or 56 in Orange) |
| `turnout_pct` | `ballots_cast / registered_total * 100` |
| `dem_share_top` | DEM share of the two-party top-of-ticket vote |

## Layout + rebuilding

```
data/turnout/
  raw/         # NCSBE precinct-sorted results ({ORANGE,CASWELL}_sort_*.txt.gz)
               # + voter registration stats (voter_stats_*.txt.gz)
  processed/   # precinct_turnout.csv  <- the deliverable
  build.py     # raw -> processed     (uv run data/turnout/build.py)
```

Raw sources (all public, no auth):

- Results: `https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/{YYYY_MM_DD}/results_precinct_sort/{COUNTY}_PRECINCT_SORT.txt` — "precinct-sorted" means early/mail votes are attributed to voters' home precincts (the plain `results_pct` files lump them into county-wide pseudo-precincts, which wildly understates precinct turnout in Orange).
- Registration: `voter_stats_{YYYYMMDD}.zip` under the same `ENRS/{date}/` prefix, filtered to the two counties.

Gotchas baked into `build.py`: the NCSBE exports use CRLF endings and embed **null bytes** in the party column (raw files here are already cleaned with `tr -d '\000\r'`); county-wide pseudo-precinct rows (`ABSENTEE`, `PROVISIONAL`, …) are excluded; precincts with no registration snapshot are dropped.
