"""📡 Sports Scraper — FlashLive API + демо-дані"""

import aiohttp
import logging
from datetime import datetime, date
from typing import Optional
from config import SPORTS_CONFIG, FLASHSCORE_HEADERS, EXCLUDED_COUNTRIES, EXCLUDED_LEAGUES, RAPIDAPI_KEY

logger = logging.getLogger(__name__)


class FlashscoreScraper:

    RAPIDAPI_HOST = "flashlive-sports.p.rapidapi.com"
    RAPIDAPI_BASE = "https://flashlive-sports.p.rapidapi.com/v1"

    SPORT_IDS = {'football': 1, 'basketball': 3, 'tennis': 2, 'hockey': 4}

    def __init__(self):
        self.session = None
        self._match_cache = {}

    def _api_headers(self) -> dict:
        return {
            "x-rapidapi-host": self.RAPIDAPI_HOST,
            "x-rapidapi-key": RAPIDAPI_KEY,
        }

    async def _get_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_today_matches(self, limit: int = 50) -> list[dict]:
        all_matches = []
        for sport in ['football', 'basketball', 'tennis', 'hockey']:
            try:
                matches = await self.get_matches_by_sport(sport, limit=10)
                all_matches.extend(matches)
            except Exception as e:
                logger.warning(f"Error {sport}: {e}")
        all_matches.sort(key=lambda x: x.get('time', '99:99'))
        return all_matches[:limit]

    async def get_matches_by_sport(self, sport: str, limit: int = 20) -> list[dict]:
        if sport == 'all':
            return await self.get_today_matches(limit)

        if RAPIDAPI_KEY and RAPIDAPI_KEY not in ("YOUR_RAPIDAPI_KEY", ""):
            matches = await self._fetch_api_matches(sport, limit)
            if matches:
                return matches

        return self._get_demo_matches(sport, limit)

    async def _fetch_api_matches(self, sport: str, limit: int) -> list[dict]:
        sport_id = self.SPORT_IDS.get(sport, 1)
        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '⚽')

        url = f"{self.RAPIDAPI_BASE}/events/list"
        params = {"sport_id": sport_id, "locale": "uk_UA", "timezone": "2", "indent_days": "0"}

        try:
            session = await self._get_session()
            async with session.get(url, headers=self._api_headers(), params=params,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.error(f"API {resp.status}")
                    return []

                data = await resp.json()
                logger.warning(f"FlashLive raw keys: {list(data.keys())}, first item sample: {str(data)[:300]}")
                return self._parse_events(data, sport, emoji, limit)

        except Exception as e:
            logger.error(f"API fetch error: {e}")
            return []

    def _parse_events(self, data: dict, sport: str, emoji: str, limit: int) -> list[dict]:
        matches = []

        # FlashLive може повертати різні структури
        events = (data.get('DATA') or data.get('data') or
                  data.get('events') or data.get('results') or [])

        if not events:
            logger.warning(f"No events in response: {list(data.keys())}")
            return []

        for event in events:
            try:
                # Пробуємо різні назви полів
                match_id = str(
                    event.get('EVENT_ID') or event.get('id') or
                    event.get('event_id') or ''
                )
                home = (event.get('HOME_NAME') or event.get('home_name') or
                        event.get('home') or event.get('HOME_TEAM') or
                        event.get('homeName') or '').strip()
                away = (event.get('AWAY_NAME') or event.get('away_name') or
                        event.get('away') or event.get('AWAY_TEAM') or
                        event.get('awayName') or '').strip()
                league = (event.get('LEAGUE_NAME') or event.get('league_name') or
                          event.get('tournament') or event.get('TOURNAMENT_NAME') or '').strip()
                country = (event.get('COUNTRY_NAME') or event.get('country') or '').strip()

                # Пропускаємо якщо немає назв команд
                if not home or not away:
                    continue

                start = event.get('START_TIME') or event.get('start_time') or event.get('startTime') or 0
                time_str = datetime.fromtimestamp(int(start)).strftime('%H:%M') if start else '--:--'

                match = {
                    'id': match_id or f"api_{sport}_{len(matches)}",
                    'sport': sport, 'sport_emoji': emoji,
                    'home': home, 'away': away,
                    'league': league, 'country': country,
                    'time': time_str, 'date': date.today().isoformat(),
                    'home_form': [], 'away_form': [], 'h2h': [],
                }

                if not self._is_excluded(match):
                    matches.append(match)
                    self._match_cache[match['id']] = match

                if len(matches) >= limit:
                    break

            except Exception as e:
                logger.debug(f"Parse event error: {e}")
                continue

        logger.info(f"Parsed {len(matches)} matches for {sport}")
        return matches

    async def get_match_details(self, match_id: str) -> dict:
        if match_id in self._match_cache:
            return self._match_cache[match_id]
        return {'id': match_id, 'sport': 'football', 'sport_emoji': '⚽',
                'home': '?', 'away': '?', 'league': '', 'time': '--:--',
                'date': date.today().isoformat(), 'home_form': [], 'away_form': []}

    def _is_excluded(self, match: dict) -> bool:
        league = match.get('league', '').lower()
        country = match.get('country', '').lower()
        for excl in EXCLUDED_LEAGUES:
            if excl.lower() in league:
                return True
        for word in ['russia', 'russian', 'беларус', 'belarus', 'росія', 'рос']:
            if word in country or word in league:
                return True
        return False

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
        matches = []
        for i, (home, away, league, time) in enumerate(demos.get(sport, demos['football'])[:limit]):
            mid = f"demo_{sport}_{i}"
            m = {'id': mid, 'sport': sport, 'sport_emoji': emoji,
                 'home': home, 'away': away, 'league': league, 'time': time,
                 'date': date.today().isoformat(),
                 'home_form': ['W', 'W', 'D', 'W', 'L'],
                 'away_form': ['D', 'W', 'L', 'W', 'W'],
                 'home_goals_avg': round(1.2 + i * 0.2, 1),
                 'away_goals_avg': round(1.0 + i * 0.15, 1)}
            matches.append(m)
            self._match_cache[mid] = m
        return matches

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
