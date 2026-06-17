import time
import json
import os
import subprocess
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# ======================================================
#  تنظیمات
# ======================================================
WATCHLIST_FILE = "watchlist.json"
IRAN_OFFSET = timedelta(hours=3, minutes=30)

# ======================================================
#  توابع زمان (همه naive هستند)
# ======================================================
def iran_now():
    return datetime.now() + IRAN_OFFSET

def parse_iran_time(time_str):
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
    now_iran = iran_now()
    now_time = now_iran.time()
    if not (9 <= now_time.hour < 23):
        next_9am = datetime.combine(now_iran.date() + timedelta(days=1), datetime.strptime("09:00", "%H:%M").time())
        diff = (next_9am - now_iran).total_seconds()
        print(f"💤 خارج از بازه‌ی کاری (۹ صبح تا ۱۲ شب). تا ۹ صبح فردا استراحت...")
        return diff
    min_diff = None
    for item in items:
        start_time = item['start_time_iran']
        start_today = datetime.combine(now_iran.date(), start_time)
        if start_today < now_iran:
            start_today += timedelta(days=1)
        diff = (start_today - now_iran).total_seconds()
        if min_diff is None or diff < min_diff:
            min_diff = diff
    if min_diff is None:
        return 300
    if min_diff < 0:
        min_diff = 0
    return min_diff

# ======================================================
#  وب سرور ساده با http.server (بدون نیاز به Flask)
# ======================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        # استفاده از encode برای کاراکترهای غیر-ASCII
        self.wfile.write("✅ Service is running".encode('utf-8'))

def run_http_server():
    server = HTTPServer(('0.0.0.0', 5000), HealthHandler)
    server.serve_forever()

# ======================================================
#  تابع اصلی (اجرای همزمان وب سرور و اسکریپت)
# ======================================================
def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 زمان‌بندی هوشمند بر اساس watchlist.json")
    
    items = load_watchlist()
    if not items:
        print("⚠️ هیچ آیتم معتبری در watchlist.json یافت نشد. خروج.")
        return
    
    # راه‌اندازی وب سرور در یک ترد جداگانه
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    print("🌐 وب سرور ساده برای سلامت سرویس در پورت ۵۰۰۰ راه‌اندازی شد.")
    
    while True:
        sleep_seconds = calculate_sleep_time(items)
        if sleep_seconds > 0:
            print(f"💤 در حال استراحت به مدت {int(sleep_seconds//60)} دقیقه و {int(sleep_seconds%60)} ثانیه...")
            time.sleep(sleep_seconds)
        run_scanner()

# ======================================================
#  نقطه‌ی ورود
# ======================================================
if __name__ == "__main__":
    main()