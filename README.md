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
│   ├── scan1.yml                 # اسکن اصلی (Multi-Watcher)
│   ├── debug_scan.yml            # Full Diagnostic + ساخت کاتالوگ
│   ├── reset_log.yml             # ریست روزانه logs و cache
│   ├── download-from-catalog.yml # دانلود با /download روی Issue
│   └── add-item v1.yml           # افزودن آیتم به watchlist از فرم Actions
├── src/
│   ├── pre_check.py              # آیا الان باید اسکن شود؟
│   ├── run_checker.py            # wrapper اجرای اسکنر
│   ├── youtube_scanner.py        # منطق اسکن + تریگر دانلود
│   └── debug_youtube_rss.py      # diagnostic + catalog + Issue
├── config/
│   ├── watchlist.json            # لیست آیتم‌های پایش (منبع حقیقت)
│   └── saved_channels.txt        # کانال‌های ذخیره‌شده برای diagnostic
├── data/
│   ├── diagnostic_results.txt    # خروجی متنی diagnostic
│   ├── channel_catalog.md        # کاتالوگ خوانا برای انسان
│   └── catalog_index.json        # ایندکس شماره‌دار برای /download
├── cache/
│   ├── states/                   # وضعیت هر کانال+کلیدواژه
│   ├── seen_titles.json          # جلوگیری از دانلود تکراری
│   └── last_reset.log
├── logs/
│   └── new_videos.txt            # لاگ اسکن / پیام تریگر
├── requirements.txt
└── README.md
```

همهٔ مسیرهای پایدار در **`config/`** و **`data/`** و وضعیت اجرایی در **`cache/`** و **`logs/`** هستند. فایل تکراری در ریشه مخزن وجود ندارد.

---

## جریان کار کلی

```
┌─────────────────┐     pre_check      ┌──────────────────┐
│  config/        │ ─────────────────► │  scan لازم است؟  │
│  watchlist.json │                    └────────┬─────────┘
└─────────────────┘                             │ بله
                                                ▼
                                       ┌──────────────────┐
                                       │ youtube_scanner  │
                                       │ RSS / yt-dlp     │
                                       └────────┬─────────┘
                                                │ ویدیو جدید
                                                ▼
                                       ┌──────────────────┐
                                       │ workflow_dispatch│
                                       │ به مخزن downloader│
                                       └──────────────────┘

