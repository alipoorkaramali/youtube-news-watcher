import requests
import xml.etree.ElementTree as ET
import os
import json
import subprocess
import re
from datetime import datetime, timedelta, timezone

# ================== تنظیمات ==================
WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "diagnostic_results.txt"
SOUNDCLOUD_MAX_AGE_HOURS = 48
SOUNDCLOUD_PLAYLIST_END = 50
SOUNDCLOUD_TOP_UNKNOWN_SAFE = 10

def write_output(text):
    """نوشتن هم در کنسول و هم در فایل"""
    print(text)
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(text + '\n')

def iran_offset():
    return timedelta(hours=3, minutes=30)

def iran_now():
    return datetime.now(timezone.utc) + iran_offset()

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0):
        g_d_m[2] = 29
    gy2 = gy - 1600
    gy -= 1600
    if gm > 2:
        gy2 += 1
    days = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400 - 80 + gd + g_d_m[gm-1]
    jy = 979
    while days >= 365:
        if jy % 33 in [1, 5, 9, 13, 17, 22, 26, 30]:
            if days >= 366:
                days -= 366
                jy += 1
            else:
                break
        else:
            days -= 365
            jy += 1
    if jy % 33 in [1, 5, 9, 13, 17, 22, 26, 30]:
        jm_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    else:
        jm_days = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 30]
    jm = 1
    while days >= jm_days[jm-1]:
        days -= jm_days[jm-1]
        jm += 1
    jd = days + 1
    return (jy, jm, jd)

