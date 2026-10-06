# youtube-news-watcher

YouTube & SoundCloud playlist/channel watcher with GitHub Actions.

## Layout

```
├── .github/workflows/   # CI workflows
├── src/                 # Python scripts
├── config/              # watchlist & saved channels
├── data/                # diagnostic output & catalogs
├── cache/               # runtime state
├── logs/                # scan logs
└── requirements.txt
```

## Scripts

| Script | Role |
|--------|------|
| `src/debug_youtube_rss.py` | Full diagnostic (cron-job.org / manual) |
| `src/youtube_scanner.py` | Main scanner |
| `src/pre_check.py` | Pre-check before scan |
| `src/run_checker.py` | Runner for scanner |

## Config

- `config/watchlist.json` – channels/playlists to watch
- `config/saved_channels.txt` – persisted channel list

## Schedule

Diagnostic runs are triggered only via **cron-job.org** (`workflow_dispatch`), not GitHub `schedule`.
