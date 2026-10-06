#!/usr/bin/env python3
"""debug diagnostic — loads last full implementation, applies config/data paths, patches issue help."""
import os
import sys
import urllib.request

URL = "https://raw.githubusercontent.com/alipoorkaramali/youtube-news-watcher/cc811e8664c14d7bf389fea27b2a4007cb9ce1b1/src/debug_youtube_rss.py"

HELP_OLD = 'body.append("Download: comment `/download 12`")'

HELP_NEW = '''body.append("### 📥 How to download")
    body.append("")
    body.append("Comment on this issue:")
    body.append("")
    body.append("```")
    body.append("/download <number> [audio|video] [mega|repo]")
    body.append("```")
    body.append("")
    body.append("| Option | Meaning |")
    body.append("|--------|---------|")
    body.append("| *(empty)* or `video` | Default / manual → **costume** workflow |")
    body.append("| `audio` | Audio only → **auto** workflow |")
    body.append("| *(empty)* or `repo` | Save in downloader **repo** |")
    body.append("| `mega` | Upload to **Mega.nz** |")
    body.append("")
    body.append("**Examples**")
    body.append("- `/download 5` → costume + repo")
    body.append("- `/download 5 audio` → auto audio + repo")
    body.append("- `/download 5 video mega` → costume video + Mega")
    body.append("- `/download 12 audio mega` → auto audio + Mega")'''

def main():
    try:
        with urllib.request.urlopen(URL, timeout=45) as r:
            code = r.read().decode("utf-8")
    except Exception as e:
        print("Failed to load diagnostic implementation:", e)
        sys.exit(1)

    code = code.replace('WATCHLIST_FILE = "watchlist.json"', 'WATCHLIST_FILE = "config/watchlist.json"')
    code = code.replace('SAVED_CHANNELS_FILE = "saved_channels.txt"', 'SAVED_CHANNELS_FILE = "config/saved_channels.txt"')
    code = code.replace('OUTPUT_FILE = "diagnostic_results.txt"', 'OUTPUT_FILE = "data/diagnostic_results.txt"')
    code = code.replace('CATALOG_FILE = "channel_catalog.md"', 'CATALOG_FILE = "data/channel_catalog.md"')
    code = code.replace('CATALOG_INDEX_FILE = "catalog_index.json"', 'CATALOG_INDEX_FILE = "data/catalog_index.json"')

    if HELP_OLD in code:
        code = code.replace(HELP_OLD, HELP_NEW)
    else:
        print("Warning: issue help marker not found; help text may stay old")

    for p in (
        "config/watchlist.json",
        "config/saved_channels.txt",
        "data/diagnostic_results.txt",
        "data/channel_catalog.md",
        "data/catalog_index.json",
    ):
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)

    ns = {"__name__": "__main__", "__file__": __file__}
    exec(compile(code, "debug_youtube_rss.py", "exec"), ns)

if __name__ == "__main__":
    main()
