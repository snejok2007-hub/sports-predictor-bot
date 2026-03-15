"""
🤖 Sports Predictor
Генерує прогнози на матчі комбінуючи статистику та Claude AI
"""

import asyncio
import aiohttp
import json
import logging
from scraper import FlashscoreScraper
from config import ANTHROPIC_API_KEY, SPORTS_CONFIG

logger = logging.getLogger(__name__)


class SportsPredictor:

    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-20250514"

    SPORT_TOTALS = {
        'football':   {'label': '⚽ Тотал голів',  'low': 2.5,   'unit': 'голів'},
        'basketball': {'label': '🏀 Тотал очок',   'low': 210.5, 'unit': 'очок'},
        'tennis':     {'label': '🎾 Тотал геймів', 'low': 20.5,  'unit': 'геймів'},
        'hockey':     {'label': '🏒 Тотал шайб',   'low': 4.5,   'unit': 'шайб'},
    }

    SPORT_PERIODS = {
        'football':   '1-й тайм / 2-й тайм',
        'basketball': '1-й чверть / 2-й чверть / 3-й чверть / 4-й чверть',
        'tennis':     '1-й сет / 2-й сет / 3-й сет',
        'hockey':     '1-й період / 2-й період / 3-й період',
    }

    def __init__(self):
        self.scraper = FlashscoreScraper()

    async def predict_match(self, match: dict) -> dict:
        stats_result = self._analyze_stats(match)
        ai_result = await self._get_ai_prediction(match)
        final_prediction = self._combine_predictions(stats_result, ai_result, match)

        return {
            **match,
            'prediction': final_prediction['prediction'],
            'confidence': final_prediction['confidence'],
            'stats_prediction': stats_result.get('summary', ''),
            'ai_analysis': ai_result.get('analysis', ''),
            'key_factors': final_prediction.get('key_factors', ''),
        }

    def _analyze_stats(self, match: dict) -> dict:
        sport = match.get('sport', 'football')
        home = match.get('home', 'Господарі')
        away = match.get('away', 'Гості')

        home_form = match.get('home_form', ['W', 'D', 'W', 'D', 'W'])
        away_form = match.get('away_form', ['L', 'W', 'D', 'W', 'L'])

        form_scores = {'W': 3, 'D': 1, 'L': 0}
        home_pts = sum(form_scores.get(r, 0) for r in home_form)
        away_pts = sum(form_scores.get(r, 0) for r in away_form)
        max_pts = len(home_form) * 3

        home_pct = round((home_pts / max_pts) * 100) if max_pts > 0 else 50
        away_pct = round((away_pts / max_pts) * 100) if max_pts > 0 else 50

        home_form_str = ' '.join(['✅' if r == 'W' else '🔲' if r == 'D' else '❌' for r in home_form[-5:]])
        away_form_str = ' '.join(['✅' if r == 'W' else '🔲' if r == 'D' else '❌' for r in away_form[-5:]])

        diff = home_pts - away_pts
        if diff >= 5:
            pred = f"Перемога {home}"
            conf = min(75, 50 + diff * 2)
        elif diff <= -5:
            pred = f"Перемога {away}"
            conf = min(75, 50 + abs(diff) * 2)
        else:
            pred = "Нічия або мінімальна різниця" if sport == 'football' else f"Незначна перевага {home if diff >= 0 else away}"
            conf = 45 if sport == 'football' else 50

        totals_cfg = self.SPORT_TOTALS.get(sport, self.SPORT_TOTALS['football'])
        threshold = totals_cfg['low']
        home_avg = match.get('home_goals_avg', threshold * 0.52)
        away_avg = match.get('away_goals_avg', threshold * 0.48)
        total_avg = home_avg + away_avg
        total_hint = f"\n{totals_cfg['label']}: {'Більше' if total_avg >= threshold else 'Менше'} {threshold} {totals_cfg['unit']}"

        periods = self.SPORT_PERIODS.get(sport, '')
        summary = (
            f"📊 Форма {home}: {home_form_str} ({home_pct}%)\n"
            f"📊 Форма {away}: {away_form_str} ({away_pct}%)"
            f"{total_hint}\n"
            f"🕐 Структура: {periods}"
        )

        return {'prediction': pred, 'confidence': conf, 'summary': summary,
                'home_score': home_pts, 'away_score': away_pts}

    async def _get_ai_prediction(self, match: dict) -> dict:
        if not ANTHROPIC_API_KEY:
            return {'analysis': '⚠️ API ключ не налаштований', 'prediction': '', 'confidence': 0}

        sport = match.get('sport', 'football')
        totals_cfg = self.SPORT_TOTALS.get(sport, self.SPORT_TOTALS['football'])
        periods = self.SPORT_PERIODS.get(sport, '')
        sport_name = SPORTS_CONFIG.get(sport, {}).get('name', sport)
        home = match.get('home', 'Господарі')
        away = match.get('away', 'Гості')
        league = match.get('league', '')
        home_form = match.get('home_form', [])
        away_form = match.get('away_form', [])

        prompt = f"""Проаналізуй матч {sport_name}: {home} vs {away}, ліга: {league}

Форма {home}: {' '.join(home_form) if home_form else 'немає'}
Форма {away}: {' '.join(away_form) if away_form else 'немає'}

Специфіка: структура матчу — {periods}, типовий тотал {totals_cfg['low']} {totals_cfg['unit']}.

Дай детальний прогноз по {periods}.
JSON: {{"prediction": "переможець", "confidence": 0-100, "analysis": "3-4 речення з деталями", "key_factors": "фактори", "periods_forecast": "прогноз по {periods}"}}"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.CLAUDE_URL,
                    headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={
                        "model": self.MODEL,
                        "max_tokens": 800,
                        "messages": [{"role": "user", "content": prompt}],
                        "system": (
                            f"Ти професійний спортивний аналітик. Враховуй специфіку кожного виду спорту. "
                            f"Для баскетболу тотали 200+ очок, для футболу 2.5-3.5 голів, для хокею 4.5-6.5 шайб. "
                            f"Відповідай ТІЛЬКИ JSON без зайвого тексту."
                        )
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        return self._fallback_ai(match)
                    text = data['content'][0]['text']
                    clean = text.replace('```json', '').replace('```', '').strip()
                    return json.loads(clean)
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return self._fallback_ai(match)

    def _combine_predictions(self, stats: dict, ai: dict, match: dict) -> dict:
        stats_conf = stats.get('confidence', 50)
        ai_conf = ai.get('confidence', 50)
        ai_pred = ai.get('prediction', '')

        final_pred = ai_pred if ai_pred else stats.get('prediction', '')
        final_conf = round(stats_conf * 0.35 + ai_conf * 0.65) if ai_pred else stats_conf

        key_factors = ai.get('key_factors', '')
        periods_forecast = ai.get('periods_forecast', '')
        if periods_forecast:
            key_factors += f"\n\n📅 По таймах/чвертях:\n{periods_forecast}"

        if not key_factors:
            diff = stats.get('home_score', 0) - stats.get('away_score', 0)
            home = match.get('home', '')
            away = match.get('away', '')
            key_factors = f"Краща форма {home if diff >= 0 else away}, перевага {'господарів' if diff >= 0 else 'гостей'}"

        return {'prediction': final_pred, 'confidence': max(40, min(95, final_conf)), 'key_factors': key_factors}

    def _fallback_ai(self, match: dict) -> dict:
        home = match.get('home', 'Господарі')
        return {
            'analysis': f'Незначна перевага {home} як господаря. Очікується рівна боротьба.',
            'prediction': f'Незначна перевага {home}',
            'confidence': 55,
            'key_factors': 'Перевага господарів, поточна форма',
            'periods_forecast': 'Рівна гра протягом усього матчу'
        }

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
