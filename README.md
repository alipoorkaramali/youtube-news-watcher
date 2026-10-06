# youtube-news-watcher

سیستم پایش خودکار کانال‌های **YouTube** و **SoundCloud** با GitHub Actions.

هدف: در بازه‌های زمانی مشخص (به وقت ایران)، عنوان‌های جدید را با کلیدواژه مطابقت دهد، در صورت یافتن آیتم جدید تریگر دانلود را به مخزن downloader بفرستد، و خروجی‌های تشخیصی/کاتالوگ را در همین مخزن نگه دارد.

---

## فهرست مطالب

- [ساختار مخزن](#ساختار-مخزن)
- [جریان کار کلی](#جریان-کار-کلی)
- [ورک‌فلوها](#ورک‌فلوها)
- [پیکربندی](#پیکربندی)
- [Secrets مورد نیاز](#secrets-مورد-نیاز)
- [زمان‌بندی](#زمان‌بندی)
- [دانلود از کاتالوگ](#دانلود-از-کاتالوگ)
- [اجرای دستی](#اجرای-دستی)
- [اسکریپت‌ها](#اسکریپت‌ها)
- [نکات فنی](#نکات-فنی)

---

## ساختار مخزن

```
youtube-news-watcher/
├── .github/workflows/
│   ├── scan1.yml
│   ├── debug_scan.yml
│   ├── reset_log.yml
│   ├── download-from-catalog.yml
│   └── add-item v1.yml
├── src/
├── config/
├── data/
├── cache/
├── logs/
├── requirements.txt
└── README.md
```

---

## دانلود از کاتالوگ

روی Issue با عنوان **`📺 Channel Catalog – Download`** کامنت بزنید:

```text
/download <شماره> [audio|video] [mega|repo]
```

### حالت (mode)

| آرگومان | معنی | ورک‌فلو |
|---------|------|----------|
| *(خالی)* یا `video` | پیش‌فرض / دستی | **costume** |
| `audio` | نسخهٔ صوتی خودکار | **auto** |

### مقصد (dest)

| آرگومان | معنی | مخزن |
|---------|------|------|
| *(خالی)* یا `repo` | ذخیره داخل مخزن | `new-youtube-SoundCloud-downloader` |
| `mega` | آپلود به Mega.nz | `youtube-SoundCloud-downloader` |

### مثال‌ها

| کامنت | نتیجه |
|--------|--------|
| `/download 5` | costume + repo |
| `/download 5 audio` | auto صوتی + repo |
| `/download 5 video mega` | costume ویدیو + Mega |
| `/download 12 audio mega` | auto صوتی + Mega |

### نگاشت ورک‌فلو

| mode | dest | فایل |
|------|------|------|
| audio | repo | `Multi-Platform Downloader-auto🔐.yml` |
| video/default | repo | `Multi-Platform Downloader-costume🔐.yml` |
| audio | mega | `Multi-Platform-Downloader-auto-Mega.yml` |
| video/default | mega | `Multi-Platform-Downloader-costume-Mega.yml` |

---

## ورک‌فلوها

| فایل | تریگر | نقش |
|------|--------|-----|
| `scan1.yml` | `workflow_dispatch` | اسکن |
| `debug_scan.yml` | `workflow_dispatch` | diagnostic + کاتالوگ |
| `reset_log.yml` | cron + دستی | ریست logs/cache |
| `download-from-catalog.yml` | `/download ...` | تریگر دانلودر |
| `add-item v1.yml` | فرم | افزودن به watchlist |

---

## پیکربندی `config/watchlist.json`

```json
[
  {
    "platform": "youtube",
    "channel_id": "UCxxxxxxxx",
    "title_keyword": "اخبار ساعت شش",
    "start_time_iran": "18:00",
    "check_every_minutes": 30,
    "max_attempts": 5
  }
]
```

---

## Secrets

| Secret | استفاده |
|--------|----------|
| `GH_PAT` / `GH_PAT1` | dispatch به هر دو مخزن دانلودر |
| `GITHUB_TOKEN` | commit و Issue |

---

## زمان‌بندی

| کار | منبع | زمان |
|-----|------|------|
| Diagnostic | cron-job.org | ۱۰:۳۰ ۱۴:۳۰ ۱۸:۳۰ ۲۲:۳۰ Tehran |
| Reset | GitHub | `45 20 * * *` UTC |

---

## اسکریپت‌ها

| مسیر | نقش |
|------|-----|
| `src/pre_check.py` | آیا اسکن لازم است؟ |
| `src/run_checker.py` | اجرای اسکنر |
| `src/youtube_scanner.py` | اسکن + تریگر |
| `src/debug_youtube_rss.py` | diagnostic |

---

*ساختار: `src/` + `config/` + `data/`.*
