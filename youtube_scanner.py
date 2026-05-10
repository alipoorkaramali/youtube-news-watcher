import os
import json
import sys
import traceback
import re
import subprocess
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import time   # <-- برای تلاش مجدد (retry) در صورت خطای ۵۰۰ یوتیوب

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "logs/new_videos.txt"
STATE_DIR = "cache/states"
MAX_ITEMS = 10
MAX_UNIQUE_CHANNELS = 5
MIN_CHECK_INTERVAL = 30
MAX_ATTEMPTS_LIMIT = 10

# ================== ابزارهای زمان ==================
def iran_offset():
    now = datetime.now()
    return timedelta(hours=4, minutes=30) if 3 <= now.month <= 9 else timedelta(hours=3, minutes=30)

def iran_now():
    return datetime.now(timezone.utc) + iran_offset()

def parse_iran_time(time_str):
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
    except:
        return None

def next_check_utc(iran_start, interval_min, attempt):
    today_iran = iran_now().date()
    start_dt_iran = datetime.combine(today_iran, iran_start)
    utc_offset = iran_offset()
    start_utc = (start_dt_iran - utc_offset).replace(tzinfo=timezone.utc)
    return start_utc + timedelta(minutes=interval_min * attempt)

# ================== تبدیل تاریخ میلادی به شمسی ==================
def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0):
        g_d_m[2] = 29
    gy2 = gy - 1600
    gy -= 1600
    if gm > 2:
        gy2 += 1
    days = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400 - 80 + gd + g_d_m[gm-1]
    jy = 979
    while days >= 365:
        if jy % 33 in [1, 5, 9, 13, 17, 22, 26, 30]:
            if days >= 366:
                days -= 366
                jy += 1
            else:
                break
        else:
            days -= 365
            jy += 1
    if jy % 33 in [1, 5, 9, 13, 17, 22, 26, 30]:
        jm_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    else:
        jm_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 30]
    jm = 1
    while days >= jm_days[jm-1]:
        days -= jm_days[jm-1]
        jm += 1
    jd = days + 1
    return (jy, jm, jd)

# ================== وضعیت ==================
def safe_name(*parts):
    raw = "_".join(parts)
    return re.sub(r'[^\w@.-]', '_', raw)[:60]

def get_state_path(channel_id, keyword):
    return os.path.join(STATE_DIR, safe_name(channel_id, keyword) + ".json")

def load_state(channel_id, keyword):
    path = get_state_path(channel_id, keyword)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"date": "", "found": False, "attempts": 0}

def save_state(channel_id, keyword, state):
    path = get_state_path(channel_id, keyword)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(state, f)

# ================== دریافت پلی‌لیست ساندکلاد با yt-dlp ==================
def fetch_soundcloud_playlist(playlist_url):
    """
    دریافت اطلاعات آهنگ‌های یک پلی‌لیست ساندکلاد با استفاده از yt-dlp.
    برمی‌گرداند لیستی از دیکشنری‌ها با کلیدهای title, link, published_date
    """
    print(f"  📡 دریافت پلی‌لیست ساندکلاد: {playlist_url}")
    try:
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "-J",
            "--no-warnings",
            playlist_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        tracks = []
        for entry in data.get('entries', []):
            title = entry.get('title')
            link = entry.get('webpage_url') or entry.get('url')
            upload_date_str = entry.get('upload_date')
            if upload_date_str:
                pub_date = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            else:
                timestamp = entry.get('timestamp')
                if timestamp:
                    pub_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                else:
                    pub_date = datetime.now(timezone.utc)
            if title and link:
                tracks.append({
                    "title": title,
                    "link": link,
                    "published_date": pub_date
                })
        return tracks
    except Exception as e:
        print(f"  ❌ خطا در دریافت پلی‌لیست ساندکلاد: {e}")
        return []

# ================== RSS یوتیوب ==================
RSS_CACHE = {}

