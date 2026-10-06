import os
import json
import re
from datetime import datetime, timedelta, timezone

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

def safe_name(*parts):
    raw = "_".join(parts)
    return re.sub(r'[^\w@.-]', '_', raw)[:60]

def get_state_path(channel_id, keyword, state_dir="cache/states"):
    return os.path.join(state_dir, safe_name(channel_id, keyword) + ".json")

def load_state(channel_id, keyword, state_dir="cache/states"):
    path = get_state_path(channel_id, keyword, state_dir)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"date": "", "found": False, "attempts": 0}

def next_check_utc(iran_start, interval_min, attempt):
    today_iran = iran_now().date()
    start_dt_iran = datetime.combine(today_iran, iran_start)
    utc_offset = iran_offset()
    start_utc = (start_dt_iran - utc_offset).replace(tzinfo=timezone.utc)
    return start_utc + timedelta(minutes=interval_min * attempt)

def should_check(item, state):
    today = iran_now().date()
    if state.get('date') != str(today):
        state = {"date": str(today), "found": False, "attempts": 0}

    if state.get('found'):
        return False

    if state['attempts'] >= item['max_attempts']:
        return False

    start_time = parse_iran_time(item['start_time_iran'])
    if not start_time:
        return False

    interval = item['check_every_minutes']
    next_utc = next_check_utc(start_time, interval, state['attempts'])
    now_utc = datetime.now(timezone.utc)
    return now_utc >= next_utc

def main():
    watchlist_file = "config/watchlist.json"
    if not os.path.exists(watchlist_file):
        print("❌ config/watchlist.json وجود ندارد.")
        exit(1)

    with open(watchlist_file, 'r', encoding='utf-8') as f:
        items = json.load(f)

    need_check = False
    for item in items:
        cid = item.get('channel_id', '').strip()
        kw = item.get('title_keyword', '').strip()
        if not cid or not kw:
            continue

        state = load_state(cid, kw)

        if state.get('found'):
            continue

        if should_check(item, state):
            need_check = True
            break

    if need_check:
        print("✅ حداقل یک آیتم نیاز به چک دارد. ادامه می‌دهیم.")
        exit(0)
    else:
        print("⏳ هیچ آیتمی در این لحظه نیاز به چک ندارد. خروج از اجرا.")
        exit(0)

if __name__ == "__main__":
    main()
