import json
import os
from datetime import datetime, timedelta
import pytz

def safe_name(channel_id, keyword):
    return f"{channel_id}_{keyword}".replace(" ", "_").replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")

def get_state_path(channel_id, keyword, state_dir="cache/states"):
    return os.path.join(state_dir, safe_name(channel_id, keyword) + ".json")

def load_state(channel_id, keyword, state_dir="cache/states"):
    path = get_state_path(channel_id, keyword, state_dir)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"last_success_date": None, "attempts_today": 0, "last_attempt_time": None}

def should_check(item):
    iran_tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(iran_tz)
    today = now.strftime("%Y-%m-%d")

    start_time_str = item.get("start_time_iran", "00:00")
    try:
        h, m = map(int, start_time_str.split(":"))
        start_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    except Exception:
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if now < start_time:
        return False

    state = load_state(item["channel_id"], item["title_keyword"])

    if state.get("last_success_date") == today:
        return False

    max_attempts = item.get("max_attempts", 5)
    if state.get("attempts_today", 0) >= max_attempts:
        return False

    interval = item.get("check_every_minutes", 60)
    last_attempt = state.get("last_attempt_time")
    if last_attempt:
        try:
            last_dt = datetime.fromisoformat(last_attempt)
            if last_dt.tzinfo is None:
                last_dt = iran_tz.localize(last_dt)
            if now < last_dt + timedelta(minutes=interval):
                return False
        except Exception:
            pass

    return True

def main():
    watchlist_file = "config/watchlist.json"
    if not os.path.exists(watchlist_file):
        print("❌ config/watchlist.json وجود ندارد.")
        return

    with open(watchlist_file, 'r', encoding='utf-8') as f:
        items = json.load(f)

    if not items:
        print("📭 watchlist خالی است.")
        return

    need_scan = False
    for item in items:
        if should_check(item):
            print(f"✅ نیاز به اسکن: {item.get('title_keyword')} ({item.get('platform')})")
            need_scan = True
        else:
            print(f"⏭️ رد شد: {item.get('title_keyword')}")

    if need_scan:
        print("✅")
    else:
        print("⏭️ هیچ آیتمی برای اسکن نیاز نیست.")

if __name__ == "__main__":
    main()
