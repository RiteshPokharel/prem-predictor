"""Download every Premier League team's matches in ALL competitions from ESPN.

Premier League, Champions League, Europa League, Conference League, FA Cup, League Cup...
This lets the model see how busy/tired a team is and how it has been doing in other games.

Saves data/raw/all_comps.csv (one row per team per match).
First run downloads every season (~220 small requests); later runs only refresh the current season.
Run:  python src/download_all_comps.py          (or --all to re-download everything)
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

from features import load_matches

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_PATH = RAW_DIR / "all_comps.csv"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
ARSENAL = 359  # in the Premier League every season, so we use them to find each season's 20 teams
SEASONS = list(range(2016, 2027))  # ESPN season 2016 = 2016/17
CURRENT = SEASONS[-1]

# Pre-season friendlies and exhibitions are ignored
COMPETITIVE = ("English Premier League", "Champions League", "Europa League", "Conference League",
               "FA Cup", "Carabao Cup", "League Cup", "Super Cup", "Club World Cup")
NOT_COMPETITIVE = ("Asia Trophy", "Community Shield", "Friendly")


def is_competitive(name: str) -> bool:
    return any(k in name for k in COMPETITIVE) and not any(k in name for k in NOT_COMPETITIVE)


def get(path: str) -> dict:
    with urlopen(ESPN + path, timeout=30) as r:
        data = json.loads(r.read())
    time.sleep(0.3)  # be polite to the server
    return data


def season_code(season: int) -> str:
    return f"{season % 100:02d}{(season + 1) % 100:02d}"


def premier_league_team_ids(season: int) -> set[str]:
    events = get(f"eng.1/teams/{ARSENAL}/schedule?season={season}")["events"]
    events += get(f"eng.1/teams/{ARSENAL}/schedule?season={season}&fixture=true").get("events", [])
    ids = {str(ARSENAL)}
    for e in events:
        for c in e["competitions"][0]["competitors"]:
            ids.add(c["team"]["id"])
    return ids


def team_matches(team_id: str, season: int) -> list[dict]:
    rows = []
    for e in get(f"all/teams/{team_id}/schedule?season={season}").get("events", []):
        comp_name = e.get("league", {}).get("name", "")
        c = e["competitions"][0]
        if not c["status"]["type"].get("completed"):
            continue
        sides = {x["homeAway"]: x for x in c["competitors"]}
        me = next(x for x in c["competitors"] if x["team"]["id"] == team_id)
        opp = next(x for x in c["competitors"] if x["team"]["id"] != team_id)
        rows.append({
            "event_id": e["id"],
            "season": season_code(season),
            "date": e["date"][:10],
            "competition": comp_name,
            "competitive": is_competitive(comp_name),
            "team_id": team_id,
            "opponent": opp["team"]["displayName"],
            "home": me is sides.get("home"),
            "gf": float(me["score"]["value"]),
            "ga": float(opp["score"]["value"]),
            "winner": bool(me.get("winner")),  # for cup games decided on penalties
        })
    return rows


def name_espn_teams(df: pd.DataFrame) -> dict[str, str]:
    """Match ESPN team ids to our team names by lining up Premier League home games by date."""
    m = load_matches()
    our_home = {(d, t) for d, t in zip(m["Date"].dt.strftime("%Y-%m-%d"), m["HomeTeam"])}
    by_date = {}
    for d, t in our_home:
        by_date.setdefault(d, []).append(t)
    names = {}
    pl_home = df[(df["competition"] == "English Premier League") & df["home"]]
    for team_id, games in pl_home.groupby("team_id"):
        votes = Counter()
        for d in games["date"]:
            # ESPN dates are UTC, so also check the day before (late kick-offs)
            prev = (pd.Timestamp(d) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            for day in (d, prev):
                votes.update(by_date.get(day, []))
        names[team_id] = votes.most_common(1)[0][0]
    return names


def main() -> None:
    full = "--all" in sys.argv or not OUT_PATH.exists()
    seasons = SEASONS if full else [CURRENT]
    rows = []
    for season in seasons:
        ids = premier_league_team_ids(season)
        for team_id in sorted(ids):
            rows.extend(team_matches(team_id, season))
        print(f"Downloaded all competitions {season_code(season)}: {len(ids)} teams")

    new = pd.DataFrame(rows)
    if not full:
        old = pd.read_csv(OUT_PATH, dtype={"season": str, "team_id": str, "event_id": str})
        new = pd.concat([old[old["season"] != season_code(CURRENT)], new], ignore_index=True)

    names = name_espn_teams(new)
    new["team"] = new["team_id"].map(names)
    new = new.drop_duplicates(["event_id", "team_id"]).sort_values(["team", "date"])
    new.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(new)} team-matches -> {OUT_PATH.name}")


if __name__ == "__main__":
    main()
