name: YouTube Multi-Watcher

on:
  schedule:
    - cron: '*/15 * * * *'   # هر ۱۵ دقیقه
  workflow_dispatch:
    inputs:
      watchlist_json:
        description: 'لیست کانال‌ها و ویدیوها (JSON)'
        required: false
        type: string
        default: ''

jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # ذخیره امن JSON در فایل (بدون تزریق مستقیم به شل)
      - name: Save watchlist from manual input
        if: github.event_name == 'workflow_dispatch' && github.event.inputs.watchlist_json != ''
        env:
          INPUT_JSON: ${{ github.event.inputs.watchlist_json }}
        run: |
          printf '%s\n' "$INPUT_JSON" > watchlist.json
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add watchlist.json
          git diff --staged --quiet || (git commit -m "Update watchlist from input" && git push)

      # اگر فایل watchlist.json وجود نداشته باشد (مثلاً اولین اجرای زمان‌بندی‌شده)، فایل خالی بساز
      - name: Ensure watchlist.json exists
        run: |
          if [ ! -f watchlist.json ]; then
            echo '[]' > watchlist.json
          fi

      - uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scanner
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
        run: python youtube_scanner.py

      - name: Commit logs and cache
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add logs/new_videos.txt cache/ watchlist.json
          git diff --staged --quiet || (git commit -m "Update logs & cache" && git push)
