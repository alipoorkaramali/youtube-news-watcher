import requests
import xml.etree.ElementTree as ET
import os
import json
import subprocess
import re
from datetime import datetime, timedelta, timezone
from collections import OrderedDict

WATCHLIST_FILE = "watchlist.json"
SAVED_CHANNELS_FILE = "saved_channels.txt"
OUTPUT_FILE = "diagnostic_results.txt"
CATALOG_FILE = "channel_catalog.md"
CATALOG_INDEX_FILE = "catalog_index.json"
SOUNDCLOUD_MAX_AGE_HOURS = 48
SOUNDCLOUD_PLAYLIST_END = 80
SOUNDCLOUD_CATALOG_LIMIT = 20
YOUTUBE_RSS_LIMIT = 50

CATALOG_ISSUE_TITLE = "📺 Channel Catalog – Download"

def write_output(text):
    print(text)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def iran_offset():
    return timedelta(hours=3, minutes=30)

def iran_now():
    return datetime.now(timezone.utc) + iran_offset()

def extract_soundcloud_date(entry):
    upload_date_str = entry.get("upload_date")
    if upload_date_str and isinstance(upload_date_str, str) and len(upload_date_str) >= 8:
        try:
            return datetime.strptime(upload_date_str[:8], "%Y%m%d").replace(tzinfo=timezone.utc), True
        except ValueError:
            pass
    for key in ("timestamp", "release_timestamp", "modified_timestamp"):
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

