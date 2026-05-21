import requests
import xml.etree.ElementTree as ET
import os, json, sys, traceback, re
from datetime import datetime, timedelta, timezone
from sclib import SoundcloudAPI, Playlist, Track

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
MAX_ITEMS = 10
OUTPUT_FILE = "diagnostic_results.txt"   # فایل خروجی

def write_output(text):
    """نوشتن هم در کنسول و هم در فایل"""
    print(text)
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(text + '\n')

def fetch_rss_youtube(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    write_output(f"📡 دریافت فید یوتیوب: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {'': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('entry', ns)
        write_output(f"✅ {len(entries)} ویدیو در فید پیدا شد.")
        titles = []
        for idx, entry in enumerate(entries[:15]):  # حداکثر ۱۵ تا
            title = entry.find('title', ns).text.strip()
            link = entry.find('link', ns).attrib['href']
            published = entry.find('published', ns)
            pub_str = published.text if published is not None else 'Unknown'
            titles.append(title)
            write_output(f"{idx+1}. {title}")
            write_output(f"   Link: {link}")
            write_output(f"   Published: {pub_str}")
        if len(entries) > 15:
            write_output(f"... و {len(entries)-15} ویدیوی دیگر (محدودیت ۱۵)")
        return titles
    except Exception as e:
        write_output(f"❌ خطا: {e}")
        return []

def fetch_soundcloud_playlist(playlist_url):
    write_output(f"📡 دریافت پلی‌لیست ساندکلاد: {playlist_url}")
    try:
        api = SoundcloudAPI()
        playlist = api.resolve(playlist_url)
        if not isinstance(playlist, Playlist):
            write_output("❌ این یک Playlist نیست.")
            return []
        titles = []
        for idx, track in enumerate(playlist.tracks[:15]):
            titles.append(track.title)
            write_output(f"{idx+1}. {track.title}")
            write_output(f"   Link: {track.permalink_url}")
        if len(playlist.tracks) > 15:
            write_output(f"... و {len(playlist.tracks)-15} آهنگ دیگر")
        write_output(f"✅ {len(titles)} آهنگ پیدا شد.")
        return titles
    except Exception as e:
        write_output(f"❌ خطا: {e}")
        return []

def fetch_soundcloud_user(user_url):
    write_output(f"📡 دریافت آهنگ‌های کاربر ساندکلاد: {user_url}")
    try:
        api = SoundcloudAPI()
        user = api.resolve(user_url)
        if not user:
            write_output("❌ کاربر پیدا نشد.")
            return []
        titles = []
        for idx, track in enumerate(user.tracks[:15]):
            titles.append(track.title)
            write_output(f"{idx+1}. {track.title}")
            write_output(f"   Link: {track.permalink_url}")
        if len(user.tracks) > 15:
            write_output(f"... و {len(user.tracks)-15} آهنگ دیگر")
        write_output(f"✅ {len(titles)} آهنگ پیدا شد.")
        return titles
    except Exception as e:
        write_output(f"❌ خطا: {e}")
        return []

def main():
    # پاک کردن فایل خروجی قبلی
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    write_output("=== Diagnostic Results ===")
    
    if not os.path.exists(WATCHLIST_FILE):
        write_output("❌ فایل watchlist.json وجود ندارد.")
        return

    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        items = json.load(f)

    for item in items:
        platform = item.get('platform', 'youtube')
        channel_id = item.get('channel_id', '')
        keywords = item.get('title_keyword', '')
        if isinstance(keywords, str):
            keywords = [keywords.strip()]
        elif isinstance(keywords, list):
            keywords = [k.strip() for k in keywords if k.strip()]
        else:
            keywords = []

        write_output(f"\n🔍 بررسی آیتم: پلتفرم={platform}, شناسه={channel_id}, کلیدواژه‌ها={keywords}")

        if platform == 'youtube':
            titles = fetch_rss_youtube(channel_id)
        elif platform == 'soundcloud_playlist':
            titles = fetch_soundcloud_playlist(channel_id)
        elif platform == 'soundcloud_user':
            titles = fetch_soundcloud_user(channel_id)
        else:
            write_output("❌ پلتفرم نامعتبر.")
            continue

        if titles:
            write_output("📋 عناوین همسان‌سازی شده با کلیدواژه:")
            for t in titles:
                match = any(kw.lower() in t.lower() for kw in keywords)
                write_output(f"   {'[✅ همسان]' if match else '[  ]'} {t}")
        else:
            write_output("⚠️ هیچ عنوانی دریافت نشد.")

if __name__ == "__main__":
    main()