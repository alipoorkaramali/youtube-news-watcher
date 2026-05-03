import sys, os, re
import yt_dlp

VIDEO_KEYWORD = "اخبار ساعت شش"   # ← می‌توانید تغییر دهید
LOG_FILE = "logs/new_videos.txt"
OUTPUT_DIR_VIDEO = "downloads/video"
OUTPUT_DIR_AUDIO = "downloads/audio"

def download(link, title):
    # تشخیص ویدیو یا صوت
    is_video = bool(re.search(VIDEO_KEYWORD, title, re.IGNORECASE))
    out_dir = OUTPUT_DIR_VIDEO if is_video else OUTPUT_DIR_AUDIO
    os.makedirs(out_dir, exist_ok=True)

    ydl_opts = {
        'outtmpl': f'{out_dir}/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': True,
        'noplaylist': True,
        'merge_output_format': 'mp4' if is_video else None,
        # کلید حل مشکل ربات و جاوااسکریپت
        'js_runtimes': ['node'],                     # ← استفاده از Node.js
        # استفاده از curl_cffi برای شبیه‌سازی TLS مرورگر
        'impersonate': 'chrome',                     # ← اضافه کردن User-Agent مدرن
        # کوکی‌ها (اگر فایل cookies.txt وجود داشته باشد)
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
    }

    if is_video:
        ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
    else:
        ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])
        print(f"✅ دانلود موفق: {title}")
        return True
    except Exception as e:
        print(f"❌ خطا در دانلود {link}: {e}")
        return False

def main():
    if not os.path.exists(LOG_FILE):
        print("ℹ️ فایل لینک‌ها پیدا نشد.")
        sys.exit(0)

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4:
            continue
        title = parts[1]
        link = parts[-1]
        if not link.startswith('https://'):
            continue
        print(f"\n🎯 پردازش: {title}")
        if re.search(VIDEO_KEYWORD, title, re.IGNORECASE):
            print("📹 دانلود ویدیو (MP4)...")
        else:
            print("🎵 دانلود صوت (MP3)...")
        download(link, title)

if __name__ == '__main__':
    main()
