import time
import subprocess
from datetime import datetime, timedelta
import os

def run_scanner():
    print(f"[{datetime.now()}] شروع چک‌کننده...")
    try:
        result = subprocess.run(["python", "youtube_scanner.py"], 
                              capture_output=True, text=True, timeout=300)
        print(result.stdout)
        if result.stderr:
            print("خطا:", result.stderr)
    except Exception as e:
        print(f"خطای اجرا: {e}")

def main():
    print("🚀 چک‌کننده Railway شروع به کار کرد...")
    while True:
        now = datetime.now()
        print(f"[{now}] چک در حال انجام... (هر ۵ دقیقه بیدار می‌شوم)")
        
        run_scanner()
        
        # خواب هوشمند (۵ دقیقه)
        time.sleep(300)

if __name__ == "__main__":
    main()