# ‼️ اصلاح‌شده: اضافه کردن User‑Agent واقعی، کوکی‌ها و تلاش مجدد برای خطای ۵۰۰ یوتیوب
def fetch_rss_youtube(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"  📡 دریافت RSS یوتیوب برای {channel_id}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }

    # بارگذاری کوکی‌های یوتیوب از فایل cookies.txt (در صورت وجود)
    cookies = {}
    if os.path.exists('cookies.txt'):
        try:
            from http.cookiejar import MozillaCookieJar
            cj = MozillaCookieJar('cookies.txt')
            cj.load(ignore_discard=True, ignore_expires=True)
            cookies = {c.name: c.value for c in cj if c.domain.endswith('.youtube.com') or c.domain == 'www.youtube.com'}
        except Exception:
            pass

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)
            if resp.status_code == 200:
                break
            elif resp.status_code == 500 and attempt < max_retries:
                print(f"  ⚠️ خطای 500 (تلاش {attempt+1})، ۱۰ ثانیه صبر می‌کنیم...")
                time.sleep(10)
        except Exception as e:
            if attempt < max_retries:
                print(f"  ⚠️ استثنا در تلاش {attempt+1}: {e} - ۱۰ ثانیه صبر می‌کنیم...")
                time.sleep(10)
            else:
                raise

    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {'': 'http://www.w3.org/2005/Atom'}
    videos = []
    for entry in root.findall('entry', ns):
        title = entry.find('title', ns).text.strip()
        link = entry.find('link', ns).attrib['href']
        pub_str = entry.find('published', ns).text
        pub_date = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
        videos.append({"title": title, "link": link, "published_date": pub_date})
    RSS_CACHE[channel_id] = videos
    return videos

def fetch_rss(platform, channel_id):
    cache_key = f"{platform}_{channel_id}"
    if cache_key in RSS_CACHE:
        return RSS_CACHE[cache_key]

    try:
        if platform == 'youtube':
            videos = fetch_rss_youtube(channel_id)
        elif platform == 'soundcloud_playlist':
            videos = fetch_soundcloud_playlist(channel_id)
        else:
            print(f"  ❌ پلتفرم نامعتبر: {platform}")
            return []
    except Exception as e:
        print(f"  ❌ خطا در دریافت فید: {e}")
        return []

    RSS_CACHE[cache_key] = videos
    return videos

