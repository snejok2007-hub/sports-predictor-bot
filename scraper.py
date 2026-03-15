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
    """Клас для отримання даних з Flashscore"""

    BASE_URL = "https://www.flashscore.ua"
    # Flashscore використовує внутрішній API
    API_BASE = "https://local-ruua.flashscore.ninja/46/x/feed"

    def __init__(self):
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=FLASHSCORE_HEADERS)
        return self.session

    async def get_today_matches(self, limit: int = 50) -> list[dict]:
        """Отримати всі матчі на сьогодні"""
        all_matches = []
        for sport in ['football', 'basketball', 'tennis', 'hockey']:
            try:
                matches = await self.get_matches_by_sport(sport, limit=10)
                all_matches.extend(matches)
            except Exception as e:
                logger.warning(f"Помилка отримання {sport}: {e}")

        # Сортуємо по часу
        all_matches.sort(key=lambda x: x.get('time', '99:99'))
        return all_matches[:limit]

    async def get_matches_by_sport(self, sport: str, limit: int = 20) -> list[dict]:
        """Отримати матчі за видом спорту"""
        if sport == 'all':
            return await self.get_today_matches(limit)

        sport_cfg = SPORTS_CONFIG.get(sport)
        if not sport_cfg:
            return []

        # Flashscore внутрішній endpoint для отримання матчів
        sport_id = sport_cfg.get('flashscore_id', 's')
        url = f"{self.API_BASE}/p_1_{sport_id}_1_UA_{sport_id}_"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return self._parse_matches(text, sport, limit)
        except Exception as e:
            logger.error(f"Flashscore API error: {e}")

        # Якщо Flashscore недоступний — повертаємо демо-дані
        return self._get_demo_matches(sport, limit)

    async def get_match_details(self, match_id: str) -> dict:
        """Отримати детальну інформацію про матч"""
        # Спробуємо отримати з Flashscore
        url = f"{self.API_BASE}/d_su._{match_id}_"

        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return self._parse_match_details(text, match_id)
        except Exception as e:
            logger.error(f"Match details error: {e}")

        # Повернути базові дані з кешу
        return self._get_cached_match(match_id)

    def _is_excluded(self, match: dict) -> bool:
        """Перевірити чи матч з виключеного ресурсу (РФ, Білорусь)"""
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
        """Парсинг відповіді Flashscore"""
        matches = []
        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '⚽')

        # Flashscore повертає власний бінарний формат
        # Розбиваємо по роздільнику ¬
        try:
            chunks = raw.split('~')
            for chunk in chunks[:limit]:
                parts = chunk.split('¬')
                if len(parts) > 10:
                    match = self._extract_match_from_parts(parts, sport, emoji)
                    if match:
                        if not self._is_excluded(match):
                            matches.append(match)
        except Exception as e:
            logger.debug(f"Parse error: {e}")

        return matches if matches else self._get_demo_matches(sport, limit)

    def _extract_match_from_parts(self, parts: list, sport: str, emoji: str) -> Optional[dict]:
        """Витягти дані матчу з розпарсених частин"""
        try:
            # Flashscore формат: ID¬timestamp¬home¬away¬...
            match_id = parts[0] if parts[0] else None
            if not match_id:
                return None

            timestamp = parts[1] if len(parts) > 1 else ''
            home = parts[2] if len(parts) > 2 else 'Home'
            away = parts[3] if len(parts) > 3 else 'Away'
            league = parts[4] if len(parts) > 4 else ''

            # Конвертуємо timestamp
            time_str = ''
            if timestamp.isdigit():
                dt = datetime.fromtimestamp(int(timestamp))
                time_str = dt.strftime('%H:%M')

            return {
                'id': match_id,
                'sport': sport,
                'sport_emoji': emoji,
                'home': home,
                'away': away,
                'league': league,
                'time': time_str,
                'date': date.today().isoformat(),
            }
        except Exception:
            return None

    def _parse_match_details(self, raw: str, match_id: str) -> dict:
        """Парсинг деталей матчу"""
        cached = self._get_cached_match(match_id)
        # Тут можна розширити парсинг статистики
        return cached

    def _get_cached_match(self, match_id: str) -> dict:
        """Базові дані матчу для резервного варіанту"""
        return {
            'id': match_id,
            'sport': 'football',
            'sport_emoji': '⚽',
            'home': 'Команда А',
            'away': 'Команда Б',
            'league': 'Невідома ліга',
            'time': '--:--',
            'date': date.today().isoformat(),
            'home_form': ['W', 'D', 'W', 'L', 'W'],
            'away_form': ['L', 'W', 'W', 'W', 'D'],
            'h2h': [],
            'home_goals_avg': 1.5,
            'away_goals_avg': 1.2,
        }

    def _get_demo_matches(self, sport: str, limit: int = 10) -> list[dict]:
        """Демо-матчі коли Flashscore недоступний"""
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
                ('Міланo', 'УНИКС Казань', 'Євроліга', '20:00'),
            ],
            'tennis': [
                ('Джокович', 'Алькарас', 'ATP Masters', '14:00'),
                ('Зверєв', 'Рубльов', 'ATP 500', '16:30'),
                ('Свьонтек', 'Соболенко', 'WTA 1000', '15:00'),
                ('Синнер', 'Фріц', 'ATP 250', '12:00'),
            ],
            'hockey': [
                ('Динамо Київ', 'Донбас', 'УХЛ', '17:00'),
                ('Женева', 'Цюрих', 'NLA (Швейцарія)', '19:00'),
                ('Берн', 'Фрібур', 'NLA (Швейцарія)', '19:45'),
                ('Відень Кепіталс', 'Грац', 'ICEHL (Австрія)', '18:30'),
            ],
        }

        sport_demos = demos.get(sport, demos['football'])
        matches = []
        for i, (home, away, league, time) in enumerate(sport_demos[:limit]):
            matches.append({
                'id': f"demo_{sport}_{i}",
                'sport': sport,
                'sport_emoji': emoji,
                'home': home,
                'away': away,
                'league': league,
                'time': time,
                'date': date.today().isoformat(),
                'home_form': ['W', 'W', 'D', 'W', 'L'],
                'away_form': ['D', 'W', 'L', 'W', 'W'],
                'home_goals_avg': round(1.0 + i * 0.3, 1),
                'away_goals_avg': round(0.9 + i * 0.2, 1),
            })
        return matches

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
