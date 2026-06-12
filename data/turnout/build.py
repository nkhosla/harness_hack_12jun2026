"""Build the processed precinct turnout table from NC SBE source files.

Reads the raw files in data/turnout/raw/ — NC State Board of Elections
precinct-sorted results (early/mail votes attributed to voters' home
precincts) plus voter registration stats, for Caswell and Orange counties —
and writes data/turnout/processed/precinct_turnout.csv.

Source files were cleaned with `tr -d '\\000\\r'` (the NCSBE export embeds
null bytes in the party column and uses CRLF endings).

Run from the repo root:  uv run data/turnout/build.py
"""

import csv
from pathlib import Path

import pandas as pd

RAW = Path(__file__).parent / "raw"
PROCESSED = Path(__file__).parent / "processed"

ELECTIONS = ["20201103", "20221108", "20241105"]
COUNTIES = ["CASWELL", "ORANGE"]

# Top-of-ticket contest per election. Ballots cast = votes + overvotes +
# undervotes on this contest (every ballot has exactly one of the three).
TOP_CONTEST = {
    "20201103": "US PRESIDENT",
    "20221108": "US SENATE",
    "20241105": "US PRESIDENT",
}

HOUSE_PREFIX = "NC HOUSE OF REPRESENTATIVES DISTRICT"

# County-wide pseudo-precincts for ballots that couldn't be sorted to a home
# precinct (a small residue in the precinct-sorted files).
PSEUDO_PRECINCTS = {"ABSENTEE", "PROVISIONAL", "ONESTOP", "TRANSFER", "CURBSIDE"}


def load_election(stamp: str) -> pd.DataFrame:
    frames = [
        pd.read_csv(
            RAW / f"{county}_sort_{stamp}.txt.gz",
            sep="\t",
            dtype=str,
            quoting=csv.QUOTE_NONE,
        )
        for county in COUNTIES
    ]
    results = pd.concat(frames, ignore_index=True)
    results["vote_ct"] = (
        pd.to_numeric(results["vote_ct"], errors="coerce").fillna(0).astype(int)
    )
    results = results[~results["precinct_code"].isin(PSEUDO_PRECINCTS)]

    stats = pd.read_csv(
        RAW / f"voter_stats_{stamp}.txt.gz",
        sep="\t",
        dtype=str,
        quoting=csv.QUOTE_NONE,
    )
    stats["total_voters"] = (
        pd.to_numeric(stats["total_voters"], errors="coerce").fillna(0).astype(int)
    )

    keys = ["county", "precinct"]
    results = results.rename(columns={"precinct_code": "precinct"})
    results["precinct_name"] = results["precinct_name"].str.strip()
    names = (
        results[results["precinct_name"] != ""]
        .groupby(keys)["precinct_name"]
        .first()
        .reset_index()
    )

    stat_keys = ["county_desc", "precinct_abbrv"]
    registered = (
        stats.groupby(stat_keys)["total_voters"]
        .sum()
        .rename("registered_total")
        .reset_index()
    )

    # Age mix of registered voters (buckets as shipped in the stats file).
    age_cols = {
        "Age 18 - 25": "reg_age_18_25",
        "Age 26 - 40": "reg_age_26_40",
        "Age 41 - 65": "reg_age_41_65",
        "Age Over 66": "reg_age_over_66",
    }
    ages = (
        stats.pivot_table(
            index=stat_keys, columns="age", values="total_voters", aggfunc="sum", fill_value=0
        )
        .rename(columns=age_cols)
        .reset_index()
    )
    registered = registered.merge(ages, on=stat_keys, how="left")
    registered = registered.rename(
        columns={"county_desc": "county", "precinct_abbrv": "precinct"}
    )

    top = results[results["contest_title"] == TOP_CONTEST[stamp]]
    ballots = top.groupby(keys)["vote_ct"].sum().rename("ballots_cast").reset_index()

    def party_votes(party: str, name: str) -> pd.DataFrame:
        sub = top[top["candidate_party_lbl"] == party]
        return sub.groupby(keys)["vote_ct"].sum().rename(name).reset_index()

    house = results[results["contest_title"].str.startswith(HOUSE_PREFIX, na=False)].copy()
    house["nc_house_district"] = house["contest_title"].str.extract(r"(\d+)$").astype(int)
    districts = house.groupby(keys)["nc_house_district"].first().reset_index()

    out = ballots.merge(names, on=keys, how="left")
    out = out.merge(registered, on=keys, how="left")
    out = out.merge(party_votes("DEM", "top_dem_votes"), on=keys, how="left")
    out = out.merge(party_votes("REP", "top_rep_votes"), on=keys, how="left")
    out = out.merge(districts, on=keys, how="left")
    out.insert(0, "election_date", f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}")

    int_cols = (
        "registered_total",
        "top_dem_votes",
        "top_rep_votes",
        "reg_age_18_25",
        "reg_age_26_40",
        "reg_age_41_65",
        "reg_age_over_66",
    )
    for col in int_cols:
        out[col] = out[col].fillna(0).astype(int)
    out["nc_house_district"] = out["nc_house_district"].astype("Int64")
    return out


def main() -> None:
    frames = []
    for stamp in ELECTIONS:
        df = load_election(stamp)
        print(f"  {stamp}: {len(df)} precinct rows")
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out[out["registered_total"] > 0].copy()

    out["turnout_pct"] = (
        out["ballots_cast"] / out["registered_total"] * 100
    ).astype("Float64").round(2)
    contested = out["top_dem_votes"] + out["top_rep_votes"]
    out["dem_share_top"] = (
        out["top_dem_votes"] / contested.replace(0, pd.NA) * 100
    ).astype("Float64").round(2)

    out = out.sort_values(["election_date", "county", "precinct"]).reset_index(drop=True)
    PROCESSED.mkdir(exist_ok=True)
    dest = PROCESSED / "precinct_turnout.csv"
    out.to_csv(dest, index=False)
    print(f"\nwrote {dest}: {len(out)} rows")
    print(
        out.groupby(["election_date", "county"])
        .agg(
            precincts=("precinct", "count"),
            registered=("registered_total", "sum"),
            ballots=("ballots_cast", "sum"),
            mean_turnout=("turnout_pct", "mean"),
        )
        .round(1)
        .to_string()
    )


if __name__ == "__main__":
    main()
