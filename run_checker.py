import time
from datetime import datetime

def run_scanner():
    print(f"[{datetime.now()}] 🔄 اجرای چک‌کننده...")
    try:
        import subprocess
        result = subprocess.run(["python", "youtube_scanner.py"], 
                              capture_output=True, text=True, timeout=600)
        print(result.stdout)
        if result.stderr:
            print("⚠️ stderr:", result.stderr)
    except Exception as e:
        print(f"❌ خطا در اجرای اسکنر: {e}")

def main():
    print("🚀 Railway YouTube/SoundCloud Checker Service شروع به کار کرد...")
    print("📋 بر اساس زمان‌بندی watchlist.json کار می‌کند")
    
    while True:
        run_scanner()
        time.sleep(300)  # هر ۵ دقیقه بیدار می‌شود (اسکریپت داخلی منطق خواب را دارد)

if __name__ == "__main__":
    main()
