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

## Progress log
- Set up the project and the GitHub repo
- Added `src/download_data.py`: downloads 2016/17–2026/27 match results from [football-data.co.uk](https://www.football-data.co.uk/englandm.php) (run `python src/download_data.py`)
