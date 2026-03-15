"""
⚙️ Конфігурація бота
"""

import os

# ── ОБОВ'ЯЗКОВО ЗАПОВНІТЬ ──────────────────────────────────────────────────────

# Отримати у @BotFather в Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# Отримати на https://console.anthropic.com
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")

# ── НАЛАШТУВАННЯ СПОРТУ ────────────────────────────────────────────────────────

SPORTS_CONFIG = {
    'football': {
        'name': 'Футбол',
        'emoji': '⚽',
        'flashscore_id': 's',   # soccer
    },
    'basketball': {
        'name': 'Баскетбол',
        'emoji': '🏀',
        'flashscore_id': 'b',   # basketball
    },
    'tennis': {
        'name': 'Теніс',
        'emoji': '🎾',
        'flashscore_id': 't',   # tennis
    },
    'hockey': {
        'name': 'Хокей',
        'emoji': '🏒',
        'flashscore_id': 'h',   # hockey
    },
}

# ── HTTP ЗАГОЛОВКИ ─────────────────────────────────────────────────────────────

FLASHSCORE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Referer": "https://www.flashscore.ua/",
}

# ── ФІЛЬТР ЗАБЛОКОВАНИХ РЕСУРСІВ ──────────────────────────────────────────────
# Виключаємо всі російські та білоруські ресурси

EXCLUDED_COUNTRIES = ['russia', 'russia1', 'russia2', 'belarus']

EXCLUDED_LEAGUES = [
    'КХЛ', 'РПЛ', 'ФНЛ', 'КБЛ',
    'VTB United League', 'Континентальна хокейна ліга',
    'Суперліга Росії', 'Вища ліга Білорусі',
]

# ── ОПЦІОНАЛЬНО ────────────────────────────────────────────────────────────────

# Апіфай скрапер (платний, але надійний)
# https://apify.com/actors/flashscore-scraper
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

# API-Football (безкоштовно 100 запитів/день)
# https://www.api-football.com/
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")

# RapidAPI ключ (FlashLive Sports)
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "YOUR_RAPIDAPI_KEY")