def load_saved_channels():
    yt, sc = [], []
    if not os.path.exists(SAVED_CHANNELS_FILE):
        return {"youtube": yt, "soundcloud": sc}
    with open(SAVED_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower()
            if low.startswith("youtube:"):
                val = line.split(":", 1)[1].strip()
                if val and val not in yt:
                    yt.append(val)
            elif low.startswith("soundcloud:"):
                val = line.split(":", 1)[1].strip()
                if val and val not in sc:
                    sc.append(val)
            elif line.startswith("UC") and len(line) >= 20 and " " not in line:
                if line not in yt:
                    yt.append(line)
            elif "soundcloud.com" in low:
                if line not in sc:
                    sc.append(line)
    return {"youtube": yt, "soundcloud": sc}

def append_saved_channel(kind, value):
    value = (value or "").strip()
    if not value:
        return False
    existing = load_saved_channels()
    if kind == "youtube":
        if value in existing["youtube"]:
            write_output(f"Already in {SAVED_CHANNELS_FILE}: youtube:{value}")
            return False
        prefix = "youtube:"
    elif kind == "soundcloud":
        if value in existing["soundcloud"]:
            write_output(f"Already in {SAVED_CHANNELS_FILE}: soundcloud:{value}")
            return False
        prefix = "soundcloud:"
    else:
        return False
    need_header = not os.path.exists(SAVED_CHANNELS_FILE) or os.path.getsize(SAVED_CHANNELS_FILE) == 0
    with open(SAVED_CHANNELS_FILE, "a", encoding="utf-8") as f:
        if need_header:
            f.write("# Saved channels for Full Diagnostic\n")
            f.write("# Format: youtube:CHANNEL_ID   or   soundcloud:URL\n")
            f.write("# One entry per line. Lines starting with # are comments.\n\n")
        f.write(f"{prefix}{value}\n")
    write_output(f"Saved to {SAVED_CHANNELS_FILE}: {prefix}{value}")
    return True

def seed_saved_from_watchlist(items):
    if os.path.exists(SAVED_CHANNELS_FILE) and os.path.getsize(SAVED_CHANNELS_FILE) > 0:
        return
    yt, sc = OrderedDict(), OrderedDict()
    for item in items:
        platform = item.get("platform", "youtube")
        cid = (item.get("channel_id") or "").strip()
        if not cid:
            continue
        if platform == "youtube":
            yt[cid] = True
        elif platform in ("soundcloud_playlist", "soundcloud_user"):
            sc[cid] = True
    lines = [
        "# Saved channels for Full Diagnostic",
        "# Format: youtube:CHANNEL_ID   or   soundcloud:URL",
        "# One entry per line. Lines starting with # are comments.",
        "",
    ]
    for cid in yt:
        lines.append(f"youtube:{cid}")
    for url in sc:
        lines.append(f"soundcloud:{url}")
    lines.append("")
    with open(SAVED_CHANNELS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    write_output(f"Created {SAVED_CHANNELS_FILE} from watchlist ({len(yt)} YT, {len(sc)} SC)")

def fetch_rss_youtube(channel_id, limit=YOUTUBE_RSS_LIMIT, quiet=False):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    if not quiet:
        write_output(f"Youtube RSS: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        feed_title = root.find("title", ns)
        channel_title = feed_title.text.strip() if feed_title is not None and feed_title.text else channel_id
        author = root.find("author", ns)
        author_name = None
        if author is not None:
            an = author.find("name", ns)
            if an is not None and an.text:
                author_name = an.text.strip()
        entries = root.findall("entry", ns)
        if not quiet:
            write_output(f"Found {len(entries)} videos in feed")
        results = []
        for idx, entry in enumerate(entries[:limit]):
            title_el = entry.find("title", ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else "(no title)"
            link_el = entry.find("link", ns)
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            published = entry.find("published", ns)
            pub_str = published.text if published is not None else "Unknown"
            results.append({"title": title, "link": link, "published_str": pub_str})
            if not quiet:
                write_output(f"{idx+1}. {title}")
                write_output(f"   {link}")
                write_output(f"   {pub_str}")
        return {
            "channel_id": channel_id,
            "channel_title": author_name or channel_title,
            "rss_url": url,
            "channel_url": f"https://www.youtube.com/channel/{channel_id}",
            "items": results,
            "error": None,
        }
    except Exception as e:
        if not quiet:
            write_output(f"YouTube error: {e}")
        return {
            "channel_id": channel_id,
            "channel_title": channel_id,
            "rss_url": url,
            "channel_url": f"https://www.youtube.com/channel/{channel_id}",
            "items": [],
            "error": str(e),
        }

def fetch_soundcloud_by_ytdlp(url, limit=40, quiet=False):
    if not quiet:
        write_output(f"SoundCloud: {url}")
    try:
        cmd = ["yt-dlp", "--flat-playlist", "-J", "--no-warnings", "--playlist-end", str(SOUNDCLOUD_PLAYLIST_END), url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            if not quiet:
                write_output(f"yt-dlp error: {(result.stderr or '')[:200]}")
            return {"url": url, "title": url, "items": [], "error": (result.stderr or "")[:300]}
        data = json.loads(result.stdout)
        entries = data.get("entries") or []
        if not entries and data.get("title"):
            entries = [data]
        sc_title = data.get("title") or data.get("uploader") or url
        if not quiet:
            write_output(f"Found {len(entries)} tracks")
        results = []
        for idx, track in enumerate(entries[: min(limit, len(entries))]):
            if not track:
                continue
            title = track.get("title", "(no title)")
            link = track.get("webpage_url") or track.get("url") or ""
            pub_date, _ = extract_soundcloud_date(track)
            pub_str = pub_date.isoformat() if pub_date else "Unknown"
            results.append({"title": title, "link": link, "published_str": pub_str})
            if not quiet:
                write_output(f"{idx+1}. {title}")
                write_output(f"   {link or '(none)'}")
                write_output(f"   {pub_str}")
        return {"url": url, "title": sc_title, "items": results, "error": None}
    except subprocess.TimeoutExpired:
        if not quiet:
            write_output("SoundCloud timeout")
        return {"url": url, "title": url, "items": [], "error": "timeout"}
    except Exception as e:
        if not quiet:
            write_output(f"SoundCloud error: {e}")
        return {"url": url, "title": url, "items": [], "error": str(e)}

def build_catalog(yt_ids, sc_urls, keyword_map=None):
    keyword_map = keyword_map or {}
    catalog = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at_iran": iran_now().isoformat(),
        "youtube": [],
        "soundcloud": [],
    }
    write_output("Building channel_catalog.md")
    for cid in yt_ids:
        data = fetch_rss_youtube(cid, limit=YOUTUBE_RSS_LIMIT, quiet=False)
        data["watchlist_keywords"] = keyword_map.get(("youtube", cid), [])
        catalog["youtube"].append(data)
    for url in sc_urls:
        data = fetch_soundcloud_by_ytdlp(url, limit=SOUNDCLOUD_CATALOG_LIMIT, quiet=False)
        data["watchlist_keywords"] = keyword_map.get(("soundcloud", url), [])
        data["platform"] = "soundcloud_playlist"
        data["items"] = data.get("items", [])[:SOUNDCLOUD_CATALOG_LIMIT]
        catalog["soundcloud"].append(data)
    return catalog

def write_catalog_md(catalog):
    lines = []
    index = {}
    counter = 0

    lines.append("# Channel Catalog")
    lines.append("")
    lines.append(f"Generated (UTC):  {catalog['generated_at_utc']}")
    lines.append(f"Generated (Iran): {catalog['generated_at_iran']}")
    lines.append("Replaced on every Full Diagnostic run.")
    lines.append(f"Channel list file: {SAVED_CHANNELS_FILE}")
    lines.append("")
    lines.append("=" * 40)
    lines.append("How to add to watchlist.json")
    lines.append("=" * 40)
    lines.append("")
    lines.append("  platform: youtube | soundcloud_playlist")
    lines.append("  channel_id: UCxxxx  or  https://soundcloud.com/...")
    lines.append("  title_keyword: part of title")
    lines.append("  start_time_iran: 18:00")
    lines.append("  check_every_minutes: 60")
    lines.append("  max_attempts: 5")
    lines.append("")
    lines.append("=" * 40)
    lines.append(f"YouTube channels ({len(catalog['youtube'])})")
    lines.append("=" * 40)
    lines.append("")
    if not catalog["youtube"]:
        lines.append("(none)")
        lines.append("")
    else:
        for n, yt in enumerate(catalog["youtube"], 1):
            name = yt.get("channel_title") or yt["channel_id"]
            n_items = len(yt.get("items") or [])
            err = " [ERROR]" if yt.get("error") else ""
            lines.append(f"  {n}) {name}{err}  —  {n_items} videos")
        lines.append("")
        lines.append("-" * 40)
        lines.append("")
    for n, yt in enumerate(catalog["youtube"], 1):
        name = yt.get("channel_title") or yt["channel_id"]
        lines.append(f"### {n}. {name}")
        lines.append("")
        lines.append(f"  channel_id : {yt['channel_id']}")
        lines.append(f"  channel_url: {yt.get('channel_url', '')}")
        lines.append(f"  rss_feed   : {yt.get('rss_url', '')}")
        kws = yt.get("watchlist_keywords") or []
        lines.append(f"  keywords   : {', '.join(kws) if kws else '—'}")
        if yt.get("error"):
            lines.append(f"  error      : {yt['error']}")
        lines.append("")
        items = yt.get("items") or []
        lines.append(f"  Videos in RSS ({len(items)}):")
        lines.append("")
        if not items:
            lines.append("    (no items)")
            lines.append("")
        else:
            for i, it in enumerate(items, 1):
                title = it.get("title") or ""
                link = it.get("link") or ""
                pub = (it.get("published_str") or "").replace("T", " ").replace("+00:00", "Z")
                if len(pub) > 19:
                    pub = pub[:19]
                counter += 1
                lines.append(f"    {counter}. [{pub}]")
                lines.append(f"       {title}")
                if link:
                    lines.append(f"       {link}")
                lines.append("")
                if link:
                    index[str(counter)] = {
                        "url": link,
                        "platform": "youtube",
                        "title": title,
                        "format": "video",
                        "channel": name,
                    }
        lines.append("-" * 40)
        lines.append("")
    lines.append("=" * 40)
    lines.append(f"SoundCloud sources ({len(catalog['soundcloud'])})")
    lines.append(f"(last {SOUNDCLOUD_CATALOG_LIMIT} posts each)")
    lines.append("=" * 40)
    lines.append("")
    if not catalog["soundcloud"]:
        lines.append("(none)")
        lines.append("")
    else:
        for n, sc in enumerate(catalog["soundcloud"], 1):
            name = sc.get("title") or sc.get("url") or ""
            n_items = len(sc.get("items") or [])
            err = " [ERROR]" if sc.get("error") else ""
            lines.append(f"  {n}) {name}{err}  —  {n_items} posts")
        lines.append("")
        lines.append("-" * 40)
        lines.append("")
    for n, sc in enumerate(catalog["soundcloud"], 1):
        name = sc.get("title") or sc.get("url")
        lines.append(f"### {n}. {name}")
        lines.append("")
        lines.append(f"  url / channel_id: {sc.get('url')}")
        lines.append(f"  platform        : {sc.get('platform') or 'soundcloud_playlist'}")
        kws = sc.get("watchlist_keywords") or []
        lines.append(f"  keywords        : {', '.join(kws) if kws else '—'}")
        if sc.get("error"):
            lines.append(f"  error           : {sc['error']}")
        lines.append("")
        items = sc.get("items") or []
        lines.append(f"  Last posts ({len(items)}):")
        lines.append("")
        if not items:
            lines.append("    (no items)")
            lines.append("")
        else:
            for i, it in enumerate(items, 1):
                title = it.get("title") or ""
                link = it.get("link") or ""
                pub = (it.get("published_str") or "").replace("T", " ").replace("+00:00", "Z")
                if len(pub) > 19:
                    pub = pub[:19]
                counter += 1
                lines.append(f"    {counter}. [{pub}]")
                lines.append(f"       {title}")
                if link:
                    lines.append(f"       {link}")
                lines.append("")
                if link:
                    index[str(counter)] = {
                        "url": link,
                        "platform": "soundcloud",
                        "title": title,
                        "format": "audio",
                        "channel": name,
                    }
        lines.append("-" * 40)
        lines.append("")
    lines.append("End of catalog.")
    lines.append("")
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    write_output(f"Saved: {CATALOG_FILE}")

    with open(CATALOG_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    write_output(f"Saved: {CATALOG_INDEX_FILE} ({len(index)} items)")

    return lines, index

def youtube_video_id(url: str) -> str:
    """Extract YouTube video/shorts ID from URL."""
    if not url:
        return ""
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"/(?:shorts|embed)/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    return ""


def soundcloud_track_id(url: str) -> str:
    """Extract a short SoundCloud track slug/id from URL."""
    if not url:
        return ""
    parts = url.rstrip("/").split("/")
    if len(parts) >= 1:
        slug = parts[-1]
        if slug and slug not in ("sets", "tracks", "likes"):
            return slug[:40]
    return ""


def build_issue_body(catalog, index):
    """Issue body: simple list first (Termux/Gitty), rich preview collapsed for GitHub mobile."""
    body = []
    body.append("# 📺 Channel Catalog – Download")
    body.append("")
    body.append(f"**Generated (Iran):** {catalog['generated_at_iran'][:19]}")
    body.append(f"**Total items:** {len(index)}")
    body.append("")
    body.append("Download: comment `/download 12`")
    body.append("")
    body.append("---")
    body.append("")

    simple = []
    rich = []
    counter = 0

    for yt in catalog.get("youtube", []):
        name = yt.get("channel_title") or yt.get("channel_id") or "YouTube"
        items = yt.get("items") or []
        if not items:
            continue
        simple.append(f"### ▶️ {name}")
        simple.append("")
        rich.append(f"### ▶️ {name}")
        rich.append("")
        for it in items:
            link = it.get("link") or ""
            if not link:
                continue
            counter += 1
            title = (it.get("title") or "").replace("\n", " ").strip()
            pub = (it.get("published_str") or "").replace("T", " ").replace("+00:00", "")[:16]
            simple.append(f"{counter}. {title}")
            if pub and pub != "Unknown":
                simple.append(f"   {pub}")
            simple.append("")

            vid = youtube_video_id(link)
            thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else ""
            sid = vid or f"yt-{counter}"
            rich.append(f"**{counter}.** `{sid}` · [{pub}]")
            if thumb:
                rich.append("")
                rich.append(f"![{sid}]({thumb})")
            rich.append("")
            rich.append(title)
            rich.append("")
            rich.append(f"[Open]({link})")
            rich.append("")
        simple.append("")
        rich.append("")

    for sc in catalog.get("soundcloud", []):
        name = sc.get("title") or sc.get("url") or "SoundCloud"
        items = sc.get("items") or []
        if not items:
            continue
        simple.append(f"### ☁️ {name}")
        simple.append("")
        rich.append(f"### ☁️ {name}")
        rich.append("")
        for it in items:
            link = it.get("link") or ""
            if not link:
                continue
            counter += 1
            title = (it.get("title") or "").replace("\n", " ").strip()
            pub = (it.get("published_str") or "").replace("T", " ").replace("+00:00", "")[:16]
            simple.append(f"{counter}. {title}")
            if pub and pub != "Unknown":
                simple.append(f"   {pub}")
            simple.append("")

            sid = soundcloud_track_id(link) or f"sc-{counter}"
            rich.append(f"**{counter}.** ☁️ `{sid}` · [{pub}]")
            rich.append("")
            rich.append(title)
            rich.append("")
            rich.append(f"[Open]({link})")
            rich.append("")
        simple.append("")
        rich.append("")

    body.extend(simple)

    body.append("---")
    body.append("")
    body.append("<details>")
    body.append("<summary>📱 Preview with thumbnails (GitHub)</summary>")
    body.append("")
    body.extend(rich)
    body.append("</details>")
    body.append("")
    body.append("*Updated on every Full Diagnostic run.*")
    return "\n".join(body)


def update_catalog_issue(catalog, index):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GH_PAT1")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        write_output("⚠️ GITHUB_TOKEN or GITHUB_REPOSITORY not set — skipping Issue update")
        return

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    body = build_issue_body(catalog, index)

    search_url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": "open", "per_page": 50}
    try:
        resp = requests.get(search_url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        issues = resp.json()
    except Exception as e:
        write_output(f"❌ Failed to list issues: {e}")
        return

    existing = None
    for iss in issues:
        if iss.get("title") == CATALOG_ISSUE_TITLE:
            existing = iss
            break

    if existing:
        issue_number = existing["number"]
        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
        payload = {"body": body}
        try:
            r = requests.patch(url, headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                write_output(f"✅ Catalog Issue updated: #{issue_number} → {existing.get('html_url')}")
            else:
                write_output(f"❌ Failed to update issue #{issue_number}: {r.status_code} {r.text[:200]}")
        except Exception as e:
            write_output(f"❌ Error updating issue: {e}")
    else:
        url = f"https://api.github.com/repos/{repo}/issues"
        payload = {
            "title": CATALOG_ISSUE_TITLE,
            "body": body,
            "labels": ["catalog", "download"],
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code == 201:
                data = r.json()
                write_output(f"✅ Catalog Issue created: #{data['number']} → {data.get('html_url')}")
            else:
                write_output(f"❌ Failed to create issue: {r.status_code} {r.text[:200]}")
        except Exception as e:
            write_output(f"❌ Error creating issue: {e}")

def main():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    write_output("=== Diagnostic Results ===")
    write_output(f"Catalog: YT RSS up to {YOUTUBE_RSS_LIMIT} | SC last {SOUNDCLOUD_CATALOG_LIMIT}")

    items = []
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    else:
        write_output("Missing watchlist.json (will still use saved_channels.txt)")

    seed_saved_from_watchlist(items)

    extra_yt = (os.environ.get("EXTRA_YOUTUBE") or "").strip()
    extra_sc = (os.environ.get("EXTRA_SOUNDCLOUD") or "").strip()
    save_flag = (os.environ.get("SAVE_TO_LIST") or "").strip().lower() in ("1", "true", "yes", "on")

    if save_flag:
        if extra_yt:
            append_saved_channel("youtube", extra_yt)
        if extra_sc:
            append_saved_channel("soundcloud", extra_sc)
    elif extra_yt or extra_sc:
        write_output("Extra channel(s) provided but SAVE_TO_LIST is off — not appending to saved list")

    saved = load_saved_channels()
    write_output(f"Saved channels: {len(saved['youtube'])} YouTube, {len(saved['soundcloud'])} SoundCloud")

    keyword_map = {}
    for item in items:
        platform = item.get("platform", "youtube")
        cid = (item.get("channel_id") or "").strip()
        kw = item.get("title_keyword", "")
        if not cid:
            continue
        key = ("youtube", cid) if platform == "youtube" else ("soundcloud", cid)
        keyword_map.setdefault(key, [])
        if kw and kw not in keyword_map[key]:
            keyword_map[key].append(kw)

    yt_order = OrderedDict()
    sc_order = OrderedDict()
    for cid in saved["youtube"]:
        yt_order[cid] = True
    for url in saved["soundcloud"]:
        sc_order[url] = True
    for item in items:
        platform = item.get("platform", "youtube")
        cid = (item.get("channel_id") or "").strip()
        if not cid:
            continue
        if platform == "youtube":
            yt_order[cid] = True
        elif platform in ("soundcloud_playlist", "soundcloud_user"):
            sc_order[cid] = True
    if extra_yt:
        yt_order[extra_yt] = True
    if extra_sc:
        sc_order[extra_sc] = True

    for item in items:
        platform = item.get("platform", "youtube")
        channel_id = item.get("channel_id", "")
        keywords = item.get("title_keyword", "")
        if isinstance(keywords, str):
            keywords = [keywords.strip()] if keywords.strip() else []
        elif isinstance(keywords, list):
            keywords = [k.strip() for k in keywords if k.strip()]
        else:
            keywords = []
        write_output(f"\nItem: platform={platform}, id={channel_id}, keywords={keywords}")
        if platform == "youtube":
            data = fetch_rss_youtube(channel_id)
            results = data.get("items") or []
            if results:
                write_output("Keyword matches:")
                for r in results:
                    match = any(kw.lower() in r["title"].lower() for kw in keywords)
                    write_output(f"  {'[MATCH]' if match else '[    ]'} {r['title']}")
            else:
                write_output("No titles")
        elif platform in ("soundcloud_playlist", "soundcloud_user"):
            data = fetch_soundcloud_by_ytdlp(channel_id)
            results = data.get("items") or []
            if results:
                write_output("Titles:")
                for r in results:
                    match = any(kw.lower() in r["title"].lower() for kw in keywords)
                    write_output(f"  {'[MATCH]' if match else '[    ]'} {r['title']}")
            else:
                write_output("No titles")
        else:
            write_output("Unknown platform")

    catalog = build_catalog(list(yt_order.keys()), list(sc_order.keys()), keyword_map)
    _, index = write_catalog_md(catalog)
    update_catalog_issue(catalog, index)

if __name__ == "__main__":
    main()
