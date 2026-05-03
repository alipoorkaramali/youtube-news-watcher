import requests
import xml.etree.ElementTree as ET
import os, json, re
from datetime import datetime, timedelta, timezone

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "logs/new_videos.txt"
STATE_DIR = "cache/states"
CACHE_CHANNEL_DIR = "cache/channels"
CACHE_TITLE_DIR = "cache/titles"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

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

# ================== مدیریت کش ==================
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

def get_channel_cache_path(channel):
    return os.path.join(CACHE_CHANNEL_DIR, safe_name(channel) + ".txt")

def load_channel_id(channel):
    return load_cache(get_channel_cache_path(channel))

def save_channel_id(channel, cid):
    save_cache(get_channel_cache_path(channel), cid)

def get_title_cache_path(channel, desc):
    return os.path.join(CACHE_TITLE_DIR, safe_name(channel, desc) + ".txt")

def load_title_keyword(channel, desc):
    return load_cache(get_title_cache_path(channel, desc))

def save_title_keyword(channel, desc, keyword):
    save_cache(get_title_cache_path(channel, desc), keyword)

def get_state_path(channel, desc):
    return os.path.join(STATE_DIR, safe_name(channel, desc) + ".json")

def load_state(channel, desc):
    path = get_state_path(channel, desc)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"date": "", "found": False, "attempts": 0}

def save_state(channel, desc, state):
    path = get_state_path(channel, desc)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(state, f)

# ================== شناسایی کانال ==================
def extract_channel_id_from_url(url):
    m = re.search(r'/channel/(UC[\w-]+)', url)
    return m.group(1) if m else None

def extract_channel_id_from_handle(handle):
    if handle.startswith('@'):
        handle = handle[1:]
    url = f'https://www.youtube.com/@{handle}/about'
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-US,en;q=0.9'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        m = re.search(r'var ytInitialData\s*=\s*({.*?});', resp.text)
        if m:
            data = json.loads(m.group(1))
            cid = data.get('metadata', {}).get('channelMetadataRenderer', {}).get('externalId')
            if cid: return cid
        m2 = re.search(r'<meta itemprop="channelId" content="(UC[\w-]+)"', resp.text)
        if m2: return m2.group(1)
    except Exception as e:
        print(f"⚠️ خطا در استخراج شناسه: {e}")
    return None

def find_channel_with_deepseek(name):
    if not DEEPSEEK_API_KEY:
        return None
    prompt = (
        f"Find the official YouTube channel handle for: '{name}'. "
        "Return ONLY the handle starting with @, or 'NOT_FOUND'."
    )
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [
        {"role": "system", "content": "Only output the handle starting with @."},
        {"role": "user", "content": prompt}
    ], "max_tokens": 50, "temperature": 0}
    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"].strip().strip('"\'')
        if answer.startswith('@'):
            return answer
        elif answer and answer != 'NOT_FOUND' and re.match(r'^[\w.-]+$', answer):
            return f"@{answer}"
    except Exception as e:
        print(f"⚠️ خطای DeepSeek: {e}")
    return None

def resolve_channel_id(channel_input):
    cached = load_channel_id(channel_input)
    if cached and cached.startswith('UC'):
        print(f"  📦 شناسه از کش: {cached}")
        return cached

    if 'youtube.com' in channel_input or 'youtu.be' in channel_input:
        cid = extract_channel_id_from_url(channel_input)
        if cid:
            save_channel_id(channel_input, cid)
            return cid

    if channel_input.startswith('@'):
        cid = extract_channel_id_from_handle(channel_input)
        if cid:
            save_channel_id(channel_input, cid)
            return cid
        corrected = find_channel_with_deepseek(channel_input[1:])
        if corrected:
            cid = extract_channel_id_from_handle(corrected)
            if cid:
                save_channel_id(channel_input, cid)
                return cid

    handle = find_channel_with_deepseek(channel_input)
    if handle:
        cid = extract_channel_id_from_handle(handle)
        if cid:
            save_channel_id(channel_input, cid)
            return cid
    return None

def guess_title_keyword(channel_input, title_desc):
    cached = load_title_keyword(channel_input, title_desc)
    if cached:
        print(f"  📦 کلیدواژه از کش: «{cached}»")
        return cached
    if not DEEPSEEK_API_KEY:
        return None
    prompt = (
        f"Channel: '{channel_input}'.\n"
        f"I need to find a daily video described as: '{title_desc}'.\n"
        "What is a common keyword or short phrase that likely appears in the video title? "
        "Output only the keyword/phrase in the same language as the channel. If unknown, say 'UNKNOWN'."
    )
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "deepseek-chat", "messages": [
        {"role": "system", "content": "Only output the keyword/phrase."},
        {"role": "user", "content": prompt}
    ], "max_tokens": 50, "temperature": 0}
    try:
        r = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"].strip().strip('"\'')
        if answer and answer.upper() != "UNKNOWN":
            print(f"  🤖 کلیدواژه پیشنهادی: «{answer}»")
            save_title_keyword(channel_input, title_desc, answer)
            return answer
    except Exception as e:
        print(f"  ⚠️ خطای DeepSeek: {e}")
    return None

# ================== RSS ==================
RSS_CACHE = {}

def fetch_rss(channel_id):
    if channel_id in RSS_CACHE:
        return RSS_CACHE[channel_id]
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"  📡 دریافت RSS: {channel_id}")
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
        return []
    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        items = json.load(f)
    if len(items) > MAX_ITEMS:
        print(f"⚠️ تعداد آیتم‌ها بیش از {MAX_ITEMS} است. فقط {MAX_ITEMS} مورد اول بررسی می‌شود.")
        items = items[:MAX_ITEMS]
    unique_channels = set(item['channel'] for item in items)
    if len(unique_channels) > MAX_UNIQUE_CHANNELS:
        print(f"⚠️ تعداد کانال‌ها بیش از {MAX_UNIQUE_CHANNELS} است. اجرا متوقف شد.")
        return []
    return items

def should_check(item, state):
    today = iran_now().date()
    if state.get('date') != str(today):
        state = {"date": str(today), "found": False, "attempts": 0}
        save_state(item['channel'], item['title_desc'], state)

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

def process_item(item, channel_id, title_keyword):
    state = load_state(item['channel'], item['title_desc'])
    check, state = should_check(item, state)
    if not check:
        return state, None

    print(f"\n🔍 بررسی: {item['channel']} - {item['title_desc']} (تلاش {state['attempts']+1})")
    videos = fetch_rss(channel_id)
    if not videos:
        return state, None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    recent = [v for v in videos if v['published_date'] >= cutoff]
    matched = None
    for v in recent:
        if title_keyword.lower() in v['title'].lower():
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

    save_state(item['channel'], item['title_desc'], state)
    return state, matched

def main():
    watchlist = load_watchlist()
    if not watchlist:
        print("📭 فهرست تماشا خالی است.")
        return

    channel_map = {}
    for item in watchlist:
        channel_map.setdefault(item['channel'], []).append(item)

    for channel_input, items in channel_map.items():
        channel_id = resolve_channel_id(channel_input)
        if not channel_id:
            print(f"❌ شناسه کانال برای '{channel_input}' پیدا نشد.")
            continue
        RSS_CACHE.clear()
        for item in items:
            title_keyword = guess_title_keyword(channel_input, item['title_desc'])
            if not title_keyword:
                print(f"⚠️ کلیدواژه برای '{item['title_desc']}' یافت نشد.")
                continue
            process_item(item, channel_id, title_keyword)

if __name__ == "__main__":
    main()
