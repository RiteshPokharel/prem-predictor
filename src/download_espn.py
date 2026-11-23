"""Download the latest Premier League results and upcoming fixtures from ESPN.

football-data.co.uk (our main source) only updates a day or two after each round.
ESPN updates right after the final whistle, so we use it to fill in the newest results
and to get the list of upcoming matches.

Saves data/raw/espn_current.csv.  Run:  python src/download_espn.py
"""

import json
import time
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_PATH = RAW_DIR / "espn_current.csv"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/"
CURRENT_SEASON = 2026  # ESPN season 2026 = 2026/27
SEASON_CODE = "2627"

# ESPN team names -> football-data.co.uk team names
TEAM_NAMES = {
    "AFC Bournemouth": "Bournemouth",
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Brentford": "Brentford",
    "Brighton & Hove Albion": "Brighton",
    "Burnley": "Burnley",
    "Chelsea": "Chelsea",
    "Coventry City": "Coventry",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Liverpool": "Liverpool",
    "Luton Town": "Luton",
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle United": "Newcastle",
    "Norwich City": "Norwich",
    "Nottingham Forest": "Nott'm Forest",
    "Sheffield United": "Sheffield United",
    "Southampton": "Southampton",
    "Sunderland": "Sunderland",
    "Tottenham Hotspur": "Tottenham",
    "Watford": "Watford",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}


def get(path: str) -> dict:
    with urlopen(ESPN + path, timeout=30) as r:
        data = json.loads(r.read())
    time.sleep(0.3)  # be polite to the server
    return data


def our_name(espn_name: str) -> str:
    if espn_name not in TEAM_NAMES:
        raise ValueError(f"Unknown ESPN team name '{espn_name}' - add it to TEAM_NAMES")
    return TEAM_NAMES[espn_name]


def fpl_rounds() -> pd.DataFrame:
    """Official gameweek (round) number of every match, from the Fantasy Premier League site."""
    from download_xg import FPL_API, TEAM_NAMES as FPL_NAMES
    with urlopen(FPL_API + "bootstrap-static/", timeout=30) as r:
        teams = {t["id"]: FPL_NAMES.get(t["name"], t["name"]) for t in json.loads(r.read())["teams"]}
    with urlopen(FPL_API + "fixtures/", timeout=30) as r:
        fixtures = json.loads(r.read())
    return pd.DataFrame([
        {"HomeTeam": teams[f["team_h"]], "AwayTeam": teams[f["team_a"]], "Round": f["event"]}
        for f in fixtures
    ])


def main() -> None:
    teams = get("teams")["sports"][0]["leagues"][0]["teams"]
    events = {}
    for t in teams:
        tid = t["team"]["id"]
        for q in (f"season={CURRENT_SEASON}", f"season={CURRENT_SEASON}&fixture=true"):
            for e in get(f"teams/{tid}/schedule?{q}").get("events", []):
                events[e["id"]] = e  # same match appears for both teams -> keep once

    rows = []
    for e in events.values():
        c = e["competitions"][0]
        side = {x["homeAway"]: x for x in c["competitors"]}
        done = bool(c["status"]["type"].get("completed"))
        score = lambda x: float(x["score"]["value"]) if done else None
        rows.append({
            "Season": SEASON_CODE,
            "Date": pd.Timestamp(e["date"]).tz_convert("Europe/London").strftime("%Y-%m-%d %H:%M"),
            "HomeTeam": our_name(side["home"]["team"]["displayName"]),
            "AwayTeam": our_name(side["away"]["team"]["displayName"]),
            "FTHG": score(side["home"]),
            "FTAG": score(side["away"]),
            "completed": done,
            "status": c["status"]["type"]["name"],
        })
    df = pd.DataFrame(rows).sort_values("Date")
    df = df.merge(fpl_rounds(), on=["HomeTeam", "AwayTeam"], how="left")
    df.to_csv(OUT_PATH, index=False)
    print(f"Downloaded ESPN: {df['completed'].sum()} results, {(~df['completed']).sum()} upcoming "
          f"-> {OUT_PATH.name}")
    if df["Round"].isna().any():
        print(f"Warning: no gameweek number for {df['Round'].isna().sum()} matches")


if __name__ == "__main__":
    main()
