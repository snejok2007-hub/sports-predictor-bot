"""🤖 Sports Predictor — детальні прогнози з імовірностями"""

import asyncio
import aiohttp
import json
import logging
from config import ANTHROPIC_API_KEY, SPORTS_CONFIG

logger = logging.getLogger(__name__)

SPORT_TOTALS = {
    'football':   {'label': 'Голів',  'line': 2.5,   'unit': 'голів',   'high_line': 3.5},
    'basketball': {'label': 'Очок',   'line': 210.5, 'unit': 'очок',    'high_line': 225.5},
    'tennis':     {'label': 'Геймів', 'line': 20.5,  'unit': 'геймів',  'high_line': 23.5},
    'hockey':     {'label': 'Шайб',   'line': 4.5,   'unit': 'шайб',    'high_line': 5.5},
}

SPORT_PERIODS = {
    'football':   '1-й тайм / 2-й тайм',
    'basketball': '1-й кв / 2-й кв / 3-й кв / 4-й кв',
    'tennis':     '1-й сет / 2-й сет / 3-й сет',
    'hockey':     '1-й пер / 2-й пер / 3-й пер',
}


class SportsPredictor:

    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, scraper=None):
        # Використовуємо переданий скрапер або створюємо новий
        if scraper:
            self.scraper = scraper
        else:
            from scraper import FlashscoreScraper
            self.scraper = FlashscoreScraper()

    async def predict_match(self, match: dict) -> dict:
        sport = match.get('sport', 'football')
        stats = self._analyze_stats(match)
        ai = await self._get_ai_prediction(match)

        return {
            **match,
            'prediction': ai.get('prediction') or stats['prediction'],
            'confidence': self._merge_confidence(stats['confidence'], ai.get('confidence', 0)),
            'win_probs': ai.get('win_probs', ''),
            'stats_prediction': stats['summary'],
            'totals_forecast': ai.get('totals_forecast', '') or stats['totals'],
            'periods_forecast': ai.get('periods_forecast', ''),
            'key_factors': ai.get('key_factors', ''),
        }

    def _analyze_stats(self, match: dict) -> dict:
        sport = match.get('sport', 'football')
        home = match.get('home', 'Господарі')
        away = match.get('away', 'Гості')
        home_form = match.get('home_form', [])
        away_form = match.get('away_form', [])

        form_scores = {'W': 3, 'D': 1, 'L': 0}
        home_pts = sum(form_scores.get(r, 0) for r in home_form) if home_form else 7
        away_pts = sum(form_scores.get(r, 0) for r in away_form) if away_form else 7
        max_pts = max(len(home_form), 1) * 3

        home_pct = round((home_pts / max_pts) * 100)
        away_pct = round((away_pts / max_pts) * 100)

        home_form_str = ' '.join(['✅' if r=='W' else '🔲' if r=='D' else '❌' for r in home_form[-5:]]) if home_form else 'немає даних'
        away_form_str = ' '.join(['✅' if r=='W' else '🔲' if r=='D' else '❌' for r in away_form[-5:]]) if away_form else 'немає даних'

        diff = home_pts - away_pts
        if diff >= 4:
            pred = f"Перемога {home}"
            conf = min(72, 52 + diff * 2)
        elif diff <= -4:
            pred = f"Перемога {away}"
            conf = min(72, 52 + abs(diff) * 2)
        else:
            pred = "Нічия або мінімальна різниця" if sport == 'football' else f"Перевага {home if diff >= 0 else away}"
            conf = 48

        tcfg = SPORT_TOTALS.get(sport, SPORT_TOTALS['football'])
        totals = f"⬆️ Більше {tcfg['line']} {tcfg['unit']} / ⬇️ Менше {tcfg['high_line']} {tcfg['unit']}"

        summary = (
            f"📊 {home}: {home_form_str} ({home_pct}%)\n"
            f"📊 {away}: {away_form_str} ({away_pct}%)"
        )

        return {'prediction': pred, 'confidence': conf, 'summary': summary, 'totals': totals,
                'home_pts': home_pts, 'away_pts': away_pts}

    async def _get_ai_prediction(self, match: dict) -> dict:
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "YOUR_ANTHROPIC_API_KEY":
            return {}

        sport = match.get('sport', 'football')
        home = match.get('home', '?')
        away = match.get('away', '?')
        league = match.get('league', '')
        home_form = match.get('home_form', [])
        away_form = match.get('away_form', [])
        sport_name = SPORTS_CONFIG.get(sport, {}).get('name', sport)
        tcfg = SPORT_TOTALS.get(sport, SPORT_TOTALS['football'])
        periods = SPORT_PERIODS.get(sport, '')

        prompt = f"""Ти професійний спортивний аналітик. Дай ДЕТАЛЬНИЙ прогноз на матч.

ВИД СПОРТУ: {sport_name}
МАТЧ: {home} vs {away}
ЛІГА: {league}
ФОРМА {home} (ост. 5): {' '.join(home_form) if home_form else 'немає'}
ФОРМА {away} (ост. 5): {' '.join(away_form) if away_form else 'немає'}
СТРУКТУРА: {periods}
ТИПОВІ ТОТАЛИ: {tcfg['line']} {tcfg['unit']}

Відповідай ТІЛЬКИ JSON (без коментарів):
{{
  "prediction": "Перемога {home} / Перемога {away} / Нічия (тільки для футболу)",
  "confidence": 65,
  "win_probs": "{home}: 55% | {away}: 30%{' | Нічия: 15%' if sport == 'football' else ''}",
  "totals_forecast": "Тотал {tcfg['label']}: Більше {tcfg['line']} ({tcfg['unit']}) — 62% | Менше — 38%",
  "periods_forecast": "детальний прогноз по {periods} з рахунком або перевагою",
  "key_factors": "3-4 конкретних фактори що впливають на результат",
  "analysis": "2-3 речення загального аналізу"
}}"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.CLAUDE_URL,
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}],
                        "system": "Відповідай ТІЛЬКИ валідним JSON без зайвого тексту."
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        return {}
                    text = data['content'][0]['text']
                    clean = text.replace('```json', '').replace('```', '').strip()
                    return json.loads(clean)
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return {}

    def _merge_confidence(self, stats_conf: int, ai_conf: int) -> int:
        if ai_conf > 0:
            return max(40, min(95, round(stats_conf * 0.3 + ai_conf * 0.7)))
        return stats_conf

    async def get_top_picks(self, limit: int = 5) -> list[dict]:
        matches = await self.scraper.get_today_matches(limit=20)
        predictions = []
        for match in matches[:10]:
            try:
                pred = await self.predict_match(match)
                if pred.get('confidence', 0) >= 60:
                    predictions.append(pred)
            except Exception as e:
                logger.warning(f"Prediction error: {e}")
        predictions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return predictions[:limit]
