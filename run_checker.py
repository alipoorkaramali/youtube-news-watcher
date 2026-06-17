import time
import json
import os
from datetime import datetime, timedelta, timezone
import subprocess

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
MIN_CHECK_INTERVAL = 30  # حداقل فاصله زمانی بین اسکن‌ها (دقیقه)

# ================== ابزارهای زمان ==================
def iran_offset():
    return timedelta(hours=3, minutes=30)

def iran_now():
    # زمان فعلی با منطقه زمانی ایران (aware)
    return datetime.now(timezone.utc).astimezone(timezone(iran_offset()))

def parse_iran_time(time_str):
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
    except:
        return None

# ================== خواندن watchlist ==================
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

# ================== محاسبه زمان بعدی برای یک آیتم (اصلاح‌شده) ==================
def next_check_time(item, attempt):
    """محاسبه زمان UTC برای تلاش بعدی یک آیتم"""
    now_iran = iran_now()
    today = now_iran.date()
    
    # زمان شروع امروز با منطقه زمانی ایران
    start_today = datetime.combine(today, item['start_time_iran'])
    # افزودن منطقه زمانی ایران به start_today تا aware شود
    start_today = start_today.replace(tzinfo=timezone(iran_offset()))
    
    # اگر زمان شروع امروز گذشته باشد، به فردا موکول می‌شود
    if start_today <= now_iran:
        start_today = start_today + timedelta(days=1)
    
    # اضافه کردن فاصله زمانی بر اساس تعداد تلاش‌ها
    delay_minutes = item['check_every_minutes'] * attempt
    next_time = start_today + timedelta(minutes=delay_minutes)
    
    # تبدیل به UTC (برای ذخیره و مقایسه با زمان فعلی سرور)
    utc_offset = iran_offset()
    next_time_utc = (next_time - utc_offset).replace(tzinfo=timezone.utc)
    
    return next_time_utc

# ================== تابع اصلی اجرا ==================
def run_scanner():
    print(f"[{iran_now().strftime('%Y-%m-%d %H:%M:%S')} به وقت ایران] 🔄 اجرای چک‌کننده...")
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

# ================== تابع اصلی ==================
def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 زمان‌بندی هوشمند بر اساس هر آیتم (خواب مجزا)")
    
    # بارگذاری لیست آیتم‌ها
    items = load_watchlist()
    if not items:
        print("⚠️ هیچ آیتم معتبری در watchlist.json یافت نشد. خروج.")
        return
    
    # دیکشنری برای ذخیره آخرین وضعیت هر آیتم
    last_attempts = {idx: 0 for idx in range(len(items))}
    
    while True:
        now_utc = datetime.now(timezone.utc)
        
        # پیدا کردن آیتم‌هایی که زمانشان رسیده
        min_sleep = None
        for idx, item in enumerate(items):
            attempt = last_attempts[idx]
            next_time = next_check_time(item, attempt)
            
            # اگر زمان رسیده باشد، اجرا کن
            if now_utc >= next_time:
                print(f"⏰ زمان اسکن برای '{item['title_keyword']}' رسیده است.")
                run_scanner()  # یک بار اسکن کامل اجرا می‌شود
                
                # افزایش تعداد تلاش‌ها برای این آیتم
                last_attempts[idx] += 1
                
                # بعد از اسکن، یک بار دیگر حلقه را بررسی می‌کنیم
                # اما برای جلوگیری از اسکن مجدد در همان لحظه، یک وقفه کوتاه می‌گذاریم
                time.sleep(10)
                break  # بعد از اجرا، دوباره از اول حلقه می‌رویم
            else:
                # محاسبه زمان باقی‌مانده تا این آیتم
                diff = (next_time - now_utc).total_seconds()
                if min_sleep is None or diff < min_sleep:
                    min_sleep = diff
        
        # اگر هیچ آیتمی زمانش نرسیده بود، تا نزدیک‌ترین زمان بخواب
        if min_sleep is not None and min_sleep > 0:
            print(f"💤 در حال استراحت به مدت {int(min_sleep//60)} دقیقه و {int(min_sleep%60)} ثانیه...")
            time.sleep(min_sleep)
        elif min_sleep is None:
            # اگر هیچ آیتمی وجود نداشته باشد (نباید اتفاق بیفتد)
            print("⚠️ هیچ آیتمی برای برنامه‌ریزی وجود ندارد. ۵ دقیقه استراحت...")
            time.sleep(300)

if __name__ == "__main__":
    main()