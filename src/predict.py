"""Predict the upcoming Premier League matches.

Trains on every match played so far, then predicts the fixtures in data/raw/fixtures.csv.
Run after downloading fresh data:
    python src/download_data.py
    python src/predict.py
"""

import warnings
from pathlib import Path

import pandas as pd

from features import (
    ELO_HOME_ADV, FORM_STATS, MARKET_FEATURES, RAW_DIR, STATS_FEATURES,
    add_diffs, build_features, latest_form, odds_to_probs,
)
from train import FIRST_TRAIN_SEASON, make_model

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

OUT_DIR = Path(__file__).resolve().parent.parent / "predictions"
FEATURES = STATS_FEATURES + MARKET_FEATURES


def load_fixtures() -> pd.DataFrame:
    fx = pd.read_csv(RAW_DIR / "fixtures.csv", encoding="utf-8-sig", encoding_errors="replace")
    fx = fx[fx["Div"] == "E0"].copy()
    fx["Date"] = pd.to_datetime(fx["Date"], dayfirst=True, format="mixed")
    return fx.reset_index(drop=True)


def fixture_features(fx: pd.DataFrame, history: pd.DataFrame, elo) -> pd.DataFrame:
    form = latest_form(history)
    fx["home_elo"] = fx["HomeTeam"].map(elo.ratings)
    fx["away_elo"] = fx["AwayTeam"].map(elo.ratings)
    fx["elo_diff"] = fx["home_elo"] + ELO_HOME_ADV - fx["away_elo"]
    for side, col in (("home", "HomeTeam"), ("away", "AwayTeam")):
        for s in FORM_STATS:
            fx[f"{side}_{s}"] = fx[col].map(form[s])
    fx = add_diffs(fx)
    return pd.concat([fx, odds_to_probs(fx)], axis=1)


def main() -> None:
    history, elo = build_features()
    fx = load_fixtures()
    if fx.empty:
        print("No upcoming Premier League fixtures found. Run src/download_data.py first.")
        return

    unknown = set(fx["HomeTeam"]) | set(fx["AwayTeam"])
    unknown -= set(elo.ratings)
    if unknown:
        print(f"Warning: no history for {unknown} (team name mismatch?)")

    fx = fixture_features(fx, history, elo)
    train = history[history["Season"] >= FIRST_TRAIN_SEASON]
    model = make_model().fit(train[FEATURES], train["FTR"])
    probs = pd.DataFrame(model.predict_proba(fx[FEATURES]), columns=model.classes_)

    out = pd.DataFrame({
        "Date": fx["Date"].dt.strftime("%a %d %b"),
        "Home": fx["HomeTeam"],
        "Away": fx["AwayTeam"],
        "Home win": (probs["H"] * 100).round().astype(int).astype(str) + "%",
        "Draw": (probs["D"] * 100).round().astype(int).astype(str) + "%",
        "Away win": (probs["A"] * 100).round().astype(int).astype(str) + "%",
        "Pick": probs[["H", "D", "A"]].idxmax(axis=1).map(
            {"H": "Home", "D": "Draw", "A": "Away"}),
    })
    print(f"Trained on {len(train)} matches up to {history['Date'].max():%d %b %Y}\n")
    print(out.to_string(index=False))

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"predictions_{fx['Date'].min():%Y-%m-%d}.csv"
    out.to_csv(path, index=False)
    print(f"\nSaved -> {path.relative_to(OUT_DIR.parent)}")


if __name__ == "__main__":
    main()
