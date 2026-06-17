import time
import json
import os
from datetime import datetime, timedelta
import subprocess
from zoneinfo import ZoneInfo  # اضافه کردن کتابخانه منطقه زمانی

# تابع برای خواندن فایل watchlist.json و استخراج همه زمان‌های شروع
def get_start_times():
    try:
        with open('watchlist.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        times = []
        for item in data:
            start_str = item.get('start_time_iran')
            if start_str:
                try:
                    hour, minute = map(int, start_str.split(':'))
                    times.append((hour, minute))
                except:
                    pass
        times = list(set(times))
        return times
    except Exception as e:
        print(f"⚠️ خطا در خواندن watchlist.json: {e}")
        return []

# تابع محاسبه فاصله تا نزدیک‌ترین زمان آینده (بر اساس ساعت ایران)
def seconds_until_next_start(times):
    # ⭐ دریافت زمان فعلی بر اساس منطقه زمانی ایران
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    current_time = now.time()
    
    if not times:
        return 300

    start_times = [datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time() for h, m in times]
    
    next_start = None
    min_diff = None
    
    for t in start_times:
        candidate_today = datetime.combine(now.date(), t).replace(tzinfo=ZoneInfo("Asia/Tehran"))
        if candidate_today > now:
            diff = (candidate_today - now).total_seconds()
        else:
            candidate_tomorrow = datetime.combine(now.date() + timedelta(days=1), t).replace(tzinfo=ZoneInfo("Asia/Tehran"))
            diff = (candidate_tomorrow - now).total_seconds()
        
        if min_diff is None or diff < min_diff:
            min_diff = diff
            next_start = candidate_today if candidate_today > now else candidate_tomorrow
    
    if min_diff is None:
        return 300
    if min_diff < 0:
        min_diff = 0
    
    # چاپ زمان باقی‌مانده بر اساس ساعت ایران
    print(f"⏳ تا زمان بعدی ({next_start.strftime('%H:%M')} به وقت ایران) {int(min_diff//60)} دقیقه و {int(min_diff%60)} ثانیه باقی مانده.")
    return min_diff

def run_scanner():
    # ⭐ ثبت زمان اجرا بر اساس ساعت ایران
    now_iran = datetime.now(ZoneInfo("Asia/Tehran"))
    print(f"[{now_iran.strftime('%Y-%m-%d %H:%M:%S')} به وقت ایران] 🔄 اجرای چک‌کننده...")
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
    print("📋 زمان‌بندی هوشمند بر اساس ساعت ایران (Asia/Tehran)")
    
    start_times = get_start_times()
    if not start_times:
        print("⚠️ هیچ زمان شروع معتبری در watchlist.json یافت نشد. از حالت پیش‌فرض ۵ دقیقه‌ای استفاده می‌شود.")
    
    while True:
        if start_times:
            sleep_seconds = seconds_until_next_start(start_times)
        else:
            sleep_seconds = 300
        
        if sleep_seconds > 0:
            print(f"💤 در حال استراحت به مدت {int(sleep_seconds//60)} دقیقه و {int(sleep_seconds%60)} ثانیه...")
            time.sleep(sleep_seconds)
        
        run_scanner()

if __name__ == "__main__":
    main()