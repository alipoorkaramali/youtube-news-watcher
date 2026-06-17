import time
import json
import os
from datetime import datetime, timedelta
import subprocess

# تابع برای خواندن فایل watchlist.json و استخراج همه زمان‌های شروع
def get_start_times():
    try:
        with open('watchlist.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        times = []
        for item in data:
            start_str = item.get('start_time_iran')
            if start_str:
                # تبدیل به datetime.time برای سهولت مقایسه
                try:
                    # فرمت "HH:MM" مثل "18:45"
                    hour, minute = map(int, start_str.split(':'))
                    times.append((hour, minute))
                except:
                    pass
        # حذف موارد تکراری (اختیاری)
        times = list(set(times))
        return times
    except Exception as e:
        print(f"⚠️ خطا در خواندن watchlist.json: {e}")
        return []

# تابع محاسبه فاصله تا نزدیک‌ترین زمان آینده
def seconds_until_next_start(times):
    now = datetime.now()
    current_time = now.time()
    
    # اگر لیست زمان‌ها خالی بود، ۵ دقیقه پیش‌فرض
    if not times:
        return 300

    # تبدیل زمان‌ها به object برای مقایسه
    start_times = [datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time() for h, m in times]
    
    # پیدا کردن نزدیک‌ترین زمان آینده (امروز یا فردا)
    next_start = None
    min_diff = None
    
    for t in start_times:
        # زمان امروز
        candidate_today = datetime.combine(now.date(), t)
        if candidate_today > now:
            diff = (candidate_today - now).total_seconds()
        else:
            # زمان فردا
            candidate_tomorrow = datetime.combine(now.date() + timedelta(days=1), t)
            diff = (candidate_tomorrow - now).total_seconds()
        
        if min_diff is None or diff < min_diff:
            min_diff = diff
            next_start = candidate_today if candidate_today > now else candidate_tomorrow
    
    # اگر به هر دلیلی محاسبه نشد، پیش‌فرض ۵ دقیقه
    if min_diff is None:
        return 300
    
    # اطمینان از اینکه منفی نباشه (فقط برای ایمنی)
    if min_diff < 0:
        min_diff = 0
    
    print(f"⏳ تا زمان بعدی ({next_start.strftime('%H:%M')}) {int(min_diff//60)} دقیقه و {int(min_diff%60)} ثانیه باقی مانده.")
    return min_diff

def run_scanner():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔄 اجرای چک‌کننده...")
    try:
        result = subprocess.run(["python", "youtube_scanner.py"], 
                              capture_output=True, text=True, timeout=600)
        print(result.stdout)
        if result.stderr:
            print("⚠️ stderr:", result.stderr)
    except Exception as e:
        print(f"❌ خطا در اجرای اسکنر: {e}")

def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 زمان‌بندی هوشمند بر اساس watchlist.json")
    
    # خواندن زمان‌ها از فایل JSON
    start_times = get_start_times()
    if not start_times:
        print("⚠️ هیچ زمان شروع معتبری در watchlist.json یافت نشد. از حالت پیش‌فرض ۵ دقیقه‌ای استفاده می‌شود.")
    
    while True:
        # محاسبه زمان خواب تا نزدیک‌ترین زمان شروع
        if start_times:
            sleep_seconds = seconds_until_next_start(start_times)
        else:
            sleep_seconds = 300  # پیش‌فرض ۵ دقیقه
        
        # اگر زمان تا شروع بیشتر از ۰ بود، بخواب
        if sleep_seconds > 0:
            print(f"💤 در حال استراحت به مدت {int(sleep_seconds//60)} دقیقه و {int(sleep_seconds%60)} ثانیه...")
            time.sleep(sleep_seconds)
        
        # اجرای اسکنر در زمان مقرر
        run_scanner()
        
        # بعد از اجرا، ممکن است لازم باشد برای آیتم‌هایی که check_every_minutes دارند
        # دوباره برنامه‌ریزی کنیم، اما فعلاً ساده گرفته شده.

if __name__ == "__main__":
    main()