def extract_soundcloud_date(entry):
    """همان منطق youtube_scanner.py"""
    upload_date_str = entry.get('upload_date')
    if upload_date_str and isinstance(upload_date_str, str) and len(upload_date_str) >= 8:
        try:
            pub_date = datetime.strptime(upload_date_str[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
            return pub_date, True
        except ValueError:
            pass

    for key in ('timestamp', 'release_timestamp', 'modified_timestamp'):
        ts = entry.get(key)
        if ts is not None:
            try:
                ts = float(ts)
                if ts > 1e12:
                    ts = ts / 1000.0
                if ts > 1e9:
                    pub_date = datetime.fromtimestamp(ts, tz=timezone.utc)
                    return pub_date, True
            except (ValueError, TypeError, OSError):
                pass

    return None, False

def fetch_rss_youtube(channel_id, limit=15):
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
        results = []
        for idx, entry in enumerate(entries[:limit]):
            title = entry.find('title', ns).text.strip()
            link = entry.find('link', ns).attrib['href']
            published = entry.find('published', ns)
            pub_str = published.text if published is not None else 'Unknown'
            results.append({"title": title, "link": link, "published_str": pub_str})
            write_output(f"{idx+1}. {title}")
            write_output(f"   Link: {link}")
            write_output(f"   Published: {pub_str}")
        if len(entries) > limit:
            write_output(f"... و {len(entries)-limit} ویدیوی دیگر (محدودیت {limit})")
        return results
    except Exception as e:
        write_output(f"❌ خطا در یوتیوب: {e}")
        return []

def fetch_soundcloud_by_ytdlp(url, limit=20):
    write_output(f"📡 دریافت اطلاعات از ساندکلاد: {url}")
    try:
        cmd = [
            'yt-dlp', '--flat-playlist', '-J', '--no-warnings',
            '--playlist-end', str(SOUNDCLOUD_PLAYLIST_END), url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            write_output(f"❌ yt-dlp خطا: {result.stderr[:200]}")
            return []
        data = json.loads(result.stdout)

        entries = data.get('entries') or []
        if not entries and data.get('title'):
            entries = [data]

        write_output(f"✅ {len(entries)} آهنگ/ویدئو پیدا شد (محدود به {SOUNDCLOUD_PLAYLIST_END} تای آخر).")

        today_greg = iran_now().date()
        jy, jm, jd = gregorian_to_jalali(today_greg.year, today_greg.month, today_greg.day)
        today_persian = (jy, jm, jd)
        persian_months = {
            'فروردین':1, 'اردیبهشت':2, 'خرداد':3,
            'تیر':4, 'مرداد':5, 'شهریور':6,
            'مهر':7, 'آبان':8, 'آذر':9,
            'دی':10, 'بهمن':11, 'اسفند':12
        }
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SOUNDCLOUD_MAX_AGE_HOURS)

        results = []
        show_limit = min(limit, len(entries))
        for idx, track in enumerate(entries[:show_limit]):
            if not track:
                continue
            title = track.get('title', 'بدون عنوان')
            link = track.get('webpage_url') or track.get('url') or ''

            pub_date, date_known = extract_soundcloud_date(track)
            pub_str = pub_date.isoformat() if pub_date else 'Unknown'

            # منطق ACCEPT دقیقاً مثل youtube_scanner
            if date_known:
                is_recent = pub_date is not None and pub_date >= cutoff
                position_ok = True
            else:
                is_recent = False
                position_ok = idx < SOUNDCLOUD_TOP_UNKNOWN_SAFE

            persian_match = False
            if title:
                match = re.search(
                    r'(\d{1,2})\s+'
                    r'(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)'
                    r'(?:\s+(\d{4}))?', title
                )
                if match:
                    day = int(match.group(1))
                    month = persian_months[match.group(2)]
                    year = int(match.group(3)) if match.group(3) else jy
                    if (year, month, day) == today_persian:
                        persian_match = True

            would_accept = (is_recent or (not date_known and position_ok)) and persian_match

            results.append({
                "title": title,
                "link": link,
                "published_str": pub_str,
                "date_known": date_known,
                "is_recent": is_recent,
                "position_ok": position_ok,
                "persian_match": persian_match,
                "would_accept": would_accept
            })

            status = "✅ ACCEPT" if would_accept else "  "
            write_output(f"{idx+1}. [{status}] {title}")
            write_output(f"   Link: {link if link else '(نامشخص)'}")
            write_output(f"   Published: {pub_str} | date_known={date_known}")
            write_output(f"   Recent: {is_recent} | Top{SOUNDCLOUD_TOP_UNKNOWN_SAFE}: {position_ok} | Persian-today: {persian_match}")

        if len(entries) > show_limit:
            write_output(f"... و {len(entries)-show_limit} مورد دیگر (نمایش محدود به {show_limit})")
        return results
    except subprocess.TimeoutExpired:
        write_output("❌ زمان‌بری در دریافت اطلاعات از ساندکلاد")
        return []
    except Exception as e:
        write_output(f"❌ خطا در yt-dlp: {e}")
        return []

def main():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    write_output("=== Diagnostic Results ===")
    write_output(f"SoundCloud: max_age={SOUNDCLOUD_MAX_AGE_HOURS}h | playlist_end={SOUNDCLOUD_PLAYLIST_END} | top_unknown_safe={SOUNDCLOUD_TOP_UNKNOWN_SAFE}")

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
            results = fetch_rss_youtube(channel_id)
            if results:
                write_output("📋 عناوین همسان‌سازی شده با کلیدواژه:")
                for r in results:
                    match = any(kw.lower() in r['title'].lower() for kw in keywords)
                    write_output(f"   {'[✅ همسان]' if match else '[  ]'} {r['title']}")
            else:
                write_output("⚠️ هیچ عنوانی دریافت نشد.")

        elif platform in ('soundcloud_playlist', 'soundcloud_user'):
            results = fetch_soundcloud_by_ytdlp(channel_id)
            if results:
                write_output("📋 نتیجه فیلتر اصلی (همان منطق youtube_scanner):")
                accepted = [r for r in results if r['would_accept']]
                if accepted:
                    for r in accepted:
                        kw_match = any(kw.lower() in r['title'].lower() for kw in keywords)
                        write_output(f"   {'[✅ ACCEPT + KEYWORD]' if kw_match else '[✅ ACCEPT]'} {r['title']}")
                else:
                    write_output("   هیچ ترکی با فیلتر تاریخ + موقعیت + تاریخ شمسی امروز قبول نشد.")

                write_output("📋 همه عناوین + وضعیت کلیدواژه (فقط تطابق متنی):")
                for r in results:
                    match = any(kw.lower() in r['title'].lower() for kw in keywords)
                    write_output(f"   {'[✅ همسان]' if match else '[  ]'} {r['title']}")
            else:
                write_output("⚠️ هیچ عنوانی دریافت نشد.")
        else:
            write_output("❌ پلتفرم نامعتبر.")

if __name__ == "__main__":
    main()
