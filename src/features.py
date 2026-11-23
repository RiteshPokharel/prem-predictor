"""Turn raw match results into features a model can learn from.

Every feature only uses information known BEFORE kickoff (no peeking at the future):
  - Elo ratings: a running strength score for each team, updated after every match
  - Form over the last 5 matches: points, goals scored/conceded, shots on target
  - Bookmaker odds converted to probabilities (the "market" view)
"""

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

FORM_WINDOW = 5
ELO_START = 1500       # rating for the teams in the first season
ELO_PROMOTED = 1420    # promoted teams are usually weaker than average
ELO_K = 20             # how fast ratings react to results
ELO_HOME_ADV = 60      # home advantage, in Elo points
ELO_SEASON_REGRESS = 0.2  # pull ratings 20% back to average between seasons

FORM_STATS = ["points", "gf", "ga", "sotf", "sota"]


def load_matches(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load every season CSV into one table, sorted by date."""
    frames = []
    for path in sorted(raw_dir.glob("E0_*.csv")):
        df = pd.read_csv(path, encoding="utf-8-sig", encoding_errors="replace")
        df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTR"]).copy()
        df["Season"] = path.stem.split("_")[1]
        frames.append(df)
    m = pd.concat(frames, ignore_index=True)
    m["Date"] = pd.to_datetime(m["Date"], dayfirst=True, format="mixed")
    return m.sort_values(["Date", "HomeTeam"]).reset_index(drop=True)


def odds_to_probs(df: pd.DataFrame) -> pd.DataFrame:
    """Average bookmaker odds -> probabilities (with the bookmaker margin removed)."""
    out = pd.DataFrame(index=df.index)
    for res in "HDA":
        odds = pd.Series(np.nan, index=df.index)
        for col in (f"Avg{res}", f"BbAv{res}", f"B365{res}"):  # column names changed over the years
            if col in df:
                odds = odds.fillna(pd.to_numeric(df[col], errors="coerce"))
        out[f"mkt_{res}"] = 1 / odds
    total = out.sum(axis=1)
    return out.div(total, axis=0)


class EloTracker:
    """Keeps a rating per team and updates it after each result."""

    def __init__(self):
        self.ratings: dict[str, float] = {}
        self.season = None

    def start_season(self, season: str, teams: set[str]) -> None:
        if self.season is None:
            self.ratings = {t: ELO_START for t in teams}
        else:
            mean = np.mean(list(self.ratings.values()))
            self.ratings = {
                t: r + ELO_SEASON_REGRESS * (mean - r) for t, r in self.ratings.items()
            }
        for t in teams:
            self.ratings.setdefault(t, ELO_PROMOTED)
        self.season = season

    def expected_home(self, home: str, away: str) -> float:
        diff = self.ratings[home] + ELO_HOME_ADV - self.ratings[away]
        return 1 / (1 + 10 ** (-diff / 400))

    def update(self, home: str, away: str, hg: int, ag: int) -> None:
        score = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        margin = np.log1p(abs(hg - ag)) if hg != ag else 1.0  # bigger wins move ratings more
        change = ELO_K * margin * (score - self.expected_home(home, away))
        self.ratings[home] += change
        self.ratings[away] -= change


def add_elo(m: pd.DataFrame) -> tuple[pd.DataFrame, EloTracker]:
    """Add pre-match Elo ratings. Returns the tracker so we can rate future fixtures."""
    elo = EloTracker()
    home_elo, away_elo = [], []
    for season, games in m.groupby("Season", sort=True):
        elo.start_season(season, set(games["HomeTeam"]) | set(games["AwayTeam"]))
        for row in games.itertuples():
            home_elo.append(elo.ratings[row.HomeTeam])
            away_elo.append(elo.ratings[row.AwayTeam])
            elo.update(row.HomeTeam, row.AwayTeam, row.FTHG, row.FTAG)
    m = m.copy()
    m["home_elo"] = home_elo
    m["away_elo"] = away_elo
    m["elo_diff"] = m["home_elo"] + ELO_HOME_ADV - m["away_elo"]
    return m, elo


def team_match_log(m: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match (each match appears twice: home view and away view)."""
    pts = {"H": (3, 0), "D": (1, 1), "A": (0, 3)}
    home = pd.DataFrame({
        "match_id": m.index, "Date": m["Date"], "team": m["HomeTeam"],
        "gf": m["FTHG"], "ga": m["FTAG"], "sotf": m["HST"], "sota": m["AST"],
        "points": m["FTR"].map(lambda r: pts[r][0]),
    })
    away = pd.DataFrame({
        "match_id": m.index, "Date": m["Date"], "team": m["AwayTeam"],
        "gf": m["FTAG"], "ga": m["FTHG"], "sotf": m["AST"], "sota": m["HST"],
        "points": m["FTR"].map(lambda r: pts[r][1]),
    })
    return pd.concat([home, away]).sort_values(["team", "Date"]).reset_index(drop=True)


def add_form(m: pd.DataFrame) -> pd.DataFrame:
    """Average of each team's last 5 matches, BEFORE the current one (shift(1) = no peeking)."""
    log = team_match_log(m)
    rolled = (
        log.groupby("team")[FORM_STATS]
        .transform(lambda s: s.shift(1).rolling(FORM_WINDOW, min_periods=1).mean())
    )
    log = pd.concat([log[["match_id", "team"]], rolled], axis=1)

    log = log.set_index(["match_id", "team"])
    m = m.copy()
    for side, team_col in (("home", "HomeTeam"), ("away", "AwayTeam")):
        keys = pd.MultiIndex.from_arrays([m.index, m[team_col]])
        vals = log.reindex(keys)[FORM_STATS].to_numpy()
        for i, s in enumerate(FORM_STATS):
            m[f"{side}_{s}"] = vals[:, i]
    return m


def latest_form(m: pd.DataFrame) -> pd.DataFrame:
    """Each team's form over its last 5 matches up to now (for predicting future fixtures)."""
    log = team_match_log(m)
    return log.groupby("team")[FORM_STATS].apply(lambda g: g.tail(FORM_WINDOW).mean())


def add_diffs(df: pd.DataFrame) -> pd.DataFrame:
    for s in FORM_STATS:
        df[f"diff_{s}"] = df[f"home_{s}"] - df[f"away_{s}"]
    return df


STATS_FEATURES = ["elo_diff"] + [f"{side}_{s}" for side in ("home", "away") for s in FORM_STATS] + [
    f"diff_{s}" for s in FORM_STATS
]
MARKET_FEATURES = ["mkt_H", "mkt_D", "mkt_A"]


def build_features(raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, EloTracker]:
    m = load_matches(raw_dir)
    m, elo = add_elo(m)
    m = add_form(m)
    m = add_diffs(m)
    m = pd.concat([m, odds_to_probs(m)], axis=1)
    return m, elo


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "processed" / "features.csv"
    feats, elo = build_features()
    cols = ["Date", "Season", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"] + STATS_FEATURES + MARKET_FEATURES
    feats[cols].to_csv(out, index=False)
    print(f"Saved {len(feats)} matches with {len(STATS_FEATURES)} stat features -> {out}")
    print("\nCurrent Elo top 5:")
    for team, r in sorted(elo.ratings.items(), key=lambda x: -x[1])[:5]:
        print(f"  {team:15s} {r:.0f}")
