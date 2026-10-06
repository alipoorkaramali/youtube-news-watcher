#!/usr/bin/env python3
"""youtube_scanner — loads last full implementation and applies config/ path."""
import urllib.request
import sys

URL = "https://raw.githubusercontent.com/alipoorkaramali/youtube-news-watcher/cc811e8664c14d7bf389fea27b2a4007cb9ce1b1/src/youtube_scanner.py"

def main():
    try:
        with urllib.request.urlopen(URL, timeout=45) as r:
            code = r.read().decode("utf-8")
    except Exception as e:
        print("Failed to load scanner implementation:", e)
        sys.exit(1)
    code = code.replace('WATCHLIST_FILE = "watchlist.json"', 'WATCHLIST_FILE = "config/watchlist.json"')
    ns = {"__name__": "__main__", "__file__": __file__}
    exec(compile(code, "youtube_scanner.py", "exec"), ns)

if __name__ == "__main__":
    main()