Diagnostic (جدا):
  config + saved_channels → RSS/SC → data/* + Issue کاتالوگ
```

1. **scan1** با `pre_check` فقط وقتی اجرا می‌شود که بر اساس `start_time_iran` و state زمان اسکن رسیده باشد.
2. اسکنر فید را می‌خواند، با `title_keyword` فیلتر می‌کند، تکراری‌ها را با `seen_titles` رد می‌کند.
3. در صورت یافتن آیتم جدید، درخواست دانلود به مخزن `new-youtube-SoundCloud-downloader` ارسال می‌شود.
4. **Diagnostic** مستقل است: کانال‌ها را پایش عمیق‌تر می‌کند، کاتالوگ می‌سازد و Issue را به‌روز می‌کند.

---

## ورک‌فلوها

| فایل | نام در Actions | تریگر | نقش |
|------|----------------|--------|-----|
| `scan1.yml` | YouTube Multi-Watcher | `workflow_dispatch` (معمولاً از cron خارجی) | pre-check → اسکن → کامیت logs/cache |
| `debug_scan.yml` | Full Diagnostic | فقط `workflow_dispatch` | diagnostic + کاتالوگ + کامیت data/config |
| `reset_log.yml` | Daily Reset | cron `45 20 * * *` UTC + دستی | خالی کردن logs و cache |
| `download-from-catalog.yml` | Download from Catalog | کامنت `/download N` روی Issue کاتالوگ | تریگر دانلودر costume |
| `add-item v1.yml` | Add Item to Watchlist | فرم `workflow_dispatch` | افزودن/جایگزینی آیتم در `config/watchlist.json` |

### scan1 (اسکنر اصلی)

1. Checkout  
2. `python src/pre_check.py` → اگر خروجی شامل `✅` نباشد، بقیهٔ jobها skip می‌شوند  
3. نصب `requirements.txt` + `yt-dlp`  
4. `python src/run_checker.py` → `src/youtube_scanner.py`  
5. بررسی پیام موفقیت تریگر در `logs/new_videos.txt`  
6. کامیت `logs/` و `cache/` با `git pull --rebase` قبل از push  

### Full Diagnostic

- ورودی اختیاری: `youtube_channel_id`، `soundcloud_url`، `save_to_list`
- اجرا: `python src/debug_youtube_rss.py`
- خروجی در `data/` و در صورت نیاز به‌روزرسانی `config/saved_channels.txt`
- به‌روزرسانی Issue کاتالوگ (عنوان: `📺 Channel Catalog – Download`)
- کامیت با rebase قبل از push

**زمان‌بندی Diagnostic فقط از cron-job.org است** (نه `schedule` داخل GitHub) تا با ساعت ایران قاطی نشود.

### Daily Reset

- هر روز ~۰۰:۱۵ به وقت ایران (`20:45 UTC`)
- `logs/new_videos.txt` را خالی و `cache/*` را پاک می‌کند تا روز بعد از صفر شروع شود

### Download from Catalog

- فقط وقتی روی Issue با عنوان دقیق کاتالوگ کامنت بزنید:  
  `/download 5`
- شماره از `data/catalog_index.json` خوانده می‌شود
- ورک‌فلو costume در مخزن downloader با `platform` / `url` / `format` تریگر می‌شود

### Add Item

فرم Actions با فیلدها:

| فیلد | توضیح |
|------|--------|
| `platform` | `youtube` یا `soundcloud` |
| `channel_id` | Channel ID یوتیوب یا URL ساندکلاد |
| `title_keyword` | کلیدواژه عنوان |
| `start_time_iran` | مثلاً `18:00` |
| `check_every_minutes` | پیش‌فرض ۳۰ |
| `max_attempts` | پیش‌فرض ۵ |

آیتم هم‌پلتفرم با همان `title_keyword` جایگزین می‌شود؛ در غیر این صورت اضافه می‌شود. فقط `config/watchlist.json` تغییر می‌کند.

---

## پیکربندی

### `config/watchlist.json`

آرایه‌ای از آبجکت‌ها:

```json
[
  {
    "platform": "youtube",
    "channel_id": "UCxxxxxxxx",
    "title_keyword": "اخبار ساعت شش",
    "start_time_iran": "18:00",
    "check_every_minutes": 30,
    "max_attempts": 5
  },
  {
    "platform": "soundcloud",
    "channel_id": "https://soundcloud.com/example",
    "title_keyword": "اخبار بامدادی",
    "start_time_iran": "08:00",
    "check_every_minutes": 30,
    "max_attempts": 5
  }
]
```

| فیلد | معنی |
|------|------|
| `platform` | `youtube` یا `soundcloud` |
| `channel_id` | ID کانال YT یا URL کامل SC |
| `title_keyword` | زیررشته در عنوان |
| `start_time_iran` | شروع پنجرهٔ چک (ساعت ایران) |
| `check_every_minutes` | فاصلهٔ تلاش‌ها |
| `max_attempts` | حداکثر تلاش در همان روز |

محدودیت‌های منطقی در اسکنر (برای پایداری Actions): تعداد آیتم و تعداد کانال یکتا محدود است.

### `config/saved_channels.txt`

لیست کانال‌های ذخیره‌شده برای Full Diagnostic (فرمت خطی؛ توسط اسکریپت diagnostic مدیریت می‌شود).

---

## Secrets مورد نیاز

در **Settings → Secrets and variables → Actions** این مخزن:

| Secret | استفاده |
|--------|----------|
| `GH_PAT` | اسکنر برای dispatch ورک‌فلو دانلودر |
| `GH_PAT1` | (اختیاری) اولویت در download-from-catalog |
| `GITHUB_TOKEN` | پیش‌فرض Actions برای commit/Issue (معمولاً خودکار) |

در مخزن **downloader** باید ورک‌فلو costume و دسترسی توکن مناسب وجود داشته باشد.

---

## زمان‌بندی

| کار | منبع زمان | زمان |
|-----|-----------|------|
| Full Diagnostic | [cron-job.org](https://cron-job.org) → `workflow_dispatch` | ۱۰:۳۰، ۱۴:۳۰، ۱۸:۳۰، ۲۲:۳۰ **Asia/Tehran** |
| Daily Reset | GitHub `schedule` | `45 20 * * *` UTC ≈ ۰۰:۱۵ ایران |
| Multi-Watcher (scan1) | معمولاً cron خارجی یا دستی | هر چند دقیقه/ساعت بسته به نیاز |

> داخل `debug_scan.yml` دیگر `schedule` گیت‌هاب نیست تا با cron-job.org دوبل نشود.

برای اتصال cron-job.org به GitHub از API  
`POST /repos/{owner}/{repo}/actions/workflows/debug_scan.yml/dispatches`  
با توکن دارای دسترسی `actions:write` استفاده کنید.

---

## دانلود از کاتالوگ

1. یک‌بار **Full Diagnostic** را اجرا کنید تا `data/catalog_index.json` و Issue ساخته/به‌روز شوند.  
2. Issue با عنوان: **`📺 Channel Catalog – Download`**  
3. کامنت:

```text
/download 12
```

4. ورک‌فلو این مخزن شماره را resolve می‌کند و costume downloader را صدا می‌زند.  
5. نتیجه به‌صورت کامنت روی همان Issue نوشته می‌شود.

---

## اجرای دستی

از تب **Actions**:

- **YouTube Multi-Watcher** → Run workflow  
- **Full Diagnostic** → Run workflow (اختیاری: channel جدید)  
- **Daily Reset** → Run workflow  
- **Add Item to Watchlist** → فرم را پر کنید  

یا با API:

```bash
curl -X POST \
  -H "Authorization: token YOUR_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/alipoorkaramali/youtube-news-watcher/actions/workflows/scan1.yml/dispatches \
  -d '{"ref":"main"}'
```

---

## اسکریپت‌ها

| مسیر | نقش |
|------|-----|
| `src/pre_check.py` | خواندن `config/watchlist.json` + state؛ چاپ `✅` اگر باید اسکن شود |
| `src/run_checker.py` | فراخوانی `python src/youtube_scanner.py` |
| `src/youtube_scanner.py` | منطق اسکن، state، dedupe، تریگر دانلود |
| `src/debug_youtube_rss.py` | diagnostic، کاتالوگ، Issue |

مسیرهای ثابت در کد (پس از بارگذاری):

- Watchlist / saved channels → `config/`
- Diagnostic / catalog → `data/`
- State / seen titles → `cache/`
- لاگ اسکن → `logs/new_videos.txt`

---

## نکات فنی

- **Timezone:** منطق پنجرهٔ زمانی بر اساس ساعت ایران (`UTC+3:30`).
- **Race روی push:** ورک‌فلوهای diagnostic و scan قبل از push از `git pull --rebase origin main` استفاده می‌کنند تا با Reset همزمان تداخل کمتر شود.
- **Downloader:** تریگر به `alipoorkaramali/new-youtube-SoundCloud-downloader` و فایل ورک‌فلو costume.
- **وابستگی‌ها:** `requirements.txt` برای اسکن؛ diagnostic علاوه بر آن `requests`، `soundcloud-lib` و باینری `yt-dlp` را در job نصب می‌کند.
- **مانیتورینگ:** می‌توانید وضعیت runها را از Actions یا با ابزارهایی مثل `gitty` در Termux ببینید.

---

## مجوز و مالکیت

مخزن خصوصی/شخصی متعلق به [alipoorkaramali](https://github.com/alipoorkaramali). استفاده و تغییر مطابق تنظیمات دسترسی همان حساب.

---

*آخرین به‌روزرسانی ساختار: مسیرهای یکدست `src/` + `config/` + `data/` بدون فایل تکراری در ریشه.*
