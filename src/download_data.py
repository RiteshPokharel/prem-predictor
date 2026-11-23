"""Download Premier League match results from football-data.co.uk.

Saves one CSV per season into data/raw/, e.g. data/raw/E0_2425.csv
Run from the project folder:  python src/download_data.py
"""

from pathlib import Path
from urllib.request import urlopen

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"

# Season codes: "1617" = 2016/17 ... "2627" = 2026/27 (in progress)
SEASONS = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2016, 2027)]


def download_season(season: str) -> Path:
    url = BASE_URL.format(season=season)
    out_path = RAW_DIR / f"E0_{season}.csv"
    with urlopen(url, timeout=30) as response:
        out_path.write_bytes(response.read())
    return out_path


def download_fixtures() -> Path:
    """Upcoming matches (all leagues) with bookmaker odds."""
    out_path = RAW_DIR / "fixtures.csv"
    with urlopen(FIXTURES_URL, timeout=30) as response:
        out_path.write_bytes(response.read())
    return out_path


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        try:
            path = download_season(season)
            print(f"Downloaded {season} -> {path.name}")
        except Exception as e:
            print(f"Failed {season}: {e}")
    try:
        print(f"Downloaded upcoming fixtures -> {download_fixtures().name}")
    except Exception as e:
        print(f"Failed fixtures: {e}")

    from download_xg import main as download_xg
    try:
        download_xg()
    except Exception as e:
        print(f"Failed xG: {e}")


if __name__ == "__main__":
    main()
