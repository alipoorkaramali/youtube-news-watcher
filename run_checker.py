import time
import json
import os
from datetime import datetime, timedelta, timezone
import subprocess

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
MIN_CHECK_INTERVAL = 30
IRAN_OFFSET = timedelta(hours=3, minutes=30)

def iran_now():
    return datetime.now(timezone.utc) + IRAN_OFFSET

def parse_iran_time(time_str):
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
    except:
        return None

def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        print(f"⚠️ فایل {WATCHLIST_FILE} یافت نشد.")
        return []
    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            print("❌ فایل JSON معتبر نیست.")
            return []
    items = []
    for item in data:
        start = item.get('start_time_iran')
        if not start:
            continue
        start_time = parse_iran_time(start)
        if not start_time:
            continue
        items.append({
            'platform': item.get('platform', 'youtube'),
            'channel_id': item.get('channel_id', ''),
            'title_keyword': item.get('title_keyword', ''),
            'start_time_iran': start_time,
            'check_every_minutes': max(item.get('check_every_minutes', 60), MIN_CHECK_INTERVAL),
            'max_attempts': item.get('max_attempts', 5)
        })
    return items

def next_check_time_utc(item, attempt):
    now_utc = datetime.now(timezone.utc)
    now_iran = now_utc + IRAN_OFFSET
    today_iran = now_iran.date()
    start_today_iran = datetime.combine(today_iran, item['start_time_iran'])
    start_today_utc = start_today_iran - IRAN_OFFSET
    # ⭐ دیگر به فردا موکول نمی‌کنیم تا اگر زمان گذشته باشد، بلافاصله اسکن شود
    delay_minutes = item['check_every_minutes'] * attempt
    next_time_utc = start_today_utc + timedelta(minutes=delay_minutes)
    return next_time_utc

def run_scanner():
    now_iran = iran_now()
    print(f"[{now_iran.strftime('%Y-%m-%d %H:%M:%S')} به وقت ایران] 🔄 اجرای چک‌کننده...")
    try:
        result = subprocess.run(
            ["python", "youtube_scanner.py"],
            capture_output=True,
            text=True,
            timeout=600
        )
        print(result.stdout)
        if result.stderr:
            print("⚠️ stderr:", result.stderr)
    except Exception as e:
        print(f"❌ خطا در اجرای اسکنر: {e}")

def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 زمان‌بندی هوشمند بر اساس هر آیتم (خواب مجزا)")
    items = load_watchlist()
    if not items:
        print("⚠️ هیچ آیتم معتبری در watchlist.json یافت نشد. خروج.")
        return
    last_attempts = {idx: 0 for idx in range(len(items))}
    
    while True:
        now_utc = datetime.now(timezone.utc)
        min_sleep = None
        for idx, item in enumerate(items):
            attempt = last_attempts[idx]
            next_time_utc = next_check_time_utc(item, attempt)
            if now_utc >= next_time_utc:
                print(f"⏰ زمان اسکن برای '{item['title_keyword']}' رسیده است.")
                run_scanner()
                last_attempts[idx] += 1
                time.sleep(10)
                break
            else:
                diff = (next_time_utc - now_utc).total_seconds()
                if min_sleep is None or diff < min_sleep:
                    min_sleep = diff
        if min_sleep is not None and min_sleep > 0:
            print(f"💤 در حال استراحت به مدت {int(min_sleep//60)} دقیقه و {int(min_sleep%60)} ثانیه...")
            time.sleep(min_sleep)
        elif min_sleep is None:
            print("⚠️ هیچ آیتمی برای برنامه‌ریزی وجود ندارد. ۵ دقیقه استراحت...")
            time.sleep(300)

if __name__ == "__main__":
    main()