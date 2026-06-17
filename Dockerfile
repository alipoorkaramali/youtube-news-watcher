FROM python:3.11-slim

WORKDIR /app

# نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt yt-dlp

# کپی تمام فایل‌ها
COPY . .

# اجرای چک‌کننده هوشمند
CMD ["python", "run_checker.py"]
