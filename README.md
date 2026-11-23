# Premier League Match Predictor

Predicting Premier League match results (home win / draw / away win) with machine learning.

## Project structure
- `data/raw/` – original match data (not uploaded to GitHub)
- `data/processed/` – cleaned data
- `notebooks/` – exploration and experiments
- `src/` – reusable code
- `models/` – trained models

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How to use
```bash
python src/download_data.py   # get the latest results, xG + upcoming fixtures
python src/train.py           # test the model week by week on past seasons
python src/predict.py         # predict the upcoming matches -> predictions/
```

## How it works
For every match the model only uses information known **before kickoff**:
- **Elo rating**: a running strength score per team, updated after every result
- **Form**: average points, goals scored/conceded and shots on target over the last 5 matches
- **xG (expected goals)**: average xG for and against over the last 20 matches — shows whether a team
  creates good chances or has just been lucky. Opta xG from Fantasy Premier League data (available from Dec 2022)
- **Bookmaker odds**: turned into probabilities

The final model (logistic regression on **Elo + xG + odds**) is **retrained every week** on all matches played so far, then predicts the next ones.

### Data sources
- Results, stats and odds: [football-data.co.uk](https://www.football-data.co.uk/englandm.php)
- xG, past seasons: [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League)
- xG, current season: the official [Fantasy Premier League](https://fantasy.premierleague.com) site
- Matches in all competitions (experiments): ESPN

## Results so far
Walk-forward test on 1,240 matches (2023/24 to Nov 2026), retraining every week:

| Model | Accuracy | Log loss (lower = better) |
|---|---|---|
| Always predict home win | 43.1% | 1.0741 |
| Elo only | 52.2% | 0.9854 |
| Elo + form | 52.4% | 0.9811 |
| Elo + form + odds | 52.5% | 0.9715 |
| Elo + form + xG + odds | 53.8% | 0.9717 |
| **Elo + xG + odds (final model)** | **53.5%** | **0.9711** |
| Bookmakers (benchmark) | 53.6% | 0.9688 |

Adding xG gets about 1 percentage point more results right — level with the bookmakers on accuracy —
but the probabilities barely improve, and the bookmakers still have the best log loss.
xG averaged over 20 matches worked better than 5 or 10.

### Which ML model?
Same walk-forward test, same features (`python src/compare_models.py`):

| Model | Accuracy | Log loss |
|---|---|---|
| **Logistic regression** | 52.5% | **0.9715** |
| Neural network | 52.8% | 0.9760 |
| Random forest | 51.6% | 0.9769 |
| K-nearest neighbours | 52.5% | 0.9877 |
| Gradient boosting | 51.0% | 0.9923 |

Logistic regression gives the best probabilities and is the fastest, so it stays.
Football results are noisy and the dataset is small, so complex models mostly fit noise —
better features (e.g. xG) are likely worth more than a fancier model.

### Experiments that didn't help
- **Rest days** (days since each team's last league match): log loss 0.9715 → 0.9720, so not used.
  Our data only has Premier League games, so it misses tiredness from midweek European and cup matches.
- **All competitions** (Champions League, Europa, Conference League, FA Cup, League Cup — 14,000 team-matches
  from ESPN, `python src/download_all_comps.py`). Tested, each against the final model (log loss 0.9711):

  | Added feature | Accuracy | Log loss |
  |---|---|---|
  | Days since last game (any competition) | 53.6% | 0.9726 |
  | Games in the last 14 days | 53.7% | 0.9715 |
  | Played a European game in the last 4 days | 53.5% | 0.9717 |
  | Points per game, last 5 (all competitions) | 53.6% | 0.9712 |
  | Goal difference, last 5 (all competitions) | 53.5% | 0.9706 |
  | All of the above | 53.5% | 0.9736 |

  None of these changes the results by more than random noise, so they're not used. Most likely the
  bookmaker odds and Elo ratings already reflect how tired or in-form a team is.

## Progress log
- Set up the project and the GitHub repo
- Added `src/download_data.py`: downloads 2016/17–2026/27 match results from [football-data.co.uk](https://www.football-data.co.uk/englandm.php) (run `python src/download_data.py`)
- Built features: Elo ratings, last-5-match form, bookmaker probabilities
- Added a week-by-week walk-forward test: model beats the home-win baseline by ~9 points, slightly behind the bookmakers
- Added predictions for upcoming fixtures (first predictions: matchweek of 21 Nov 2026)
- Compared 5 ML models — logistic regression was best, kept it
- Tried rest days as a feature — no improvement, left out of the model
- Added real xG (Opta, via FPL data) — accuracy 52.5% → 53.5%, now the final model
- Added every team's matches in all competitions (European + cups) and tested fatigue and all-competition form — no real improvement, not used
