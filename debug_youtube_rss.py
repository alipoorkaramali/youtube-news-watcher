#!/usr/bin/env python3
"""
اسکریپت عیب‌یاب فید RSS یوتیوب
استفاده:
    python debug_youtube_rss.py <channel_id> <keyword> [start_time_iran]

مثال:
    python debug_youtube_rss.py UCat6bC0Wrqq9Bcq7EkH_yQw "اخبار نیمروزی" 15:00
"""

import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

def fetch_rss_feed(channel_id):
    """دریافت و تجزیه فید RSS یوتیوب"""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"📡 دریافت فید از: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; Debugger/1.0)'}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ خطا در دریافت فید: {e}")
        return None

    root = ET.fromstring(resp.content)
    # namespace پیش‌فرض اتم
    ns = {'': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('entry', ns)
    if not entries:
        print("⚠️ هیچ ورودی (entry) در فید پیدا نشد.")
        return []

    videos = []
    for entry in entries:
        title = entry.find('title', ns).text.strip()
        link = entry.find('link', ns).attrib['href']
        pub_str = entry.find('published', ns).text
        # تبدیل به datetime
        pub_date = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
        videos.append({
            'title': title,
            'link': link,
            'published_date': pub_date
        })
    return videos

def iran_offset():
    """محاسبه آفست ایران (تغییر ساعت رسمی)"""
    now = datetime.now()
    if 3 <= now.month <= 9:
        return timedelta(hours=4, minutes=30)
    else:
        return timedelta(hours=3, minutes=30)

def iran_now():
    return datetime.now(timezone.utc) + iran_offset()

def parse_iran_time(time_str):
    """تبدیل زمان HH:MM به شیء time"""
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
    except:
        return None

def main():
    if len(sys.argv) < 3:
        print("استفاده: python debug_youtube_rss.py <channel_id> <keyword> [start_time_iran]")
        sys.exit(1)

    channel_id = sys.argv[1]
    keyword = sys.argv[2]
    start_time_str = sys.argv[3] if len(sys.argv) >= 4 else "00:00"

    # 1. دریافت فید
    videos = fetch_rss_feed(channel_id)
    if videos is None:
        sys.exit(1)

    print(f"\n📊 تعداد کل ویدئوهای فید: {len(videos)}")
    if not videos:
        print("فید خالی است. شاید کانال اشتباه باشد یا یوتیوب مسدود کرده باشد.")
        sys.exit(0)

    # 2. نمایش آخرین ویدئوها (جهت بررسی)
    print("\n🔍 آخرین ویدئوهای موجود در فید:")
    for v in videos[:10]:  # فقط ۱۰ تای اول
        pub_iran = v['published_date'] + iran_offset()
        time_str = pub_iran.strftime("%H:%M")
        print(f"   - [{time_str}] {v['title']}")

    # 3. فیلتر بر اساس زمان شروع
    start_time = parse_iran_time(start_time_str)
    if start_time is None:
        print("⚠️ فرمت start_time_iran نامعتبر است. همه ویدئوها را بررسی می‌کنیم.")
        recent = videos
    else:
        # ویدئوهایی که بعد از start_time امروز (به وقت ایران) منتشر شده‌اند
        today_iran = iran_now().date()
        start_dt_iran = datetime.combine(today_iran, start_time)
        start_utc = (start_dt_iran - iran_offset()).replace(tzinfo=timezone.utc)
        recent = [v for v in videos if v['published_date'] >= start_utc]
        print(f"\n⏰ زمان شروع جستجو (به وقت ایران): {start_time_str}")
        print(f"   ویدئوهای منتشرشده بعد از این ساعت: {len(recent)}")

    if not recent:
        print("❌ هیچ ویدئویی بعد از زمان شروع در فید نیست. احتمالاً ویدئوی امروز هنوز در فید منتشر نشده است.")
        sys.exit(0)

    # 4. جستجوی کلیدواژه
    matched = []
    for v in recent:
        if keyword.lower() in v['title'].lower():
            matched.append(v)

    if matched:
        print(f"\n✅ {len(matched)} ویدئو با کلیدواژه «{keyword}» پیدا شد:")
        for v in matched:
            pub_iran = v['published_date'] + iran_offset()
            print(f"   - {v['title']}")
            print(f"     لینک: {v['link']}")
            print(f"     انتشار: {pub_iran.strftime('%Y-%m-%d %H:%M')}")
    else:
        print(f"\n❌ هیچ ویدئویی با کلیدواژه «{keyword}» در فید یافت نشد.")
        print("🔎 دلایل احتمالی:")
        print("   1. ویدئو هنوز در فید RSS منتشر نشده است (تأخیر یوتیوب).")
        print("   2. عنوان ویدئو دقیقاً حاوی عبارت جستجو نیست. (بررسی کنید)")
        print("   3. ویدئو جزو ۱۵ ویدئوی آخر کانال نیست (فید RSS فقط ۱۵ آیتم آخر را نشان می‌دهد).")
        print("   4. کانال، انتشار ویدئو را خصوصی یا غیرفهرست‌شده انجام داده است که در فید RSS نمی‌آید.")

if __name__ == "__main__":
    main()
