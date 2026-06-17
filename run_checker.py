import time
import json
import os
from datetime import datetime, timedelta
import subprocess

# ======================================================
#  تنظیمات اولیه
# ======================================================
WATCHLIST_FILE = "watchlist.json"        # نام فایل لیست کانال‌ها

# ======================================================
#  توابع کمکی زمان
# ======================================================
def iran_offset():
    """برگرداندن اختلاف ساعت ایران با UTC (۳:۳۰+)"""
    return timedelta(hours=3, minutes=30)

def iran_now():
    """برگرداندن زمان فعلی به‌وقت ایران (بدون منطقه‌ی زمانی)"""
    return datetime.now() + iran_offset()

def parse_iran_time(time_str):
    """تبدیل رشته‌ی زمان (مثلاً '18:45') به شیء time"""
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
    except:
        return None

# ======================================================
#  خواندن فایل watchlist.json
# ======================================================
def load_watchlist():
    """بارگذاری و اعتبارسنجی آیتم‌های موجود در watchlist.json"""
    if not os.path.exists(WATCHLIST_FILE):
        print(f"⚠️ فایل {WATCHLIST_FILE} یافت نشد.")
        return []

    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
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
#  اجرای اسکنر اصلی (youtube_scanner.py)
# ======================================================
def run_scanner():
    """اجرای اسکریپت youtube_scanner.py و چاپ خروجی آن"""
    print(f"[{iran_now().strftime('%Y-%m-%d %H:%M:%S')} به وقت ایران] 🔄 اجرای چک‌کننده...")
    try:
        result = subprocess.run(
            ["python", "youtube_scanner.py"],
            capture_output=True,
            text=True,
            timeout=600          # حداکثر ۱۰ دقیقه زمان برای اجرا
        )
        print(result.stdout)
        if result.stderr:
            print("⚠️ stderr:", result.stderr)
    except subprocess.TimeoutExpired:
        print("❌ زمان اجرای اسکنر به پایان رسید (timeout).")
    except Exception as e:
        print(f"❌ خطا در اجرای اسکنر: {e}")

# ======================================================
#  تابع اصلی (حلقه‌ی بی‌نهایت با خواب ۵ دقیقه‌ای)
# ======================================================
def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 بر اساس زمان‌بندی watchlist.json کار می‌کند")

    # یک بار لیست آیتم‌ها را بارگذاری می‌کنیم (در صورت نیاز)
    items = load_watchlist()
    if not items:
        print("⚠️ هیچ آیتم معتبری در watchlist.json یافت نشد. اما سرویس همچنان اجرا می‌شود.")

    while True:
        # اجرای اسکنر
        run_scanner()
        # ۵ دقیقه صبر کن (۳۰۰ ثانیه)
        time.sleep(300)

# ======================================================
#  نقطه‌ی ورود
# ======================================================
if __name__ == "__main__":
    main()