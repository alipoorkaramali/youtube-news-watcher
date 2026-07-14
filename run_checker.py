import time
from datetime import datetime
import subprocess

def run_scanner():
    print(f"[{datetime.now()}] 🔄 اجرای چک‌کننده...")
    try:
        result = subprocess.run(["python", "youtube_scanner.py"], 
                              capture_output=True, text=True, timeout=600)
        print(result.stdout)
        if result.stderr:
            print("⚠️ خطا:", result.stderr)
    except Exception as e:
        print(f"❌ خطای کلی: {e}")

def main():
    print("🚀 Railway Checker Service شروع به کار کرد...")
    run_scanner()
    print("✅ اجرا تمام شد. سرویس در حالت serverless می‌خوابد...")

if __name__ == "__main__":
    main()