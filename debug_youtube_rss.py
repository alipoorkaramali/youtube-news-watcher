import requests
import xml.etree.ElementTree as ET
import os, json, sys, traceback, re
from datetime import datetime, timedelta, timezone
from sclib import SoundcloudAPI, Playlist, Track

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
MAX_ITEMS = 10

def fetch_rss_youtube(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    print(f"📡 دریافت فید یوتیوب: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {'': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('entry', ns)
        print(f"✅ {len(entries)} ویدیو در فید پیدا شد.")
        return [entry.find('title', ns).text.strip() for entry in entries]
    except Exception as e:
        print(f"❌ خطا: {e}")
        return []

def fetch_soundcloud_playlist(playlist_url):
    print(f"📡 دریافت پلی‌لیست ساندکلاد: {playlist_url}")
    try:
        api = SoundcloudAPI()
        playlist = api.resolve(playlist_url)
        if not isinstance(playlist, Playlist):
            print("❌ این یک Playlist نیست.")
            return []
        titles = [track.title for track in playlist.tracks]
        print(f"✅ {len(titles)} آهنگ پیدا شد.")
        return titles
    except Exception as e:
        print(f"❌ خطا: {e}")
        return []

def fetch_soundcloud_user(user_url):
    print(f"📡 دریافت آهنگ‌های کاربر ساندکلاد: {user_url}")
    try:
        api = SoundcloudAPI()
        user = api.resolve(user_url)
        if not user:
            print("❌ کاربر پیدا نشد.")
            return []
        titles = [track.title for track in user.tracks]
        print(f"✅ {len(titles)} آهنگ پیدا شد.")
        return titles
    except Exception as e:
        print(f"❌ خطا: {e}")
        return []

def main():
    if not os.path.exists(WATCHLIST_FILE):
        print("❌ فایل watchlist.json وجود ندارد.")
        return

    with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
        items = json.load(f)

    for item in items:
        platform = item.get('platform', 'youtube')
        channel_id = item.get('channel_id', '')
        keywords = item.get('title_keyword', '')
        # تبدیل به لیست
        if isinstance(keywords, str):
            keywords = [keywords.strip()]
        elif isinstance(keywords, list):
            keywords = [k.strip() for k in keywords if k.strip()]
        else:
            keywords = []

        print(f"\n🔍 بررسی آیتم: پلتفرم={platform}, کانال={channel_id}, کلیدواژه‌ها={keywords}")

        if platform == 'youtube':
            titles = fetch_rss_youtube(channel_id)
        elif platform == 'soundcloud_playlist':
            titles = fetch_soundcloud_playlist(channel_id)
        elif platform == 'soundcloud_user':
            titles = fetch_soundcloud_user(channel_id)
        else:
            print("❌ پلتفرم نامعتبر.")
            continue

        if titles:
            print("📋 عناوین پیدا شده:")
            for t in titles[:15]:  # فقط ۱۵ تای اول
                match = any(kw.lower() in t.lower() for kw in keywords)
                print(f"   {'[✅ همسان]' if match else '[  ]'} {t}")
        else:
            print("⚠️ هیچ عنوانی دریافت نشد.")

if __name__ == "__main__":
    main()
