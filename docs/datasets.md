# Dataset Registry

This file records the data assets used by the project. Raw and derived data files are local-only and are not committed to Git.

## Public Git Boundary

The following directories are local-only:

- `data/raw/`
- `data/interim/`
- `data/processed/`
- `outputs/`
- `logs/`

Git tracks only `.gitkeep` files in the data/log directories. The public repository should not include raw Reddit comments, submissions, annotation rows containing raw text, model predictions, or large output directories.

## Reddit COVID Vaccine Dataset

- Human-readable name: `christinegu27/reddit_covidvaccine_data`
- Source URL: `https://github.com/christinegu27/reddit_covidvaccine_data`
- Local raw path: `data/raw/external/reddit_covidvaccine_data`
- Source revision: `87185ea21a8fa08cc47d935bf723c36a34573b09`
- Raw files:
  - `reddit_data.csv`: Reddit comments from COVID-19 vaccine related submissions.
  - `submissions.csv`: Reddit submissions and crosspost metadata.
- Derived files:
  - `data/interim/covidvaccine_submissions.jsonl`
  - `data/interim/covidvaccine_comments.jsonl`
  - `data/interim/covidvaccine_thread_profiles.csv`
- Role: topic-specific data preparation, corrective-response measurement, and thread-level analysis.
- Limitation: the dataset is topic-specific and does not provide complete Reddit-wide user histories. Cross-subreddit measures are therefore observed within this dataset, not complete user-level platform histories.
- Public-release boundary: raw and derived comment-level files are not redistributed through this repository.

## Watchful1 / Pushshift Subreddit Archive

- Human-readable name: `Subreddit comments/submissions 2005-06 to 2024-12`
- Source URL: `https://academictorrents.com/details/1614740ac8c94505e4ecb9d88be8bed7b6afddd4`
- Local metadata path: `data/raw/archive/reddit_2024_12_subreddits.torrent`
- Intended raw path: `data/raw/archive/reddit/subreddits24/`
- Role: possible broader Reddit archive for expanding beyond the topic-specific dataset.
- Current status: torrent metadata was downloaded, but selective BitTorrent download from WSL did not obtain peers in the first attempt.
- Public-release boundary: archive files and filtered archive outputs are local-only.

Initial target files:

- `COVID19_comments.zst`, `COVID19_submissions.zst`
- `DebateVaccines_comments.zst`, `DebateVaccines_submissions.zst`
- `LockdownSkepticism_comments.zst`, `LockdownSkepticism_submissions.zst`
- `NoNewNormal_comments.zst`, `NoNewNormal_submissions.zst`
- `medicine_comments.zst`, `medicine_submissions.zst`

## Reddit Live Data API

- Human-readable name: Reddit for Researchers / Reddit API collection
- Local credential path: `.env`
- Role: optional future collection route only if valid access is granted.
- Current status: Reddit for Researchers API access was rejected on July 4, 2026.
- Repository status: no live API access is assumed.
- Ethical boundary: do not use browser login cookies as the default route.

## Derived Assets

Derived tables, predictions, models, and figures remain local under `outputs/` and are not committed.
