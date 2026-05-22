import requests
import xml.etree.ElementTree as ET
import os, json, subprocess, sys
from datetime import datetime

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "diagnostic_results.txt"

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
        for idx, entry in enumerate(entries[:15]):
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
        write_output(f"❌ خطا در یوتیوب: {e}")
        return []

def fetch_soundcloud_by_ytdlp(url, limit=15):
    """دریافت عناوین از ساندکلاد با استفاده از yt-dlp"""
    write_output(f"📡 دریافت اطلاعات از ساندکلاد: {url}")
    try:
        # اجرای yt-dlp برای گرفتن JSON خروجی
        cmd = ['yt-dlp', '--flat-playlist', '-J', '--no-warnings', url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            write_output(f"❌ yt-dlp خطا: {result.stderr[:200]}")
            return []
        data = json.loads(result.stdout)
        # اگر کاربر باشد، entries داخل data است
        # اگر پلی‌لیست باشد، entries داخل data['entries']
        if 'entries' in data:
            entries = data['entries']
        else:
            entries = [data]  # تک آهنگ یا کاربر؟ در حالت کاربر، خود data شامل tracks نیست
            # برای کاربر، باید به فیلد 'tracks' مراجعه کنیم اما yt-dlp آن را به صورت جداگانه نمی‌دهد.
            # راه حل: اگر url به soundcloud.com/username ختم شود، از --flat-playlist استفاده نمی‌شود؟
            # ساده‌تر: اگر data['_type'] == 'playlist' باشد، entries را بگیر.
            if data.get('_type') == 'playlist':
                entries = data.get('entries', [])
            else:
                # احتمالاً یک track تکی است
                if 'title' in data:
                    entries = [data]
                else:
                    write_output("❌ فرمت داده نامشخص است.")
                    return []
        write_output(f"✅ {len(entries)} آهنگ/ویدئو پیدا شد.")
        titles = []
        for idx, track in enumerate(entries[:limit]):
            title = track.get('title', 'بدون عنوان')
            webpage_url = track.get('webpage_url', '')
            titles.append(title)
            write_output(f"{idx+1}. {title}")
            if webpage_url:
                write_output(f"   Link: {webpage_url}")
        if len(entries) > limit:
            write_output(f"... و {len(entries)-limit} مورد دیگر (محدودیت {limit})")
        return titles
    except subprocess.TimeoutExpired:
        write_output("❌ زمان‌بری در دریافت اطلاعات از ساندکلاد")
        return []
    except Exception as e:
        write_output(f"❌ خطا در yt-dlp: {e}")
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
        elif platform in ('soundcloud_playlist', 'soundcloud_user'):
            # با yt-dlp هر دو نوع پشتیبانی می‌شود
            titles = fetch_soundcloud_by_ytdlp(channel_id)
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