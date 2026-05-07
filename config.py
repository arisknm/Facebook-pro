"""
Konfigurasi untuk agent konten bola.
Isi file .env dengan kredensial yang sesuai.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic / Claude (opsional, jika masih dipakai)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Google Gemini (gratis 1.500 req/hari)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Facebook / Meta
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")

# YouTube
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

# Football Data API (api-football.com / football-data.org)
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")
FOOTBALL_API_HOST = os.getenv("FOOTBALL_API_HOST", "v3.football.api-sports.io")

# News API (newsapi.org)
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# Konten
BAHASA = os.getenv("BAHASA", "id")  # id = Indonesia
LIGA_FAVORIT = os.getenv("LIGA_FAVORIT", "Premier League,La Liga,Serie A,Bundesliga,Liga 1").split(",")

# Output dir
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
