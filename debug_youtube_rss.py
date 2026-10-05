import requests
import xml.etree.ElementTree as ET
import os
import json
import subprocess
import re
from datetime import datetime, timedelta, timezone
from collections import OrderedDict

WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "diagnostic_results.txt"
CATALOG_FILE = "channel_catalog.md"
SOUNDCLOUD_MAX_AGE_HOURS = 48
SOUNDCLOUD_PLAYLIST_END = 80
SOUNDCLOUD_CATALOG_LIMIT = 20
YOUTUBE_RSS_LIMIT = 50

PERSIAN_WEEKDAYS = {
    'شنبه': 5, 'یکشنبه': 6, 'دوشنبه': 0, 'سه‌شنبه': 1, 'سه شنبه': 1,
    'چهارشنبه': 2, 'پنج‌شنبه': 3, 'پنجشنبه': 3, 'جمعه': 4,
}

def write_output(text):
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
    gy -= 1600
    days = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400 - 80 + gd + g_d_m[gm - 1]
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
    while days >= jm_days[jm - 1]:
        days -= jm_days[jm - 1]
        jm += 1
    return (jy, jm, days + 1)

def extract_soundcloud_date(entry):
    upload_date_str = entry.get('upload_date')
    if upload_date_str and isinstance(upload_date_str, str) and len(upload_date_str) >= 8:
        try:
            return datetime.strptime(upload_date_str[:8], '%Y%m%d').replace(tzinfo=timezone.utc), True
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
                    return datetime.fromtimestamp(ts, tz=timezone.utc), True
            except (ValueError, TypeError, OSError):
                pass
    return None, False

