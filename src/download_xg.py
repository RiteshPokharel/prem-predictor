"""Download expected goals (xG) for every Premier League match.

xG = how many goals a team "should" have scored, based on the quality of its chances (Opta data).
Source: Fantasy Premier League (FPL), which records xG for every player in every match
from December 2022 onwards. We add up the players' xG to get each team's xG per match.

  - Past seasons:   github.com/vaastav/Fantasy-Premier-League (archived FPL data)
  - Current season: the official FPL website, fantasy.premierleague.com

Saves data/raw/xg_matches.csv.  Run:  python src/download_xg.py
"""

import io
import json
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
ARCHIVE_URL = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws/merged_gw.csv"
FPL_API = "https://fantasy.premierleague.com/api/"

PAST_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
CURRENT_SEASON = "2026-27"

# FPL team names -> football-data.co.uk team names
TEAM_NAMES = {
    "Man Utd": "Man United",
    "Spurs": "Tottenham",
    "Sheffield Utd": "Sheffield United",
    "Nott'm Forest": "Nott'm Forest",
    "Coventry City": "Coventry",
    "Hull City": "Hull",
    "Ipswich Town": "Ipswich",
    "Leicester City": "Leicester",
    "Luton Town": "Luton",
    "Leeds United": "Leeds",
    "Norwich City": "Norwich",
    "Watford FC": "Watford",
}


def season_code(season: str) -> str:
    """'2022-23' -> '2223' (same codes as the match files)."""
    return season[2:4] + season[5:7]


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=60) as r:
        return r.read()


def past_season_players(season: str) -> pd.DataFrame:
    """One row per player per match: fixture, team, home/away, xG."""
    df = pd.read_csv(io.BytesIO(fetch(ARCHIVE_URL.format(season=season))), low_memory=False)
    return df[["fixture", "team", "was_home", "expected_goals", "kickoff_time"]]


def current_season_players() -> pd.DataFrame:
    """Same as above, built from the live FPL website (one download per gameweek)."""
    boot = json.loads(fetch(FPL_API + "bootstrap-static/"))
    fixtures = {f["id"]: f for f in json.loads(fetch(FPL_API + "fixtures/"))}
    team_name = {t["id"]: t["name"] for t in boot["teams"]}
    player_team = {p["id"]: p["team"] for p in boot["elements"]}
    done_gws = sorted({f["event"] for f in fixtures.values() if f["finished"] and f["event"]})

    rows = []
    for gw in done_gws:
        live = json.loads(fetch(FPL_API + f"event/{gw}/live/"))["elements"]
        for p in live:
            xg = float(p["stats"]["expected_goals"])
            team = player_team.get(p["id"])
            games = [e for e in p["explain"] if fixtures[e["fixture"]]["finished"]]
            mins = {e["fixture"]: next((s["value"] for s in e["stats"] if s["identifier"] == "minutes"), 0)
                    for e in games}
            total_mins = sum(mins.values())
            for fid, m in mins.items():
                f = fixtures[fid]
                if m == 0 or team not in (f["team_h"], f["team_a"]):
                    continue  # didn't play, or moved clubs mid-season
                rows.append({
                    "fixture": fid,
                    "team": team_name[team],
                    "was_home": team == f["team_h"],
                    "expected_goals": xg * m / total_mins,  # split double gameweeks by minutes
                    "kickoff_time": f["kickoff_time"],
                })
    return pd.DataFrame(rows)


def to_team_matches(players: pd.DataFrame, season: str) -> pd.DataFrame:
    """Add up player xG -> one row per match with home xG and away xG."""
    players = players.copy()
    players["team"] = players["team"].replace(TEAM_NAMES)
    players["expected_goals"] = pd.to_numeric(players["expected_goals"], errors="coerce")
    g = players.groupby(["fixture", "was_home"]).agg(
        team=("team", "first"), xg=("expected_goals", "sum"), kickoff=("kickoff_time", "first"))
    g = g.reset_index().pivot(index="fixture", columns="was_home")
    out = pd.DataFrame({
        "Season": season_code(season),
        "Date": pd.to_datetime(g[("kickoff", True)]).dt.date,
        "HomeTeam": g[("team", True)],
        "AwayTeam": g[("team", False)],
        "home_xg": g[("xg", True)].round(2),
        "away_xg": g[("xg", False)].round(2),
    })
    # Before Dec 2022 FPL had no xG: it shows up as 0.0 for both teams -> mark as missing
    no_xg = (out["home_xg"] == 0) & (out["away_xg"] == 0)
    out.loc[no_xg, ["home_xg", "away_xg"]] = None
    return out.sort_values("Date").reset_index(drop=True)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for season in PAST_SEASONS:
        frames.append(to_team_matches(past_season_players(season), season))
        print(f"Downloaded xG {season}: {frames[-1]['home_xg'].notna().sum()} matches")
    frames.append(to_team_matches(current_season_players(), CURRENT_SEASON))
    print(f"Downloaded xG {CURRENT_SEASON}: {frames[-1]['home_xg'].notna().sum()} matches")

    out = pd.concat(frames, ignore_index=True)
    path = RAW_DIR / "xg_matches.csv"
    out.to_csv(path, index=False)
    print(f"Saved -> {path.name}")


if __name__ == "__main__":
    main()
