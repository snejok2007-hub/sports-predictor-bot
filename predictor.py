"""🤖 Sports Predictor — детальні прогнози з імовірностями по таймах"""

import asyncio
import aiohttp
import json
import logging
from config import ANTHROPIC_API_KEY, SPORTS_CONFIG

logger = logging.getLogger(__name__)

SPORT_CONFIG = {
    'football': {
        'total_line': 2.5, 'unit': 'голів',
        'periods': ['1-й тайм', '2-й тайм'],
        'period_totals': [1.5, 1.5],
    },
    'basketball': {
        'total_line': 210.5, 'unit': 'очок',
        'periods': ['1-й кв', '2-й кв', '3-й кв', '4-й кв'],
        'period_totals': [52.5, 53.5, 51.5, 52.5],
    },
    'tennis': {
        'total_line': 20.5, 'unit': 'геймів',
        'periods': ['1-й сет', '2-й сет', '3-й сет'],
        'period_totals': [9.5, 9.5, 9.5],
    },
    'hockey': {
        'total_line': 4.5, 'unit': 'шайб',
        'periods': ['1-й пер', '2-й пер', '3-й пер'],
        'period_totals': [1.5, 1.5, 1.5],
    },
}


class SportsPredictor:

    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-20250514"

    def __init__(self, scraper=None):
        if scraper:
            self.scraper = scraper
        else:
            from scraper import FlashscoreScraper
            self.scraper = FlashscoreScraper()

    async def predict_match(self, match: dict) -> dict:
        sport = match.get('sport', 'football')
        home = match.get('home', '?')
        away = match.get('away', '?')

        # Статистичний аналіз
        stats = self._analyze_stats(match)

        # AI прогноз
        ai = await self._get_ai_prediction(match)

        # Якщо AI не відповів — генеруємо базові дані самостійно
        if not ai:
            ai = self._generate_fallback(match, stats)

        confidence = self._merge_confidence(stats['confidence'], ai.get('confidence', 0))

        return {
            **match,
            'prediction': ai.get('prediction') or stats['prediction'],
            'confidence': confidence,
            'win_probs': ai.get('win_probs', ''),
            'stats_prediction': stats['summary'],
            'totals_forecast': ai.get('totals_forecast', ''),
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

        hf = ' '.join(['✅' if r=='W' else '🔲' if r=='D' else '❌' for r in home_form[-5:]]) if home_form else 'немає даних'
        af = ' '.join(['✅' if r=='W' else '🔲' if r=='D' else '❌' for r in away_form[-5:]]) if away_form else 'немає даних'

        diff = home_pts - away_pts
        if diff >= 4:
            pred = f"Перемога {home}"
            conf = min(70, 52 + diff * 2)
        elif diff <= -4:
            pred = f"Перемога {away}"
            conf = min(70, 52 + abs(diff) * 2)
        else:
            pred = "Нічия або мінімальна різниця" if sport == 'football' else f"Перевага {home if diff >= 0 else away}"
            conf = 48

        summary = f"📊 {home}: {hf} ({home_pct}%)\n📊 {away}: {af} ({away_pct}%)"
        return {'prediction': pred, 'confidence': conf, 'summary': summary,
                'home_pts': home_pts, 'away_pts': away_pts}

    def _generate_fallback(self, match: dict, stats: dict) -> dict:
        """Генерує детальний прогноз без AI на основі статистики"""
        sport = match.get('sport', 'football')
        home = match.get('home', '?')
        away = match.get('away', '?')
        cfg = SPORT_CONFIG.get(sport, SPORT_CONFIG['football'])

        home_pts = stats['home_pts']
        away_pts = stats['away_pts']
        total = home_pts + away_pts or 14

        # Імовірності
        home_win_pct = round(45 + (home_pts - away_pts) * 3)
        home_win_pct = max(25, min(75, home_win_pct))

        if sport == 'football':
            draw_pct = 25
            away_win_pct = 100 - home_win_pct - draw_pct
            win_probs = f"{home}: {home_win_pct}% | Нічия: {draw_pct}% | {away}: {away_win_pct}%"
        else:
            away_win_pct = 100 - home_win_pct
            win_probs = f"{home}: {home_win_pct}% | {away}: {away_win_pct}%"

        # Загальний тотал
        line = cfg['total_line']
        totals_forecast = f"Тотал {cfg['unit']}: Більше {line} — {55 if home_pts >= away_pts else 45}% | Менше {line} — {45 if home_pts >= away_pts else 55}%"

        # Тотали по таймах/чвертях
        periods_lines = []
        for period, pt_line in zip(cfg['periods'], cfg['period_totals']):
            pct = 55 if home_win_pct > 50 else 45
            periods_lines.append(f"• {period}: Більше {pt_line} {cfg['unit']} — {pct}%")
        periods_forecast = '\n'.join(periods_lines)

        prediction = f"Перемога {home}" if home_win_pct > 55 else (
            f"Перемога {away}" if away_win_pct > 55 else
            ("Нічия" if sport == 'football' else f"Рівна гра, незначна перевага {home if home_win_pct >= 50 else away}")
        )

        return {
            'prediction': prediction,
            'confidence': stats['confidence'],
            'win_probs': win_probs,
            'totals_forecast': totals_forecast,
            'periods_forecast': periods_forecast,
            'key_factors': f"Перевага господарів, поточна форма команд",
        }

    async def _get_ai_prediction(self, match: dict) -> dict:
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY in ("YOUR_ANTHROPIC_API_KEY", ""):
            return {}

        sport = match.get('sport', 'football')
        home = match.get('home', '?')
        away = match.get('away', '?')
        league = match.get('league', '')
        home_form = match.get('home_form', [])
        away_form = match.get('away_form', [])
        cfg = SPORT_CONFIG.get(sport, SPORT_CONFIG['football'])
        sport_name = SPORTS_CONFIG.get(sport, {}).get('name', sport)

        periods_str = ' / '.join(cfg['periods'])
        period_totals_str = ', '.join([f"{p}: {t}" for p, t in zip(cfg['periods'], cfg['period_totals'])])

        prompt = f"""Ти — топ спортивний аналітик. Дай ДЕТАЛЬНИЙ прогноз.

ВИД: {sport_name} | МАТЧ: {home} vs {away} | ЛІГА: {league}
ФОРМА {home}: {' '.join(home_form) if home_form else 'немає'}
ФОРМА {away}: {' '.join(away_form) if away_form else 'немає'}

ВІДПОВІДАЙ ТІЛЬКИ JSON:
{{
  "prediction": "Перемога {home} АБО Перемога {away}{' АБО Нічия' if sport == 'football' else ''}",
  "confidence": 65,
  "win_probs": "{home}: X% | {'Нічия: Y% | ' if sport == 'football' else ''}{away}: Z% (сума = 100%)",
  "totals_forecast": "Тотал {cfg['unit']}: Більше {cfg['total_line']} — X% | Менше {cfg['total_line']} — Y%",
  "periods_forecast": "• {cfg['periods'][0]}: Більше {cfg['period_totals'][0]} {cfg['unit']} — X%\\n• {cfg['periods'][1] if len(cfg['periods']) > 1 else cfg['periods'][0]}: Більше {cfg['period_totals'][1] if len(cfg['period_totals']) > 1 else cfg['period_totals'][0]} {cfg['unit']} — X%{chr(10) + '• ' + cfg['periods'][2] + ': Більше ' + str(cfg['period_totals'][2]) + ' ' + cfg['unit'] + ' — X%' if len(cfg['periods']) > 2 else ''}{chr(10) + '• ' + cfg['periods'][3] + ': Більше ' + str(cfg['period_totals'][3]) + ' ' + cfg['unit'] + ' — X%' if len(cfg['periods']) > 3 else ''}",
  "key_factors": "конкретний фактор 1, конкретний фактор 2, конкретний фактор 3"
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
                        "system": "Відповідай ТІЛЬКИ валідним JSON. Ніякого тексту до або після JSON."
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Claude API {resp.status}")
                        return {}
                    data = await resp.json()
                    text = data['content'][0]['text']
                    clean = text.replace('```json', '').replace('```', '').strip()
                    return json.loads(clean)
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return {}

    def _merge_confidence(self, stats_conf: int, ai_conf: int) -> int:
        if ai_conf > 0:
            return max(40, min(95, round(stats_conf * 0.3 + ai_conf * 0.7)))
        return max(40, stats_conf)

    async def get_top_picks(self, limit: int = 5) -> list[dict]:
        matches = await self.scraper.get_today_matches(limit=20)
        predictions = []
        for match in matches[:10]:
            try:
                pred = await self.predict_match(match)
                if pred.get('confidence', 0) >= 58:
                    predictions.append(pred)
            except Exception as e:
                logger.warning(f"Error: {e}")
        predictions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return predictions[:limit]