def fetch_rss_youtube(channel_id, limit=YOUTUBE_RSS_LIMIT, quiet=False):
    url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
    if not quiet:
        write_output(f'📡 دریافت فید یوتیوب: {url}')
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {'': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
        feed_title = root.find('title', ns)
        channel_title = feed_title.text.strip() if feed_title is not None and feed_title.text else channel_id
        author = root.find('author', ns)
        author_name = None
        if author is not None:
            an = author.find('name', ns)
            if an is not None and an.text:
                author_name = an.text.strip()
        entries = root.findall('entry', ns)
        if not quiet:
            write_output(f'✅ {len(entries)} ویدیو در فید پیدا شد.')
        results = []
        for idx, entry in enumerate(entries[:limit]):
            title_el = entry.find('title', ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else '(no title)'
            link_el = entry.find('link', ns)
            link = link_el.attrib.get('href', '') if link_el is not None else ''
            published = entry.find('published', ns)
            pub_str = published.text if published is not None else 'Unknown'
            video_id_el = entry.find('yt:videoId', ns)
            video_id = video_id_el.text if video_id_el is not None else ''
            results.append({'title': title, 'link': link, 'published_str': pub_str, 'video_id': video_id})
            if not quiet:
                write_output(f'{idx+1}. {title}')
                write_output(f'   Link: {link}')
                write_output(f'   Published: {pub_str}')
        return {
            'channel_id': channel_id,
            'channel_title': author_name or channel_title,
            'rss_url': url,
            'channel_url': f'https://www.youtube.com/channel/{channel_id}',
            'items': results,
            'error': None,
        }
    except Exception as e:
        if not quiet:
            write_output(f'❌ خطا در یوتیوب: {e}')
        return {
            'channel_id': channel_id,
            'channel_title': channel_id,
            'rss_url': url,
            'channel_url': f'https://www.youtube.com/channel/{channel_id}',
            'items': [],
            'error': str(e),
        }

def fetch_soundcloud_by_ytdlp(url, limit=40, quiet=False):
    if not quiet:
        write_output(f'📡 دریافت اطلاعات از ساندکلاد: {url}')
    try:
        cmd = ['yt-dlp', '--flat-playlist', '-J', '--no-warnings', '--playlist-end', str(SOUNDCLOUD_PLAYLIST_END), url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            if not quiet:
                write_output(f'❌ yt-dlp خطا: {(result.stderr or "")[:200]}')
            return {'url': url, 'title': url, 'items': [], 'error': (result.stderr or '')[:300]}
        data = json.loads(result.stdout)
        entries = data.get('entries') or []
        if not entries and data.get('title'):
            entries = [data]
        sc_title = data.get('title') or data.get('uploader') or url
        if not quiet:
            write_output(f'✅ {len(entries)} آهنگ/ویدئو پیدا شد.')
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SOUNDCLOUD_MAX_AGE_HOURS)
        results = []
        for idx, track in enumerate(entries[:min(limit, len(entries))]):
            if not track:
                continue
            title = track.get('title', 'بدون عنوان')
            link = track.get('webpage_url') or track.get('url') or ''
            pub_date, date_known = extract_soundcloud_date(track)
            pub_str = pub_date.isoformat() if pub_date else 'Unknown'
            is_recent = bool(date_known and pub_date and pub_date >= cutoff)
            results.append({
                'title': title, 'link': link, 'published_str': pub_str,
                'date_known': date_known, 'is_recent': is_recent, 'would_accept': False,
            })
            if not quiet:
                write_output(f'{idx+1}. {title}')
                write_output(f'   Link: {link or "(نامشخص)"}')
                write_output(f'   Published: {pub_str}')
        return {'url': url, 'title': sc_title, 'items': results, 'error': None}
    except subprocess.TimeoutExpired:
        if not quiet:
            write_output('❌ زمان‌بری در دریافت اطلاعات از ساندکلاد')
        return {'url': url, 'title': url, 'items': [], 'error': 'timeout'}
    except Exception as e:
        if not quiet:
            write_output(f'❌ خطا در yt-dlp: {e}')
        return {'url': url, 'title': url, 'items': [], 'error': str(e)}

def build_catalog(watchlist_items):
    yt_ids = OrderedDict()
    sc_urls = OrderedDict()
    for item in watchlist_items:
        platform = item.get('platform', 'youtube')
        cid = (item.get('channel_id') or '').strip()
        kw = item.get('title_keyword', '')
        if not cid:
            continue
        if platform == 'youtube':
            yt_ids.setdefault(cid, {'keywords': []})
            if kw and kw not in yt_ids[cid]['keywords']:
                yt_ids[cid]['keywords'].append(kw)
        elif platform in ('soundcloud_playlist', 'soundcloud_user'):
            sc_urls.setdefault(cid, {'keywords': [], 'platform': platform})
            if kw and kw not in sc_urls[cid]['keywords']:
                sc_urls[cid]['keywords'].append(kw)
    catalog = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'generated_at_iran': iran_now().isoformat(),
        'youtube': [],
        'soundcloud': [],
    }
    write_output('\n' + '=' * 60)
    write_output('📚 ساخت کاتالوگ تمیز کانال‌ها (channel_catalog.md)')
    write_output('=' * 60)
    for cid, meta in yt_ids.items():
        write_output(f'\n▶ YouTube catalog: {cid}')
        data = fetch_rss_youtube(cid, limit=YOUTUBE_RSS_LIMIT, quiet=False)
        data['watchlist_keywords'] = meta['keywords']
        catalog['youtube'].append(data)
    for url, meta in sc_urls.items():
        write_output(f'\n▶ SoundCloud catalog (last {SOUNDCLOUD_CATALOG_LIMIT}): {url}')
        data = fetch_soundcloud_by_ytdlp(url, limit=SOUNDCLOUD_CATALOG_LIMIT, quiet=False)
        data['watchlist_keywords'] = meta['keywords']
        data['platform'] = meta['platform']
        data['items'] = data.get('items', [])[:SOUNDCLOUD_CATALOG_LIMIT]
        catalog['soundcloud'].append(data)
    return catalog

def write_catalog_md(catalog):
    """Issue-style layout: index table + per-channel identity table + items table."""
    lines = []
    lines.append('# Channel Catalog')
    lines.append('')
    lines.append(f"- **Generated (UTC):** `{catalog['generated_at_utc']}`")
    lines.append(f"- **Generated (Iran):** `{catalog['generated_at_iran']}`")
    lines.append('- **Purpose:** clean list of sources + recent posts to help add watchlist items')
    lines.append('- **Note:** this file is **replaced** on every Full Diagnostic run')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## How to add a new item to `watchlist.json`')
    lines.append('')
    lines.append('| Field | Example |')
    lines.append('|-------|---------|')
    lines.append('| `platform` | `youtube` or `soundcloud_playlist` |')
    lines.append('| `channel_id` | `UCxxxxxxxx` or `https://soundcloud.com/...` |')
    lines.append('| `title_keyword` | part of the video/track title |')
    lines.append('| `start_time_iran` | `18:00` |')
    lines.append('| `check_every_minutes` | `60` |')
    lines.append('| `max_attempts` | `5` |')
    lines.append('')
    lines.append('```json')
    lines.append('{')
    lines.append('  "platform": "youtube",')
    lines.append('  "channel_id": "UCxxxxxxxx",')
    lines.append('  "title_keyword": "بخشی از عنوان",')
    lines.append('  "start_time_iran": "18:00",')
    lines.append('  "check_every_minutes": 60,')
    lines.append('  "max_attempts": 5')
    lines.append('}')
    lines.append('```')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append(f"## YouTube channels ({len(catalog['youtube'])})")
    lines.append('')
    if catalog['youtube']:
        lines.append('| # | Channel | channel_id | Keywords in watchlist | Items |')
        lines.append('|---|---------|------------|------------------------|-------|')
        for n, yt in enumerate(catalog['youtube'], 1):
            name = (yt.get('channel_title') or yt['channel_id']).replace('|', '\\|')
            cid = yt['channel_id']
            kws = ', '.join(yt.get('watchlist_keywords') or []) or '—'
            kws = kws.replace('|', '\\|')
            n_items = len(yt.get('items') or [])
            err = ' ⚠️' if yt.get('error') else ''
            lines.append(f'| {n} | {name}{err} | `{cid}` | {kws} | {n_items} |')
        lines.append('')
        lines.append('_Details per channel below._')
        lines.append('')
    else:
        lines.append('_No YouTube sources in watchlist._')
        lines.append('')
    for n, yt in enumerate(catalog['youtube'], 1):
        name = yt.get('channel_title') or yt['channel_id']
        lines.append(f'### {n}. {name}')
        lines.append('')
        lines.append('| | |')
        lines.append('|---|---|')
        lines.append(f"| **channel_id** | `{yt['channel_id']}` |")
        lines.append(f"| **Channel URL** | {yt.get('channel_url', '')} |")
        lines.append(f"| **RSS feed** | {yt.get('rss_url', '')} |")
        kws = yt.get('watchlist_keywords') or []
        lines.append(f"| **Keywords already watched** | {', '.join(f'`{k}`' for k in kws) if kws else '—'} |")
        if yt.get('error'):
            lines.append(f"| **Error** | {yt['error']} |")
        lines.append('')
        items = yt.get('items') or []
        lines.append(f'#### Videos in RSS ({len(items)})')
        lines.append('')
        if not items:
            lines.append('_No items._')
            lines.append('')
        else:
            lines.append('| # | Published | Title | Link |')
            lines.append('|---|-----------|-------|------|')
            for i, it in enumerate(items, 1):
                title = (it.get('title') or '').replace('|', '\\|')
                link = it.get('link') or ''
                pub = (it.get('published_str') or '').replace('T', ' ').replace('+00:00', 'Z')
                if len(pub) > 19:
                    pub = pub[:19]
                link_md = f'[open]({link})' if link else '—'
                lines.append(f'| {i} | {pub} | {title} | {link_md} |')
            lines.append('')
    lines.append('---')
    lines.append('')
    lines.append(f"## SoundCloud sources ({len(catalog['soundcloud'])})")
    lines.append('')
    lines.append(f'_Last {SOUNDCLOUD_CATALOG_LIMIT} posts per source._')
    lines.append('')
    if catalog['soundcloud']:
        lines.append('| # | Source | URL | Keywords in watchlist | Posts |')
        lines.append('|---|--------|-----|------------------------|-------|')
        for n, sc in enumerate(catalog['soundcloud'], 1):
            name = (sc.get('title') or sc.get('url') or '').replace('|', '\\|')
            url = sc.get('url') or ''
            kws = ', '.join(sc.get('watchlist_keywords') or []) or '—'
            kws = kws.replace('|', '\\|')
            n_items = len(sc.get('items') or [])
            err = ' ⚠️' if sc.get('error') else ''
            lines.append(f'| {n} | {name}{err} | `{url}` | {kws} | {n_items} |')
        lines.append('')
        lines.append('_Details per source below._')
        lines.append('')
    else:
        lines.append('_No SoundCloud sources in watchlist._')
        lines.append('')
    for n, sc in enumerate(catalog['soundcloud'], 1):
        name = sc.get('title') or sc.get('url')
        lines.append(f'### {n}. {name}')
        lines.append('')
        lines.append('| | |')
        lines.append('|---|---|')
        lines.append(f"| **URL / channel_id** | `{sc.get('url')}` |")
        lines.append(f"| **platform** | `{sc.get('platform') or 'soundcloud_playlist'}` |")
        kws = sc.get('watchlist_keywords') or []
        lines.append(f"| **Keywords already watched** | {', '.join(f'`{k}`' for k in kws) if kws else '—'} |")
        if sc.get('error'):
            lines.append(f"| **Error** | {sc['error']} |")
        lines.append('')
        items = sc.get('items') or []
        lines.append(f'#### Last posts ({len(items)})')
        lines.append('')
        if not items:
            lines.append('_No items._')
            lines.append('')
        else:
            lines.append('| # | Published | Title | Link |')
            lines.append('|---|-----------|-------|------|')
            for i, it in enumerate(items, 1):
                title = (it.get('title') or '').replace('|', '\\|')
                link = it.get('link') or ''
                pub = (it.get('published_str') or '').replace('T', ' ').replace('+00:00', 'Z')
                if len(pub) > 19:
                    pub = pub[:19]
                link_md = f'[open]({link})' if link else '—'
                lines.append(f'| {i} | {pub} | {title} | {link_md} |')
            lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('_End of catalog._')
    lines.append('')
    with open(CATALOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    write_output(f'\n✅ کاتالوگ ذخیره شد: {CATALOG_FILE}')

def main():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    write_output('=== Diagnostic Results ===')
    write_output(f'SoundCloud: max_age={SOUNDCLOUD_MAX_AGE_HOURS}h | playlist_end={SOUNDCLOUD_PLAYLIST_END}')
    write_output(f'Catalog: YouTube RSS up to {YOUTUBE_RSS_LIMIT} | SoundCloud last {SOUNDCLOUD_CATALOG_LIMIT}')
    if not os.path.exists(WATCHLIST_FILE):
        write_output('❌ فایل watchlist.json وجود ندارد.')
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
        write_output(f'\n🔍 بررسی آیتم: پلتفرم={platform}, شناسه={channel_id}, کلیدواژه‌ها={keywords}')
        if platform == 'youtube':
            data = fetch_rss_youtube(channel_id)
            results = data.get('items') or []
            if results:
                write_output('📋 عناوین همسان‌سازی شده با کلیدواژه:')
                for r in results:
                    match = any(kw.lower() in r['title'].lower() for kw in keywords)
                    write_output(f"   {'[✅ همسان]' if match else '[  ]'} {r['title']}")
            else:
                write_output('⚠️ هیچ عنوانی دریافت نشد.')
        elif platform in ('soundcloud_playlist', 'soundcloud_user'):
            data = fetch_soundcloud_by_ytdlp(channel_id)
            results = data.get('items') or []
            if results:
                write_output('📋 همه عناوین:')
                for r in results:
                    match = any(kw.lower() in r['title'].lower() for kw in keywords)
                    write_output(f"   {'[✅ همسان]' if match else '[  ]'} {r['title']}")
            else:
                write_output('⚠️ هیچ عنوانی دریافت نشد.')
        else:
            write_output('❌ پلتفرم نامعتبر.')
    catalog = build_catalog(items)
    write_catalog_md(catalog)

if __name__ == '__main__':
    main()
