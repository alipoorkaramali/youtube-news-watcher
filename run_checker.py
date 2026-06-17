import time
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

# ======================================================
#  تنظیمات
# ======================================================
WATCHLIST_FILE = "watchlist.json"
IRAN_OFFSET = timedelta(hours=3, minutes=30)

# ======================================================
#  توابع زمان
# ======================================================
def iran_now():
    """زمان فعلی به‌وقت ایران (با منطقه‌ی زمانی)"""
    return datetime.now(timezone.utc) + IRAN_OFFSET

def parse_iran_time(time_str):
    """تبدیل رشته‌ی زمان (مثلاً '18:45') به شیء time"""
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
    except:
        return None

# ======================================================
#  خواندن watchlist.json
# ======================================================
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
            'check_every_minutes': item.get('check_every_minutes', 60),
            'max_attempts': item.get('max_attempts', 5)
        })
    
    return items

# ======================================================
#  اجرای اسکنر اصلی
# ======================================================
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

# ======================================================
#  محاسبه‌ی زمان خواب هوشمند
# ======================================================
def calculate_sleep_time(items):
    """
    نزدیک‌ترین زمان شروع (از بین تمام آیتم‌ها) را پیدا می‌کند
    و زمان خواب را بر اساس آن محاسبه می‌کند.
    اگر خارج از بازه‌ی ۹ صبح تا ۱۲ شب باشد، تا ۹ صبح فردا می‌خوابد.
    """
    now_iran = iran_now()
    now_time = now_iran.time()
    
    # بازه‌ی کاری: ۹ صبح تا ۱۲ شب
    if not (9 <= now_time.hour < 23):
        # اگر خارج از بازه است، تا ۹ صبح فردا بخواب
        next_9am = datetime.combine(now_iran.date() + timedelta(days=1), datetime.strptime("09:00", "%H:%M").time())
        diff = (next_9am - now_iran).total_seconds()
        print(f"💤 خارج از بازه‌ی کاری (۹ صبح تا ۱۲ شب). تا ۹ صبح فردا استراحت...")
        return diff
    
    # پیدا کردن نزدیک‌ترین زمان شروع
    min_diff = None
    for item in items:
        start_time = item['start_time_iran']
        # زمان شروع امروز
        start_today = datetime.combine(now_iran.date(), start_time)
        if start_today < now_iran:
            # اگر گذشته، به فردا موکول کن
            start_today += timedelta(days=1)
        diff = (start_today - now_iran).total_seconds()
        if min_diff is None or diff < min_diff:
            min_diff = diff
    
    if min_diff is None:
        return 300  # ۵ دقیقه پیش‌فرض
    
    if min_diff < 0:
        min_diff = 0
    
    return min_diff

# ======================================================
#  تابع اصلی (حلقه‌ی هوشمند)
# ======================================================
def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 زمان‌بندی هوشمند بر اساس watchlist.json")
    
    items = load_watchlist()
    if not items:
        print("⚠️ هیچ آیتم معتبری در watchlist.json یافت نشد. خروج.")
        return
    
    while True:
        # محاسبه‌ی زمان خواب تا نزدیک‌ترین زمان شروع
        sleep_seconds = calculate_sleep_time(items)
        
        if sleep_seconds > 0:
            print(f"💤 در حال استراحت به مدت {int(sleep_seconds//60)} دقیقه و {int(sleep_seconds%60)} ثانیه...")
            time.sleep(sleep_seconds)
        
        # اجرای اسکنر
        run_scanner()

# ======================================================
#  نقطه‌ی ورود
# ======================================================
if __name__ == "__main__":
    main()