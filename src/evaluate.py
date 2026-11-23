"""Check saved predictions against the real results (the model's track record).

Reads every file in predictions/, finds the matches that have been played since,
and scores them. Saves predictions/track_record.csv.
Run:  python src/evaluate.py
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from features import load_matches

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

PRED_DIR = Path(__file__).resolve().parent.parent / "predictions"
PICK = {"Home": "H", "Draw": "D", "Away": "A"}


def load_predictions() -> pd.DataFrame:
    frames = []
    for path in sorted(PRED_DIR.glob("predictions_*.csv")):
        p = pd.read_csv(path)
        p["file"] = path.name
        frames.append(p)
    p = pd.concat(frames, ignore_index=True)
    for col in ("Home win", "Draw", "Away win"):
        p[col] = p[col].str.rstrip("%").astype(float) / 100
    # if a match was predicted in more than one file, keep the earliest prediction
    return p.drop_duplicates(["Home", "Away"], keep="first")


def main() -> None:
    preds = load_predictions()
    results = load_matches()
    results = results[results["Season"] == results["Season"].max()]
    results = results.rename(columns={"Date": "Played"})
    played = preds.merge(results[["Played", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]],
                         left_on=["Home", "Away"], right_on=["HomeTeam", "AwayTeam"])
    if played.empty:
        print("None of the predicted matches have been played yet.")
        return

    probs = played[["Home win", "Draw", "Away win"]].to_numpy()
    actual = played["FTR"].map({"H": 0, "D": 1, "A": 2}).to_numpy()
    played["Correct"] = played["Pick"].map(PICK) == played["FTR"]
    played["Chance given"] = probs[np.arange(len(played)), actual]

    table = pd.DataFrame({
        "Date": played["Played"].dt.strftime("%Y-%m-%d"),
        "Match": played["Home"] + " v " + played["Away"],
        "Score": played["FTHG"].astype(int).astype(str) + "-" + played["FTAG"].astype(int).astype(str),
        "Pick": played["Pick"],
        "Chance given to result": (played["Chance given"] * 100).round().astype(int).astype(str) + "%",
        "Correct": played["Correct"].map({True: "yes", False: "no"}),
    })
    print(table.to_string(index=False))

    n, right = len(played), played["Correct"].sum()
    log_loss = -np.log(played["Chance given"].clip(1e-9)).mean()
    print(f"\nCorrect: {right}/{n} ({right / n:.0%})   log loss: {log_loss:.4f}")
    print("(walk-forward test average: 53.5% correct, log loss 0.9711)")

    table.to_csv(PRED_DIR / "track_record.csv", index=False)


if __name__ == "__main__":
    main()
