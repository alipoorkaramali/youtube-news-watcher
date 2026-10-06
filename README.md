# youtube-news-watcher

YouTube & SoundCloud watcher with GitHub Actions.

## Layout

```
├── .github/workflows/   # CI workflows
├── src/                 # Python scripts
│   ├── debug_youtube_rss.py
│   ├── youtube_scanner.py
│   ├── pre_check.py
│   └── run_checker.py
├── config/              # watchlist & saved channels
│   ├── watchlist.json
│   └── saved_channels.txt
├── data/                # diagnostic output & catalogs
│   ├── diagnostic_results.txt
│   ├── channel_catalog.md
│   └── catalog_index.json
├── cache/               # runtime state
├── logs/                # scan logs
└── requirements.txt
```

## Schedule

Diagnostic is triggered only via **cron-job.org** (`workflow_dispatch`), not GitHub native `schedule`.
