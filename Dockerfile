FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt yt-dlp

COPY . .

# برای اجرای دوره‌ای
CMD ["sh", "-c", "while true; do python youtube_scanner.py; sleep 900; done"]
