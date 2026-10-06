import os
import json
import sys
import traceback
import re
import subprocess
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import time

# ================== تنظیمات ==================
WATCHLIST_FILE = "config/watchlist.json"
OUTPUT_FILE = "logs/new_videos.txt"
STATE_DIR = "cache/states"
SEEN_TITLES_FILE = "cache/seen_titles.json"
MAX_ITEMS = 10
MAX_UNIQUE_CHANNELS = 5
MIN_CHECK_INTERVAL = 30
MAX_ATTEMPTS_LIMIT = 10
SOUNDCLOUD_MAX_AGE_HOURS = 48
SOUNDCLOUD_PLAYLIST_END = 80
SOUNDCLOUD_TOP_UNKNOWN_SAFE = 80

PERSIAN_WEEKDAYS = {
    'شنبه': 5,
    'یکشنبه': 6,
    'دوشنبه': 0,
    'سه‌شنبه': 1,
    'سه شنبه': 1,
    'چهارشنبه': 2,
    'پنج‌شنبه': 3,
    'پنجشنبه': 3,
    'جمعه': 4,
}

def iran_offset():
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
    utc_offset = iran_offset()
    start_utc = (start_dt_iran - utc_offset).replace(tzinfo=timezone.utc)
    return start_utc + timedelta(minutes=interval_min * attempt)

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

def normalize_title_for_dedup(title: str) -> str:
    if not title:
        return ""
    t = title.strip()
    t = re.sub(r'\s*\|\s*\d+\s*(hours?|minutes?|ago).*$', '', t, flags=re.I)
    t = re.sub(r'\s*[\(\[].*?[\)\]]\s*', ' ', t)
    t = re.sub(r'(?i)\b(audio|official|video|music|clip|lyrics|hd|4k|mp3|download)\b', '', t)
    t = re.sub(r'[\|–—\-/]+', ' ', t)
    trans = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    t = t.translate(trans)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t

def load_seen_titles():
    if not os.path.exists(SEEN_TITLES_FILE):
        return {}
    try:
        with open(SEEN_TITLES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        today = str(iran_now().date())
        if today not in data:
            return {}
        return {today: data[today]}
    except Exception:
        return {}

def save_seen_titles(data: dict):
    today = str(iran_now().date())
    data = {today: data.get(today) or {}}
    os.makedirs(os.path.dirname(SEEN_TITLES_FILE), exist_ok=True)
    with open(SEEN_TITLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_title_already_downloaded(title: str):
    key = normalize_title_for_dedup(title)
    if not key:
        return False, key, None
    data = load_seen_titles()
    today = str(iran_now().date())
    entry = (data.get(today) or {}).get(key)
    if entry:
        return True, key, entry
    return False, key, None

def mark_title_downloaded(title: str, platform: str, url: str):
    key = normalize_title_for_dedup(title)
    if not key:
        return
    data = load_seen_titles()
    today = str(iran_now().date())
    if today not in data:
        data[today] = {}
    data[today][key] = {"platform": platform, "url": url, "at": datetime.now(timezone.utc).isoformat()}
    save_seen_titles(data)

def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        os.makedirs(os.path.dirname(WATCHLIST_FILE) or '.', exist_ok=True)
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            f.write("[]")
        return []
    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        raw = f.read().strip()
    if not raw:
        print("📭 watchlist خالی است.")
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ فایل JSON معتبر نیست: {e}")
        sys.exit(1)
    valid_items = []
    for item in items:
        plat = item.get('platform', 'youtube')
        cid = item.get('channel_id', '')
        keyword = item.get('title_keyword', '')
        start = item.get('start_time_iran', '')
        if not cid.strip() or not keyword.strip() or not parse_iran_time(start):
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
        valid_items = valid_items[:MAX_ITEMS]
    unique_channels = set(it['channel_id'] for it in valid_items)
    if len(unique_channels) > MAX_UNIQUE_CHANNELS:
        print(f"⚠️ تعداد کانال‌ها بیش از {MAX_UNIQUE_CHANNELS} است. اجرا متوقف شد.")
        sys.exit(1)
    return valid_items

def main():
    print("youtube_scanner starting...")
    items = load_watchlist()
    print(f"loaded {len(items)} watch items from {WATCHLIST_FILE}")
    for it in items:
        print(f"  - {it['platform']} {it['title_keyword']}")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
