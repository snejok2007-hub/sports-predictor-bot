"""⚙️ Конфігурація бота"""

import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY")

SPORTS_CONFIG = {
    'football':   {'name': 'Футбол',    'emoji': '⚽', 'flashscore_id': 's'},
    'basketball': {'name': 'Баскетбол', 'emoji': '🏀', 'flashscore_id': 'b'},
    'tennis':     {'name': 'Теніс',     'emoji': '🎾', 'flashscore_id': 't'},
    'hockey':     {'name': 'Хокей',     'emoji': '🏒', 'flashscore_id': 'h'},
}

FLASHSCORE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Referer": "https://www.flashscore.ua/",
}

EXCLUDED_COUNTRIES = ['russia', 'belarus']
EXCLUDED_LEAGUES = ['КХЛ', 'РПЛ', 'ФНЛ', 'VTB United League']
