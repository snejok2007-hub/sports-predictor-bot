"""
📡 FlashLive Sports Scraper
Отримує реальні матчі через RapidAPI FlashLive Sports
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, date
from typing import Optional
from config import SPORTS_CONFIG, FLASHSCORE_HEADERS, EXCLUDED_COUNTRIES, EXCLUDED_LEAGUES, RAPIDAPI_KEY

logger = logging.getLogger(__name__)


class FlashscoreScraper:

    # FlashLive Sports API через RapidAPI
    RAPIDAPI_HOST = "flashlive-sports.p.rapidapi.com"
    RAPIDAPI_BASE = "https://flashlive-sports.p.rapidapi.com/v1"

    # Sport IDs у FlashLive
    SPORT_IDS = {
        'football':   1,
        'basketball': 3,
        'tennis':     2,
        'hockey':     4,
    }

    def __init__(self):
        self.session = None
        self._match_cache = {}

    def _get_headers(self) -> dict:
        return {
            "x-rapidapi-host": self.RAPIDAPI_HOST,
            "x-rapidapi-key": RAPIDAPI_KEY,
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_today_matches(self, limit: int = 50) -> list[dict]:
        all_matches = []
        for sport in ['football', 'basketball', 'tennis', 'hockey']:
            try:
                matches = await self.get_matches_by_sport(sport, limit=10)
                all_matches.extend(matches)
            except Exception as e:
                logger.warning(f"Помилка {sport}: {e}")
        all_matches.sort(key=lambda x: x.get('time', '99:99'))
        return all_matches[:limit]

    async def get_matches_by_sport(self, sport: str, limit: int = 20) -> list[dict]:
        if sport == 'all':
            return await self.get_today_matches(limit)

        # Якщо є RapidAPI ключ — використовуємо реальний API
        if RAPIDAPI_KEY and RAPIDAPI_KEY != "YOUR_RAPIDAPI_KEY":
            matches = await self._fetch_flashlive_matches(sport, limit)
            if matches:
                return matches

        # Резервний демо-режим
        return self._get_demo_matches(sport, limit)

    async def _fetch_flashlive_matches(self, sport: str, limit: int) -> list[dict]:
        """Отримати матчі з FlashLive Sports API"""
        sport_id = self.SPORT_IDS.get(sport, 1)
        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '⚽')
        today = date.today().strftime('%d.%m.%Y')

        url = f"{self.RAPIDAPI_BASE}/events/list"
        params = {
            "sport_id": sport_id,
            "locale": "uk_UA",
            "timezone": "2",
            "indent_days": "0",
        }

        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    logger.error(f"FlashLive API error: {resp.status}")
                    return []

                data = await resp.json()
                return self._parse_flashlive_events(data, sport, emoji, limit)

        except Exception as e:
            logger.error(f"FlashLive fetch error: {e}")
            return []

    def _parse_flashlive_events(self, data: dict, sport: str, emoji: str, limit: int) -> list[dict]:
        """Парсинг відповіді FlashLive API"""
        matches = []

        try:
            events = data.get('DATA', [])
            for event in events[:limit * 3]:  # Беремо більше щоб після фільтрації залишилось достатньо
                try:
                    # Структура FlashLive API
                    match_id = str(event.get('EVENT_ID', ''))
                    home = event.get('HOME_NAME', 'Команда А')
                    away = event.get('AWAY_NAME', 'Команда Б')
                    league = event.get('LEAGUE_NAME', '')
                    country = event.get('COUNTRY_NAME', '')

                    # Час матчу
                    start_time = event.get('START_TIME', 0)
                    if start_time:
                        dt = datetime.fromtimestamp(int(start_time))
                        time_str = dt.strftime('%H:%M')
                    else:
                        time_str = '--:--'

                    # Статус (тільки майбутні та живі)
                    status = event.get('EVENT_STAGE_TYPE', '')

                    match = {
                        'id': match_id,
                        'sport': sport,
                        'sport_emoji': emoji,
                        'home': home,
                        'away': away,
                        'league': league,
                        'country': country,
                        'time': time_str,
                        'date': date.today().isoformat(),
                        'status': status,
                        'home_form': [],
                        'away_form': [],
                        'h2h': [],
                    }

                    if not self._is_excluded(match):
                        matches.append(match)
                        self._match_cache[match_id] = match

                    if len(matches) >= limit:
                        break

                except Exception as e:
                    logger.debug(f"Parse event error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Parse events error: {e}")

        return matches

    async def get_match_details(self, match_id: str) -> dict:
        """Отримати деталі матчу з кешу або API"""
        if match_id in self._match_cache:
            cached = self._match_cache[match_id]
            # Спробуємо отримати статистику якщо є API ключ
            if RAPIDAPI_KEY and RAPIDAPI_KEY != "YOUR_RAPIDAPI_KEY":
                details = await self._fetch_match_stats(match_id, cached)
                if details:
                    return details
            return cached

        return self._get_empty_match(match_id)

    async def _fetch_match_stats(self, match_id: str, base_match: dict) -> Optional[dict]:
        """Отримати статистику конкретного матчу"""
        url = f"{self.RAPIDAPI_BASE}/events/summary"
        params = {"event_id": match_id, "locale": "uk_UA"}

        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                summary = data.get('DATA', {})

                # Оновлюємо матч детальними даними
                match = {**base_match}

                # Форма команд якщо є
                home_form_raw = summary.get('HOME_FORM', '')
                away_form_raw = summary.get('AWAY_FORM', '')
                if home_form_raw:
                    match['home_form'] = list(home_form_raw.upper())[:5]
                if away_form_raw:
                    match['away_form'] = list(away_form_raw.upper())[:5]

                return match

        except Exception as e:
            logger.debug(f"Match stats error: {e}")
            return None

    def _is_excluded(self, match: dict) -> bool:
        league = match.get('league', '')
        country = match.get('country', '')
        for excl in EXCLUDED_LEAGUES:
            if excl.lower() in league.lower():
                return True
        for excl in EXCLUDED_COUNTRIES:
            if excl.lower() in country.lower():
                return True
        # Додатково фільтруємо за країною
        excluded_words = ['russia', 'russian', 'беларус', 'belarus', 'росія', 'росс']
        for word in excluded_words:
            if word in country.lower() or word in league.lower():
                return True
        return False

    def _get_empty_match(self, match_id: str) -> dict:
        return {
            'id': match_id, 'sport': 'football', 'sport_emoji': '⚽',
            'home': 'Команда А', 'away': 'Команда Б',
            'league': 'Невідома ліга', 'time': '--:--',
            'date': date.today().isoformat(),
            'home_form': ['W', 'D', 'W', 'L', 'W'],
            'away_form': ['L', 'W', 'W', 'W', 'D'],
            'h2h': [], 'home_goals_avg': 1.5, 'away_goals_avg': 1.2,
        }

    def _get_demo_matches(self, sport: str, limit: int = 10) -> list[dict]:
        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '⚽')
        demos = {
            'football': [
                ('Манчестер Сіті', 'Арсенал', 'АПЛ', '18:30'),
                ('Реал Мадрид', 'Барселона', 'Ла Ліга', '21:00'),
                ('Динамо Київ', 'Шахтар', 'УПЛ', '19:00'),
                ('Баварія', 'Боруссія Д', 'Бундесліга', '20:30'),
                ('ПСЖ', 'Марсель', 'Ліг 1', '21:00'),
                ('Інтер', 'Ювентус', 'Серія А', '20:45'),
            ],
            'basketball': [
                ('Лейкерс', 'Селтікс', 'НБА', '02:30'),
                ('Ворріорс', 'Буллс', 'НБА', '04:00'),
                ('Реал Мадрид', 'Барселона', 'АКБ', '21:00'),
                ('Олімпіакос', 'Панатінаїкос', 'Євроліга', '19:00'),
            ],
            'tennis': [
                ('Джокович', 'Алькарас', 'ATP Masters', '14:00'),
                ('Зверєв', 'Сінер', 'ATP 500', '16:30'),
                ('Свьонтек', 'Соболенко', 'WTA 1000', '15:00'),
            ],
            'hockey': [
                ('Динамо Київ', 'Донбас', 'УХЛ', '17:00'),
                ('Женева', 'Цюрих', 'NLA Швейцарія', '19:00'),
                ('Відень', 'Грац', 'ICEHL Австрія', '18:30'),
            ],
        }

        sport_demos = demos.get(sport, demos['football'])
        matches = []
        for i, (home, away, league, time) in enumerate(sport_demos[:limit]):
            match_id = f"demo_{sport}_{i}"
            match = {
                'id': match_id, 'sport': sport, 'sport_emoji': emoji,
                'home': home, 'away': away, 'league': league,
                'time': time, 'date': date.today().isoformat(),
                'home_form': ['W', 'W', 'D', 'W', 'L'],
                'away_form': ['D', 'W', 'L', 'W', 'W'],
                'home_goals_avg': round(1.0 + i * 0.3, 1),
                'away_goals_avg': round(0.9 + i * 0.2, 1),
            }
            matches.append(match)
            self._match_cache[match_id] = match
        return matches

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
