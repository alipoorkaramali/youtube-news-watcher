# youtube-news-watcher

YouTube & SoundCloud watcher with GitHub Actions.

## Layout

```
├── .github/workflows/
├── src/           # Python scripts
├── config/        # watchlist.json, saved_channels.txt
├── data/          # diagnostic + catalogs
├── cache/
├── logs/
└── requirements.txt
```

Scripts read/write only under `config/` and `data/` (plus `cache/` and `logs/` for runtime).

Diagnostic schedule: **cron-job.org** only (`workflow_dispatch`).
