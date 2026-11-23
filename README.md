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
python src/download_data.py   # get the latest results + upcoming fixtures
python src/train.py           # test the model week by week on past seasons
python src/predict.py         # predict the upcoming matches -> predictions/
```

## How it works
For every match the model only uses information known **before kickoff**:
- **Elo rating**: a running strength score per team, updated after every result
- **Form**: average points, goals scored/conceded and shots on target over the last 5 matches
- **Bookmaker odds**: turned into probabilities

The model (logistic regression) is **retrained every week** on all matches played so far, then predicts the next ones.

## Results so far
Walk-forward test on 1,240 matches (2023/24 to Nov 2026), retraining every week:

| Model | Accuracy | Log loss (lower = better) |
|---|---|---|
| Always predict home win | 43.1% | 1.0741 |
| Elo only | 52.2% | 0.9854 |
| Elo + form | 52.4% | 0.9811 |
| Elo + form + odds | 52.5% | 0.9715 |
| Bookmakers (benchmark) | 53.6% | 0.9688 |

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

## Progress log
- Set up the project and the GitHub repo
- Added `src/download_data.py`: downloads 2016/17–2026/27 match results from [football-data.co.uk](https://www.football-data.co.uk/englandm.php) (run `python src/download_data.py`)
- Built features: Elo ratings, last-5-match form, bookmaker probabilities
- Added a week-by-week walk-forward test: model beats the home-win baseline by ~9 points, slightly behind the bookmakers
- Added predictions for upcoming fixtures (first predictions: matchweek of 21 Nov 2026)
- Compared 5 ML models — logistic regression was best, kept it
- Tried rest days as a feature — no improvement, left out of the model
