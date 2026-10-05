import requests
import xml.etree.ElementTree as ET
import os
import json
import subprocess
from datetime import datetime, timedelta, timezone
from collections import OrderedDict

WATCHLIST_FILE = "watchlist.json"
OUTPUT_FILE = "diagnostic_results.txt"
CATALOG_FILE = "channel_catalog.md"
SOUNDCLOUD_MAX_AGE_HOURS = 48
SOUNDCLOUD_PLAYLIST_END = 80
SOUNDCLOUD_CATALOG_LIMIT = 20
YOUTUBE_RSS_LIMIT = 50

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
            pub_date, date_known = extract_soundcloud_date(track)
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

def build_catalog(watchlist_items):
    yt_ids = OrderedDict()
    sc_urls = OrderedDict()
    for item in watchlist_items:
        platform = item.get("platform", "youtube")
        cid = (item.get("channel_id") or "").strip()
        kw = item.get("title_keyword", "")
        if not cid:
            continue
        if platform == "youtube":
            yt_ids.setdefault(cid, {"keywords": []})
            if kw and kw not in yt_ids[cid]["keywords"]:
                yt_ids[cid]["keywords"].append(kw)
        elif platform in ("soundcloud_playlist", "soundcloud_user"):
            sc_urls.setdefault(cid, {"keywords": [], "platform": platform})
            if kw and kw not in sc_urls[cid]["keywords"]:
                sc_urls[cid]["keywords"].append(kw)
    catalog = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at_iran": iran_now().isoformat(),
        "youtube": [],
        "soundcloud": [],
    }
    write_output("Building channel_catalog.md")
    for cid, meta in yt_ids.items():
        data = fetch_rss_youtube(cid, limit=YOUTUBE_RSS_LIMIT, quiet=False)
        data["watchlist_keywords"] = meta["keywords"]
        catalog["youtube"].append(data)
    for url, meta in sc_urls.items():
        data = fetch_soundcloud_by_ytdlp(url, limit=SOUNDCLOUD_CATALOG_LIMIT, quiet=False)
        data["watchlist_keywords"] = meta["keywords"]
        data["platform"] = meta["platform"]
        data["items"] = data.get("items", [])[:SOUNDCLOUD_CATALOG_LIMIT]
        catalog["soundcloud"].append(data)
    return catalog

def write_catalog_md(catalog):
    """Line blocks — readable in Termux with RTL Persian (no markdown tables)."""
    lines = []
    lines.append("# Channel Catalog")
    lines.append("")
    lines.append(f"Generated (UTC):  {catalog['generated_at_utc']}")
    lines.append(f"Generated (Iran): {catalog['generated_at_iran']}")
    lines.append("Replaced on every Full Diagnostic run.")
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
                lines.append(f"    {i}. [{pub}]")
                lines.append(f"       {title}")
                if link:
                    lines.append(f"       {link}")
                lines.append("")
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
                lines.append(f"    {i}. [{pub}]")
                lines.append(f"       {title}")
                if link:
                    lines.append(f"       {link}")
                lines.append("")
        lines.append("-" * 40)
        lines.append("")
    lines.append("End of catalog.")
    lines.append("")
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    write_output(f"Saved: {CATALOG_FILE}")

def main():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    write_output("=== Diagnostic Results ===")
    write_output(f"Catalog: YT RSS up to {YOUTUBE_RSS_LIMIT} | SC last {SOUNDCLOUD_CATALOG_LIMIT}")
    if not os.path.exists(WATCHLIST_FILE):
        write_output("Missing watchlist.json")
        return
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)
    for item in items:
        platform = item.get("platform", "youtube")
        channel_id = item.get("channel_id", "")
        keywords = item.get("title_keyword", "")
        if isinstance(keywords, str):
            keywords = [keywords.strip()]
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
    catalog = build_catalog(items)
    write_catalog_md(catalog)

if __name__ == "__main__":
    main()