def get_relative_time(pub_date):
    delta = datetime.now(timezone.utc) - pub_date
    h = int(delta.total_seconds() // 3600)
    m = int((delta.total_seconds() % 3600) // 60)
    return f"{h} hours ago" if h > 0 else f"{m} minutes ago"

# ================== منطق اصلی ==================
def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            f.write("[]")
        return []
    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        raw = f.read().strip()
    if not raw:
        print("📭 watchlist.json خالی است.")
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ فایل JSON معتبر نیست: {e}")
        sys.exit(1)

    valid_items = []
    for idx, item in enumerate(items):
        plat = item.get('platform', 'youtube')
        cid = item.get('channel_id', '')
        keyword = item.get('title_keyword', '')
        start = item.get('start_time_iran', '')
        if not cid.strip():
            print(f"⚠️ آیتم {idx+1}: channel_id خالی است. نادیده گرفته شد.")
            continue
        if not keyword.strip():
            print(f"⚠️ آیتم {idx+1}: title_keyword خالی است. نادیده گرفته شد.")
            continue
        if not parse_iran_time(start):
            print(f"⚠️ آیتم {idx+1}: start_time_iran نامعتبر ('{start}'). نادیده گرفته شد.")
            continue
        valid_items.append({
            'platform': plat,
            'channel_id': cid.strip(),
            'title_keyword': keyword.strip(),
            'start_time_iran': start,
            'check_every_minutes': max(item.get('check_every_minutes', 60), MIN_CHECK_INTERVAL),
            'max_attempts': min(item.get('max_attempts', 5), MAX_ATTEMPTS_LIMIT)
        })

    if len(valid_items) > MAX_ITEMS:
        print(f"⚠️ تعداد آیتم‌ها بیش از {MAX_ITEMS} است. فقط {MAX_ITEMS} اول بررسی می‌شود.")
        valid_items = valid_items[:MAX_ITEMS]
    unique_channels = set(it['channel_id'] for it in valid_items)
    if len(unique_channels) > MAX_UNIQUE_CHANNELS:
        print(f"⚠️ تعداد کانال‌ها بیش از {MAX_UNIQUE_CHANNELS} است. اجرا متوقف شد.")
        sys.exit(1)
    return valid_items

def should_check(item, state):
    today = iran_now().date()
    if state.get('date') != str(today):
        state = {"date": str(today), "found": False, "attempts": 0}
        save_state(item['channel_id'], item['title_keyword'], state)

    if state.get('found'):
        return False, state

    if state['attempts'] >= item['max_attempts']:
        return False, state

    start_time = parse_iran_time(item['start_time_iran'])
    interval = item['check_every_minutes']
    next_utc = next_check_utc(start_time, interval, state['attempts'])
    now_utc = datetime.now(timezone.utc)
    return now_utc >= next_utc, state

def process_item(item):
    plat = item['platform']
    cid = item['channel_id']
    kw = item['title_keyword']
    state = load_state(cid, kw)
    check, state = should_check(item, state)
    if not check:
        return

    print(f"\n🔍 بررسی [{plat.upper()}] {cid} - '{kw}' (تلاش {state['attempts']+1})")
    videos = fetch_rss(plat, cid)
    if not videos:
        state['attempts'] += 1
        save_state(cid, kw, state)
        return

    # ========== فقط بخش زیر برای ساندکلاد تغییر کرده ==========
    if plat == 'soundcloud_playlist':
        today_greg = iran_now().date()
        jy, jm, jd = gregorian_to_jalali(today_greg.year, today_greg.month, today_greg.day)
        today_persian = (jy, jm, jd)

        persian_months = {
            'فروردین':1, 'اردیبهشت':2, 'خرداد':3,
            'تیر':4, 'مرداد':5, 'شهریور':6,
            'مهر':7, 'آبان':8, 'آذر':9,
            'دی':10, 'بهمن':11, 'اسفند':12
        }

        recent = []
        for v in videos:
            title = v['title']
            match = re.search(r'(\d{1,2})\s+'
                              r'(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)'
                              r'(?:\s+(\d{4}))?', title)
            if match:
                day = int(match.group(1))
                month = persian_months[match.group(2)]
                year = int(match.group(3)) if match.group(3) else jy
                if (year, month, day) == today_persian:
                    recent.append(v)
        # اگر تطابقی پیدا نشود، recent خالی می‌ماند
    else:
        # ========== بخش یوتیوب و سایر پلتفرم‌ها کاملاً بدون تغییر ==========
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = [v for v in videos if v['published_date'] >= cutoff]
    # ============================================================

    matched = None
    for v in recent:
        if kw.lower() in v['title'].lower():
            matched = v
            break

    if matched:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        existing = ""
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing = f.read()
        if matched['link'] not in existing:
            rel = get_relative_time(matched['published_date'])
            now_iso = datetime.now(timezone.utc).isoformat()
            plat_label = 'soundcloud' if plat == 'soundcloud_playlist' else plat
            line = f"{now_iso} | {plat_label} | {matched['title']} | {rel} | {matched['link']}\n"
            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(line)
            print(f"  ✅ ذخیره شد: {matched['title']} ({rel})")
            state['found'] = True
        else:
            print("  ℹ️ تکراری است")
            state['found'] = True
    else:
        print("  ❌ یافت نشد")
        state['attempts'] += 1

    save_state(cid, kw, state)

def main():
    print("🚀 شروع اسکن...")
    try:
        items = load_watchlist()
        if not items:
            print("ℹ️ هیچ آیتم معتبری برای بررسی وجود ندارد.")
            return
        for item in items:
            process_item(item)
        print("✅ اسکن به پایان رسید.")
    except Exception:
        print("💥 خطای پیش‌بینی نشده:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
