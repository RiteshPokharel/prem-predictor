"""Walk-forward test: pretend we're living through past seasons week by week.

Every week we retrain the model on ALL matches played before that week,
then predict that week's matches. This is exactly how the model will be used
for real, so the scores are an honest estimate of how good it is.

Run:  python src/train.py
"""

import warnings

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import MARKET_FEATURES, STATS_FEATURES, build_features

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

CLASSES = ["A", "D", "H"]          # sklearn sorts labels alphabetically
FIRST_TRAIN_SEASON = "1718"         # 2016/17 is a warm-up season for the Elo ratings
TEST_SEASONS = ["2324", "2425", "2526", "2627"]

MODELS = {
    "Elo only": ["elo_diff"],
    "Elo + form": STATS_FEATURES,
    "Elo + form + odds": STATS_FEATURES + MARKET_FEATURES,
}


def make_model():
    return make_pipeline(
        SimpleImputer(strategy="mean"),
        StandardScaler(),
        LogisticRegression(C=0.1, max_iter=2000),
    )


def walk_forward(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Retrain every week, predict that week. Returns probabilities for A, D, H."""
    probs = np.full((len(df), 3), np.nan)
    train_pool = df["Season"] >= FIRST_TRAIN_SEASON
    test = df["Season"].isin(TEST_SEASONS)
    weeks = df["Date"].dt.to_period("W")

    for week in weeks[test].unique():
        in_week = (weeks == week) & test
        week_start = df.loc[in_week, "Date"].min()
        train = train_pool & (df["Date"] < week_start)
        model = make_model().fit(df.loc[train, features], df.loc[train, "FTR"])
        probs[in_week.to_numpy()] = model.predict_proba(df.loc[in_week, features])
    return probs


def score(y: pd.Series, probs: np.ndarray) -> dict:
    pred = np.array(CLASSES)[probs.argmax(axis=1)]
    return {
        "accuracy": accuracy_score(y, pred),
        "log_loss": log_loss(y, probs, labels=CLASSES),
    }


def main() -> None:
    df, _ = build_features()
    test = df["Season"].isin(TEST_SEASONS).to_numpy()
    y = df.loc[test, "FTR"]
    print(f"Testing on {test.sum()} matches from seasons {', '.join(TEST_SEASONS)}")
    print("(model retrained every week using only past matches)\n")

    results = {}

    # Baseline 1: always predict a home win, with the historical H/D/A rates as probabilities
    rates = df.loc[~test & (df["Season"] >= FIRST_TRAIN_SEASON), "FTR"].value_counts(normalize=True)
    base = np.tile([rates["A"], rates["D"], rates["H"]], (test.sum(), 1))
    results["Always home win"] = score(y, base)

    for name, feats in MODELS.items():
        probs = walk_forward(df, feats)
        results[name] = score(y, probs[test])

    # Benchmark: the bookmakers' own odds
    mkt = df.loc[test, ["mkt_A", "mkt_D", "mkt_H"]].to_numpy()
    ok = ~np.isnan(mkt).any(axis=1)
    results["Bookmakers (benchmark)"] = score(y[ok], mkt[ok])

    table = pd.DataFrame(results).T
    table["accuracy"] = (table["accuracy"] * 100).round(1).astype(str) + "%"
    table["log_loss"] = table["log_loss"].round(4)
    print(table.to_string())
    print("\naccuracy: % of matches where the most likely result was right (higher = better)")
    print("log_loss: how good the probabilities are (lower = better)")


if __name__ == "__main__":
    main()
