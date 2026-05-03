import requests
import xml.etree.ElementTree as ET
import os, json, sys, traceback
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

# ... (بقیهٔ توابع مانند قبل، اما در ادامه تنها بخش main تغییر کرده است)

def main():
    try:
        # بارگذاری watchlist
        if not os.path.exists(WATCHLIST_FILE):
            print(f"📭 فایل {WATCHLIST_FILE} وجود ندارد. یک فایل خالی می‌سازیم.")
            with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
                f.write("[]")
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            raw = f.read().strip()
        if not raw:
            print("📭 watchlist.json خالی است. آیتمی برای بررسی وجود ندارد.")
            return
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"❌ فایل watchlist.json معتبر نیست: {e}")
            sys.exit(1)

        # اعتبارسنجی محدودیت‌ها
        if len(items) > MAX_ITEMS:
            print(f"⚠️ تعداد آیتم‌ها بیش از {MAX_ITEMS} است. فقط {MAX_ITEMS} مورد اول بررسی می‌شود.")
            items = items[:MAX_ITEMS]
        unique_channels = set(item.get('channel', '') for item in items)
        if len(unique_channels) > MAX_UNIQUE_CHANNELS:
            print(f"⚠️ تعداد کانال‌ها بیش از {MAX_UNIQUE_CHANNELS} است. اجرا متوقف شد.")
            sys.exit(1)

        # گروه‌بندی بر اساس کانال
        channel_map = {}
        for item in items:
            channel_map.setdefault(item.get('channel', ''), []).append(item)

        for channel_input, its in channel_map.items():
            channel_id = resolve_channel_id(channel_input)
            if not channel_id:
                print(f"❌ شناسه کانال برای '{channel_input}' پیدا نشد.")
                continue
            RSS_CACHE.clear()
            for item in its:
                title_keyword = guess_title_keyword(channel_input, item.get('title_desc', ''))
                if not title_keyword:
                    print(f"⚠️ کلیدواژه برای '{item.get('title_desc', '')}' یافت نشد.")
                    continue
                process_item(item, channel_id, title_keyword)

    except Exception as e:
        print("💥 خطای پیش‌بینی نشده:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # ... توابع دیگر باید در اینجا کامل باشند، اما برای کوتاهی، فرض می‌کنم شما کل کد قبلی را همراه با این main جایگزین می‌کنید.
