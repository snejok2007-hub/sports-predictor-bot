"""
📡 Flashscore Scraper
Отримує матчі та статистику з flashscore.ua
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, date
from typing import Optional
from config import SPORTS_CONFIG, FLASHSCORE_HEADERS, EXCLUDED_COUNTRIES, EXCLUDED_LEAGUES

logger = logging.getLogger(__name__)


class FlashscoreScraper:

    BASE_URL = "https://www.flashscore.ua"
    API_BASE = "https://local-ruua.flashscore.ninja/46/x/feed"

    def __init__(self):
        self.session = None
        self._match_cache = {}  # Кеш матчів по ID

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=FLASHSCORE_HEADERS)
        return self.session

    async def get_today_matches(self, limit: int = 50) -> list[dict]:
        all_matches = []
        for sport in ['football', 'basketball', 'tennis', 'hockey']:
            try:
                matches = await self.get_matches_by_sport(sport, limit=10)
                all_matches.extend(matches)
            except Exception as e:
                logger.warning(f"Помилка отримання {sport}: {e}")
        all_matches.sort(key=lambda x: x.get('time', '99:99'))
        return all_matches[:limit]

    async def get_matches_by_sport(self, sport: str, limit: int = 20) -> list[dict]:
        if sport == 'all':
            return await self.get_today_matches(limit)

        sport_cfg = SPORTS_CONFIG.get(sport)
        if not sport_cfg:
            return []

        sport_id = sport_cfg.get('flashscore_id', 's')
        url = f"{self.API_BASE}/p_1_{sport_id}_1_UA_{sport_id}_"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    matches = self._parse_matches(text, sport, limit)
                    if matches:
                        # Зберігаємо в кеш
                        for m in matches:
                            self._match_cache[m['id']] = m
                        return matches
        except Exception as e:
            logger.error(f"Flashscore API error: {e}")

        matches = self._get_demo_matches(sport, limit)
        for m in matches:
            self._match_cache[m['id']] = m
        return matches

    async def get_match_details(self, match_id: str) -> dict:
        # Спочатку шукаємо в кеші
        if match_id in self._match_cache:
            return self._match_cache[match_id]

        # Якщо немає — пробуємо отримати з API
        url = f"{self.API_BASE}/d_su._{match_id}_"
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return self._parse_match_details(text, match_id)
        except Exception as e:
            logger.error(f"Match details error: {e}")

        return self._match_cache.get(match_id, self._get_empty_match(match_id))

    def _is_excluded(self, match: dict) -> bool:
        league = match.get('league', '')
        country = match.get('country', '')
        for excl in EXCLUDED_LEAGUES:
            if excl.lower() in league.lower():
                return True
        for excl in EXCLUDED_COUNTRIES:
            if excl.lower() in country.lower():
                return True
        return False

    def _parse_matches(self, raw: str, sport: str, limit: int) -> list[dict]:
        matches = []
        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '⚽')
        try:
            chunks = raw.split('~')
            for chunk in chunks[:limit]:
                parts = chunk.split('¬')
                if len(parts) > 10:
                    match = self._extract_match_from_parts(parts, sport, emoji)
                    if match and not self._is_excluded(match):
                        matches.append(match)
        except Exception as e:
            logger.debug(f"Parse error: {e}")
        return matches if matches else self._get_demo_matches(sport, limit)

    def _extract_match_from_parts(self, parts: list, sport: str, emoji: str) -> Optional[dict]:
        try:
            match_id = parts[0] if parts[0] else None
            if not match_id:
                return None
            timestamp = parts[1] if len(parts) > 1 else ''
            home = parts[2] if len(parts) > 2 else 'Home'
            away = parts[3] if len(parts) > 3 else 'Away'
            league = parts[4] if len(parts) > 4 else ''
            time_str = ''
            if timestamp.isdigit():
                dt = datetime.fromtimestamp(int(timestamp))
                time_str = dt.strftime('%H:%M')
            return {
                'id': match_id, 'sport': sport, 'sport_emoji': emoji,
                'home': home, 'away': away, 'league': league,
                'time': time_str, 'date': date.today().isoformat(),
            }
        except Exception:
            return None

    def _parse_match_details(self, raw: str, match_id: str) -> dict:
        cached = self._match_cache.get(match_id, self._get_empty_match(match_id))
        return cached

    def _get_empty_match(self, match_id: str) -> dict:
        return {
            'id': match_id, 'sport': 'football', 'sport_emoji': '⚽',
            'home': 'Невідома команда А', 'away': 'Невідома команда Б',
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
                ('Аякс', 'Фейєноорд', 'Ередивізі', '19:00'),
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
                ('Женева', 'Цюрих', 'NLA (Швейцарія)', '19:00'),
                ('Відень', 'Грац', 'ICEHL (Австрія)', '18:30'),
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
            self._match_cache[match_id] = match  # Одразу кешуємо
        return matches

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
