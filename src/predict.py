"""Predict the upcoming Premier League matches.

Trains on every match played so far (including the newest ESPN results), then predicts
the matches in the next week. Uses bookmaker odds from data/raw/fixtures.csv when they're
available; for fixtures without odds yet it uses the backup model (Elo + xG only).

Run after downloading fresh data:
    python src/download_data.py
    python src/predict.py
"""

import json
import warnings
from pathlib import Path

import pandas as pd

from features import (
    ELO_HOME_ADV, MARKET_FEATURES, MODEL_FEATURES, NO_ODDS_FEATURES, RAW_DIR,
    XG_STATS, XG_WINDOW, build_features, latest_form, load_espn, odds_to_probs,
)
from train import FIRST_TRAIN_SEASON, make_model

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

OUT_DIR = Path(__file__).resolve().parent.parent / "predictions"
MATCHES_AHEAD = 10  # one full round
DAYS_AHEAD = 7      # fallback if gameweek numbers are missing


def load_odds() -> pd.DataFrame:
    """Bookmaker odds for upcoming matches (football-data.co.uk fixtures file)."""
    path = RAW_DIR / "fixtures.csv"
    if not path.exists():
        return pd.DataFrame(columns=["HomeTeam", "AwayTeam"])
    fx = pd.read_csv(path, encoding="utf-8-sig", encoding_errors="replace")
    fx = fx[fx["Div"] == "E0"]
    probs = odds_to_probs(fx)
    return pd.concat([fx[["HomeTeam", "AwayTeam"]], probs], axis=1)


def upcoming_fixtures(history: pd.DataFrame) -> pd.DataFrame:
    """The next week of matches that haven't been played yet."""
    espn = load_espn()
    if espn is None:
        raise SystemExit("No fixtures found. Run src/download_data.py first.")
    played = set(zip(history["HomeTeam"], history["AwayTeam"], history["Season"]))
    fx = espn[~espn["completed"]]
    fx = fx[[k not in played for k in zip(fx["HomeTeam"], fx["AwayTeam"], fx["Season"])]]
    fx = fx.sort_values("Kickoff")
    if fx.empty:
        raise SystemExit("No upcoming matches.")
    if fx["Round"].notna().all():
        # the next 10 matches, plus the rest of any gameweek they belong to
        rounds = set(fx["Round"].head(MATCHES_AHEAD))
        fx = fx[fx["Round"].isin(rounds)]
    else:
        first = fx["Kickoff"].iloc[0].normalize()
        fx = fx[fx["Kickoff"] < first + pd.Timedelta(days=DAYS_AHEAD)]
    fx = fx.merge(load_odds(), on=["HomeTeam", "AwayTeam"], how="left")
    return fx.reset_index(drop=True)


def fixture_features(fx: pd.DataFrame, history: pd.DataFrame, elo) -> pd.DataFrame:
    xg_form = latest_form(history, XG_STATS, XG_WINDOW)
    unknown = (set(fx["HomeTeam"]) | set(fx["AwayTeam"])) - set(elo.ratings)
    if unknown:
        raise SystemExit(f"No history for {unknown} - team name mismatch?")
    fx["elo_diff"] = fx["HomeTeam"].map(elo.ratings) + ELO_HOME_ADV - fx["AwayTeam"].map(elo.ratings)
    for side, col in (("home", "HomeTeam"), ("away", "AwayTeam")):
        for s in XG_STATS:
            fx[f"{side}_{s}"] = fx[col].map(xg_form[s])
    for s in XG_STATS:
        fx[f"diff_{s}"] = fx[f"home_{s}"] - fx[f"away_{s}"]
    return fx


def train_model(history: pd.DataFrame, features: list[str]):
    train = history[history["Season"] >= FIRST_TRAIN_SEASON]
    train = train.dropna(subset=[f for f in features if f in MARKET_FEATURES])
    return make_model().fit(train[features], train["FTR"]), len(train)


