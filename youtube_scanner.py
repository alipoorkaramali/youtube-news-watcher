import requests
import xml.etree.ElementTree as ET
import os, json, sys, traceback, re
from datetime import datetime, timedelta, timezone

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "logs/new_videos.txt"
STATE_DIR = "cache/states"
CACHE_CHANNEL_DIR = "cache/channels"   # کش شناسه کانال (در صورت نیاز)
CACHE_TITLE_DIR = "cache/titles"       # کش کلیدواژه عنوان (در صورت نیاز)

MAX_ITEMS = 10
MAX_UNIQUE_CHANNELS = 5
MIN_CHECK_INTERVAL = 30
MAX_ATTEMPTS_LIMIT = 10

# ================== ابزارهای زمان ایران ==================
def iran_offset():
    now = datetime.now()
    if 3 <= now.month <= 9:
        return timedelta(hours=4, minutes=30)
    else:
        return timedelta(hours=3, minutes=30)

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
    start_utc = start_dt_iran - iran_offset()
    return start_utc + timedelta(minutes=interval_min * attempt)

# ================== کش‌ها ==================
def safe_name(*parts):
    raw = "_".join(parts)
    return re.sub(r'[^\w@.-]', '_', raw)[:60]

def load_cache(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content if content else None
    return None

def save_cache(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(value)

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

# ================== RSS ==================
RSS_CACHE = {}

def fetch_rss(channel_id):
    if channel_id in RSS_CACHE:
        return RSS_CACHE[channel_id]
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"  📡 دریافت RSS برای {channel_id}")
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; YT-Watcher/1.0)'})
        resp.raise_for_status()
    except Exception as e:
        print(f"  ❌ خطا RSS: {e}")
        return []
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

def get_relative_time(pub_date):
    delta = datetime.now(timezone.utc) - pub_date
    h = int(delta.total_seconds() // 3600)
    m = int((delta.total_seconds() % 3600) // 60)
    if h > 0:
        return f"{h} hours ago"
    return f"{m} minutes ago"

# ================== منطق اصلی ==================
def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        print(f"📭 فایل {WATCHLIST_FILE} وجود ندارد. ساختن فایل خالی.")
        with open(WATCHLIST_FILE, 'w') as f:
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
    # اعتبارسنجی فیلدهای اجباری
    valid_items = []
    for idx, item in enumerate(items):
        if 'channel_id' not in item or not item['channel_id'].startswith('UC'):
            print(f"⚠️ آیتم {idx+1}: فیلد channel_id معتبر نیست. نادیده گرفته شد.")
            continue
        if 'title_keyword' not in item or not item['title_keyword'].strip():
            print(f"⚠️ آیتم {idx+1}: فیلد title_keyword خالی است. نادیده گرفته شد.")
            continue
        if 'start_time_iran' not in item or not parse_iran_time(item['start_time_iran']):
            print(f"⚠️ آیتم {idx+1}: start_time_iran نامعتبر است. نادیده گرفته شد.")
            continue
        valid_items.append(item)
    if len(valid_items) > MAX_ITEMS:
        print(f"⚠️ تعداد آیتم‌ها بیش از {MAX_ITEMS} است. فقط {MAX_ITEMS} مورد اول بررسی می‌شود.")
        valid_items = valid_items[:MAX_ITEMS]
    unique_channels = set(item['channel_id'] for item in valid_items)
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

    max_attempts = min(item.get('max_attempts', 5), MAX_ATTEMPTS_LIMIT)
    if state['attempts'] >= max_attempts:
        return False, state

    start_time = parse_iran_time(item['start_time_iran'])
    if not start_time:
        return False, state

    interval = max(item.get('check_every_minutes', 60), MIN_CHECK_INTERVAL)
    next_utc = next_check_utc(start_time, interval, state['attempts'])
    now_utc = datetime.now(timezone.utc)
    return now_utc >= next_utc, state

def process_item(item):
    channel_id = item['channel_id']
    keyword = item['title_keyword'].strip()
    state = load_state(channel_id, keyword)
    check, state = should_check(item, state)
    if not check:
        return state, None

    print(f"\n🔍 بررسی: {channel_id} - '{keyword}' (تلاش {state['attempts']+1})")
    videos = fetch_rss(channel_id)
    if not videos:
        return state, None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    recent = [v for v in videos if v['published_date'] >= cutoff]
    matched = None
    for v in recent:
        if keyword.lower() in v['title'].lower():
            matched = v
            break

    if matched:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            existing = f.read()
        if matched['link'] not in existing:
            rel = get_relative_time(matched['published_date'])
            now_iso = datetime.now(timezone.utc).isoformat()
            line = f"{now_iso} | {matched['title']} | {rel} | {matched['link']}\n"
            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(line)
            print(f"  ✅ ذخیره شد: {matched['title']} ({rel})")
            state['found'] = True
        else:
            print("  ℹ️ ویدیو تکراری است")
            state['found'] = True
    else:
        print("  ❌ یافت نشد")
        state['attempts'] += 1

    save_state(channel_id, keyword, state)
    return state, matched

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
