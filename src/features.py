"""Turn raw match results into features a model can learn from.

Every feature only uses information known BEFORE kickoff (no peeking at the future):
  - Elo ratings: a running strength score for each team, updated after every match
  - Form over the last 5 matches: points, goals scored/conceded, shots on target
  - xG (expected goals) for/against over the last 20 matches
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
XG_STATS = ["xgf", "xga"]   # expected goals for / against
XG_WINDOW = 20              # tested 5/10/20 — xG works best averaged over a longer stretch


def load_matches(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load every season CSV into one table, plus the newest results from ESPN, sorted by date."""
    frames = []
    for path in sorted(raw_dir.glob("E0_*.csv")):
        df = pd.read_csv(path, encoding="utf-8-sig", encoding_errors="replace")
        df = df.dropna(subset=["HomeTeam", "AwayTeam", "FTR"]).copy()
        df["Season"] = path.stem.split("_")[1]
        frames.append(df)
    m = pd.concat(frames, ignore_index=True)
    m["Date"] = pd.to_datetime(m["Date"], dayfirst=True, format="mixed")
    m["source"] = "football-data"
    m = pd.concat([m, fresh_espn_results(m, raw_dir)], ignore_index=True)
    m = m.sort_values(["Date", "HomeTeam"]).reset_index(drop=True)
    return add_xg(m, raw_dir)


def load_espn(raw_dir: Path = RAW_DIR) -> pd.DataFrame | None:
    """This season's results + upcoming fixtures from src/download_espn.py."""
    path = raw_dir / "espn_current.csv"
    if not path.exists():
        return None
    e = pd.read_csv(path, dtype={"Season": str})
    local = pd.to_datetime(e["Date"])
    e["Kickoff"] = local.dt.tz_localize("Europe/London")  # UK time: GMT in winter, BST in summer
    e["Date"] = local.dt.normalize()
    return e


def fresh_espn_results(m: pd.DataFrame, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Finished matches ESPN has that football-data.co.uk hasn't added yet."""
    e = load_espn(raw_dir)
    if e is None:
        return pd.DataFrame()
    e = e[e["completed"]]
    have = set(zip(m["Season"], m["HomeTeam"], m["AwayTeam"]))
    new = e[[k not in have for k in zip(e["Season"], e["HomeTeam"], e["AwayTeam"])]].copy()
    new["FTR"] = np.select([new["FTHG"] > new["FTAG"], new["FTHG"] == new["FTAG"]], ["H", "D"], "A")
    new["source"] = "espn"
    return new[["Season", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "source"]]


def add_xg(m: pd.DataFrame, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Attach each match's xG (from src/download_xg.py). Missing before Dec 2022."""
    path = raw_dir / "xg_matches.csv"
    m = m.copy()
    if not path.exists():
        m["home_xg"] = m["away_xg"] = np.nan
        return m
    xg = pd.read_csv(path, dtype={"Season": str})[["Season", "HomeTeam", "AwayTeam", "home_xg", "away_xg"]]
    return m.merge(xg, on=["Season", "HomeTeam", "AwayTeam"], how="left")


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
        "xgf": m["home_xg"], "xga": m["away_xg"],
        "points": m["FTR"].map(lambda r: pts[r][0]),
    })
    away = pd.DataFrame({
        "match_id": m.index, "Date": m["Date"], "team": m["AwayTeam"],
        "gf": m["FTAG"], "ga": m["FTHG"], "sotf": m["AST"], "sota": m["HST"],
        "xgf": m["away_xg"], "xga": m["home_xg"],
        "points": m["FTR"].map(lambda r: pts[r][1]),
    })
    return pd.concat([home, away]).sort_values(["team", "Date"]).reset_index(drop=True)


def add_form(m: pd.DataFrame, stats=FORM_STATS, window=FORM_WINDOW) -> pd.DataFrame:
    """Average of each team's last N matches, BEFORE the current one (shift(1) = no peeking)."""
    log = team_match_log(m)
    rolled = (
        log.groupby("team")[stats]
        .transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
    )
    log = pd.concat([log[["match_id", "team"]], rolled], axis=1)

    log = log.set_index(["match_id", "team"])
    m = m.copy()
    for side, team_col in (("home", "HomeTeam"), ("away", "AwayTeam")):
        keys = pd.MultiIndex.from_arrays([m.index, m[team_col]])
        vals = log.reindex(keys)[stats].to_numpy()
        for i, s in enumerate(stats):
            m[f"{side}_{s}"] = vals[:, i]
    return m


def latest_form(m: pd.DataFrame, stats=FORM_STATS, window=FORM_WINDOW) -> pd.DataFrame:
    """Each team's form over its last N matches up to now (for predicting future fixtures)."""
    log = team_match_log(m)
    return log.groupby("team")[stats].apply(lambda g: g.tail(window).mean())


def add_diffs(df: pd.DataFrame) -> pd.DataFrame:
    for s in FORM_STATS + XG_STATS:
        df[f"diff_{s}"] = df[f"home_{s}"] - df[f"away_{s}"]
    return df


STATS_FEATURES = ["elo_diff"] + [f"{side}_{s}" for side in ("home", "away") for s in FORM_STATS] + [
    f"diff_{s}" for s in FORM_STATS
]
XG_FEATURES = [f"{side}_{s}" for side in ("home", "away") for s in XG_STATS] + [
    f"diff_{s}" for s in XG_STATS
]
MARKET_FEATURES = ["mkt_H", "mkt_D", "mkt_A"]

# The features the final model uses (best in the walk-forward test, see README)
MODEL_FEATURES = ["elo_diff"] + XG_FEATURES + MARKET_FEATURES
# Backup model for fixtures that don't have bookmaker odds yet
NO_ODDS_FEATURES = ["elo_diff"] + XG_FEATURES


def build_features(raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, EloTracker]:
    m = load_matches(raw_dir)
    m, elo = add_elo(m)
    m = add_form(m)
    m = add_form(m, XG_STATS, XG_WINDOW)
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