def main() -> None:
    history, elo = build_features()
    fx = fixture_features(upcoming_fixtures(history), history, elo)

    has_odds = fx[MARKET_FEATURES].notna().all(axis=1)
    probs = pd.DataFrame(index=fx.index, columns=["H", "D", "A"], dtype=float)
    for features, rows in ((MODEL_FEATURES, has_odds), (NO_ODDS_FEATURES, ~has_odds)):
        if rows.any():
            model, n = train_model(history, features)
            p = pd.DataFrame(model.predict_proba(fx.loc[rows, features]),
                             columns=model.classes_, index=fx.index[rows])
            probs.loc[rows] = p[["H", "D", "A"]]

    out = pd.DataFrame({
        "Kick-off": fx["Kickoff"].dt.strftime("%a %d %b %H:%M %Z"),
        "Home": fx["HomeTeam"],
        "Away": fx["AwayTeam"],
        "Home win": (probs["H"] * 100).round().astype(int).astype(str) + "%",
        "Draw": (probs["D"] * 100).round().astype(int).astype(str) + "%",
        "Away win": (probs["A"] * 100).round().astype(int).astype(str) + "%",
        "Pick": probs.astype(float).idxmax(axis=1).map({"H": "Home", "D": "Draw", "A": "Away"}),
        "Model": has_odds.map({True: "Elo+xG+odds", False: "Elo+xG (no odds yet)"}),
    })
    print(f"Using results up to {history['Date'].max():%a %d %b %Y} "
          f"({(history['source'] == 'espn').sum()} newest from ESPN)\n")
    print(out.to_string(index=False))

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"predictions_{fx['Kickoff'].min():%Y-%m-%d}.csv"
    out.to_csv(path, index=False)
    print(f"\nSaved -> {path.relative_to(OUT_DIR.parent)}")
    export_team_data(history, elo)

    next_round = [
        {"kickoff": k.isoformat(), "round": None if pd.isna(r) else int(r), "home": h, "away": a,
         "pH": round(float(p["H"]), 4), "pD": round(float(p["D"]), 4), "pA": round(float(p["A"]), 4),
         "odds": bool(o)}
        for k, r, h, a, (_, p), o in zip(fx["Kickoff"], fx["Round"], fx["HomeTeam"], fx["AwayTeam"],
                                          probs.iterrows(), has_odds)
    ]
    summary = {"results_up_to": f"{history['Date'].max():%Y-%m-%d}", "matches": next_round}
    (OUT_DIR / "next_round.json").write_text(json.dumps(summary, indent=1))


def export_team_data(history: pd.DataFrame, elo) -> None:
    """League table, ratings and rating history for the dashboard."""
    season = history["Season"].max()
    games = history[history["Season"] == season]
    rows = []
    for side, other in (("Home", "Away"), ("Away", "Home")):
        gf, ga = ("FTHG", "FTAG") if side == "Home" else ("FTAG", "FTHG")
        rows.append(pd.DataFrame({
            "Team": games[f"{side}Team"], "GF": games[gf], "GA": games[ga],
            "W": games[gf] > games[ga], "D": games[gf] == games[ga], "L": games[gf] < games[ga],
        }))
    table = pd.concat(rows).groupby("Team").sum()
    table["P"] = table[["W", "D", "L"]].sum(axis=1)
    table[["GF", "GA"]] = table[["GF", "GA"]].astype(int)
    table["GD"] = table["GF"] - table["GA"]
    table["Pts"] = 3 * table["W"] + table["D"]
    table = table.sort_values(["Pts", "GD", "GF"], ascending=False)
    xg = latest_form(history, XG_STATS, XG_WINDOW)
    table["Elo"] = table.index.map(elo.ratings).round().astype(int)
    table["xG for"] = table.index.map(xg["xgf"]).round(2)
    table["xG against"] = table.index.map(xg["xga"]).round(2)
    table = table[["P", "W", "D", "L", "GF", "GA", "GD", "Pts", "Elo", "xG for", "xG against"]]
    table.insert(0, "Pos", range(1, len(table) + 1))
    table.to_csv(OUT_DIR / "table.csv", index_label="Team")

    recent = history[history["Season"] >= sorted(history["Season"].unique())[-2]]
    ratings = pd.concat([
        recent[["Date", "Season", "HomeTeam", "home_elo_after"]].set_axis(["Date", "Season", "Team", "Elo"], axis=1),
        recent[["Date", "Season", "AwayTeam", "away_elo_after"]].set_axis(["Date", "Season", "Team", "Elo"], axis=1),
    ]).sort_values(["Team", "Date"])
    ratings["Elo"] = ratings["Elo"].round(1)
    ratings.to_csv(OUT_DIR / "elo_history.csv", index=False)


if __name__ == "__main__":
    main()
