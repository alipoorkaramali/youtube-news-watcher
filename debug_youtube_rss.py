import requests
import xml.etree.ElementTree as ET
import os
import json
import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "diagnostic_results.txt"

def write_output(text):
    """نوشتن هم در کنسول و هم در فایل"""
    print(text)
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(text + '\n')

def _parse_feed_entries(root, limit=15):
    """Parse both Atom and RSS 2.0 feeds robustly. Returns list of (title, link, pub_str)."""
    results = []

    # Try Atom first
    ns_atom = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('atom:entry', ns_atom)
    if not entries:
        entries = root.findall('{http://www.w3.org/2005/Atom}entry')
    if not entries:
        entries = root.findall('entry')

    if entries:
        for entry in entries[:limit]:
            title_el = entry.find('{http://www.w3.org/2005/Atom}title') or entry.find('title') or entry.find('atom:title', ns_atom)
            link_el = entry.find('{http://www.w3.org/2005/Atom}link') or entry.find('link') or entry.find('atom:link', ns_atom)
            pub_el = entry.find('{http://www.w3.org/2005/Atom}published') or entry.find('published') or entry.find('atom:published', ns_atom)
            if pub_el is None:
                pub_el = entry.find('{http://www.w3.org/2005/Atom}updated') or entry.find('updated')

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            link = None
            if link_el is not None:
                link = link_el.get('href') or (link_el.text.strip() if link_el.text else None)
            pub_str = pub_el.text if pub_el is not None else 'Unknown'

            if title and link:
                results.append((title, link, pub_str))
        return results

    # Try RSS 2.0
    channel = root.find('channel')
    if channel is not None:
        items = channel.findall('item')
        for item in items[:limit]:
            title_el = item.find('title')
            link_el = item.find('link')
            pub_el = item.find('pubDate') or item.find('published')

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            link = link_el.text.strip() if link_el is not None and link_el.text else None
            pub_str = pub_el.text if pub_el is not None else 'Unknown'

            if title and link:
                results.append((title, link, pub_str))
    return results


def fetch_rss_youtube(channel_id, limit=15):
    """دریافت عناوین و لینک‌ها - اولویت با OpenRSS، سپس فید رسمی یوتیوب"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    # 1) Try OpenRSS first (correct format)
    openrss_url = f"https://openrss.org/feed/www.youtube.com/channel/{channel_id}/videos"
    write_output(f"📡 دریافت فید از OpenRSS: {openrss_url}")

    try:
        resp = requests.get(openrss_url, headers=headers, timeout=25)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            results = _parse_feed_entries(root, limit)
            if results:
                write_output(f"✅ OpenRSS موفق - {len(results)} ویدیو پیدا شد.")
                titles = []
                for idx, (title, link, pub_str) in enumerate(results):
                    titles.append(title)
                    write_output(f"{idx+1}. {title}")
                    write_output(f"   Link: {link}")
                    write_output(f"   Published: {pub_str}")
                return titles
            else:
                write_output("⚠️ OpenRSS خالی بود، سراغ فید رسمی می‌رویم...")
        else:
            write_output(f"⚠️ OpenRSS وضعیت {resp.status_code}، سراغ فید رسمی می‌رویم...")
    except Exception as e:
        write_output(f"⚠️ خطا در OpenRSS: {e} - سراغ فید رسمی می‌رویم...")

    # 2) Fallback to official YouTube RSS
    official_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    write_output(f"📡 دریافت فید رسمی یوتیوب: {official_url}")

    try:
        resp = requests.get(official_url, headers=headers, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        results = _parse_feed_entries(root, limit)
        write_output(f"✅ فید رسمی موفق - {len(results)} ویدیو پیدا شد.")
        titles = []
        for idx, (title, link, pub_str) in enumerate(results):
            titles.append(title)
            write_output(f"{idx+1}. {title}")
            write_output(f"   Link: {link}")
            write_output(f"   Published: {pub_str}")
        return titles
    except Exception as e:
        write_output(f"❌ خطا در فید رسمی یوتیوب: {e}")
        return []

def fetch_soundcloud_by_ytdlp(url, limit=15):
    """دریافت عناوین و لینک‌ها از ساندکلاد با استفاده از yt-dlp"""
    write_output(f"📡 دریافت اطلاعات از ساندکلاد: {url}")
    try:
        cmd = ['yt-dlp', '--flat-playlist', '-J', '--no-warnings', url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            write_output(f"❌ yt-dlp خطا: {result.stderr[:200]}")
            return []
        data = json.loads(result.stdout)
        
        # استخراج entries بسته به نوع (پلی‌لیست یا کاربر)
        entries = []
        if 'entries' in data:
            entries = data['entries']
        elif data.get('_type') == 'playlist':
            entries = data.get('entries', [])
        elif 'title' in data:
            entries = [data]  # تک آهنگ
        else:
            write_output("❌ فرمت داده نامشخص است.")
            return []
        
        write_output(f"✅ {len(entries)} آهنگ/ویدئو پیدا شد.")
        titles = []
        for idx, track in enumerate(entries[:limit]):
            title = track.get('title', 'بدون عنوان')
            # لینک: اولویت با webpage_url، سپس url
            link = track.get('webpage_url') or track.get('url') or ''
            titles.append(title)
            write_output(f"{idx+1}. {title}")
            if link:
                write_output(f"   Link: {link}")
            else:
                write_output(f"   Link: (نامشخص)")
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
