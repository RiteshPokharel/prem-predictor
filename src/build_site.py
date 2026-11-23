"""Build the dashboard: site/index.html, a single page you can open in any browser.

Reads the files in predictions/ and puts the data into site/template.html
(which loads site/style.css and site/app.js).
Run after predict.py and evaluate.py:  python src/build_site.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PRED = ROOT / "predictions"
SITE = ROOT / "site"


def percent(col: pd.Series) -> pd.Series:
    return col.str.rstrip("%").astype(float) / 100


def main() -> None:
    upcoming = json.loads((PRED / "next_round.json").read_text())

    record = pd.read_csv(PRED / "track_record.csv")
    record[["home", "away"]] = record["Match"].str.split(" v ", n=1, expand=True)
    record[["hg", "ag"]] = record["Score"].str.split("-", expand=True).astype(int)
    played = [
        {"date": r.Date, "gw": None if pd.isna(r.Gameweek) else int(r.Gameweek), "home": r.home, "away": r.away, "hg": r.hg, "ag": r.ag,
         "pH": h, "pD": d, "pA": a, "result": r.Result, "pick": r.Pick, "correct": r.Correct == "yes"}
        for r, h, d, a in zip(record.itertuples(), percent(record["Home win"]),
                              percent(record["Draw"]), percent(record["Away win"]))
    ]

    table = pd.read_csv(PRED / "table.csv")
    ratings = pd.read_csv(PRED / "elo_history.csv")
    data = {
        "updated": upcoming["results_up_to"],
        "fixtures": upcoming["matches"],
        "record": played,
        "table": table.rename(columns={"xG for": "xgf", "xG against": "xga"}).to_dict("records"),
        "ratings": {team: g[["Date", "Season", "Elo"]].values.tolist() for team, g in ratings.groupby("Team")},
    }

    page = (SITE / "template.html").read_text()
    page = page.replace("/*DATA*/null", json.dumps(data, separators=(",", ":")))
    (SITE / "index.html").write_text(page)
    print(f"Built -> {(SITE / 'index.html').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
