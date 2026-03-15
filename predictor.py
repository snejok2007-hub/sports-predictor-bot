"""
🤖 Sports Predictor
Генерує прогнози на матчі комбінуючи статистику та Claude AI
"""

import asyncio
import aiohttp
import json
import logging
from typing import Optional
from scraper import FlashscoreScraper
from config import ANTHROPIC_API_KEY, SPORTS_CONFIG

logger = logging.getLogger(__name__)


class SportsPredictor:
    """Генератор прогнозів на спортивні матчі"""

    CLAUDE_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-20250514"

    def __init__(self):
        self.scraper = FlashscoreScraper()

    async def predict_match(self, match: dict) -> dict:
        """
        Генерує повний прогноз на матч:
        1. Статистичний аналіз
        2. AI-аналіз через Claude
        3. Об'єднаний прогноз
        """
        sport = match.get('sport', 'football')

        # 1. Статистичний прогноз
        stats_result = self._analyze_stats(match)

        # 2. AI прогноз через Claude
        ai_result = await self._get_ai_prediction(match)

        # 3. Об'єднуємо
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
        """Статистичний аналіз на основі форми та H2H"""
        sport = match.get('sport', 'football')
        home = match.get('home', 'Господарі')
        away = match.get('away', 'Гості')

        home_form = match.get('home_form', ['W', 'D', 'W', 'D', 'W'])
        away_form = match.get('away_form', ['L', 'W', 'D', 'W', 'L'])

        # Рахуємо бали форми (W=3, D=1, L=0)
        form_scores = {'W': 3, 'D': 1, 'L': 0}
        home_pts = sum(form_scores.get(r, 0) for r in home_form)
        away_pts = sum(form_scores.get(r, 0) for r in away_form)
        max_pts = len(home_form) * 3

        home_pct = round((home_pts / max_pts) * 100) if max_pts > 0 else 50
        away_pct = round((away_pts / max_pts) * 100) if max_pts > 0 else 50

        # Форма у вигляді рядка
        home_form_str = ' '.join(['✅' if r == 'W' else '🔲' if r == 'D' else '❌' for r in home_form[-5:]])
        away_form_str = ' '.join(['✅' if r == 'W' else '🔲' if r == 'D' else '❌' for r in away_form[-5:]])

        # Базовий прогноз
        diff = home_pts - away_pts
        if diff >= 5:
            pred = f"Перемога {home}"
            conf = min(75, 50 + diff * 2)
        elif diff <= -5:
            pred = f"Перемога {away}"
            conf = min(75, 50 + abs(diff) * 2)
        else:
            if sport == 'football':
                pred = "Нічия або мінімальна різниця"
                conf = 45
            else:
                pred = f"Незначна перевага {home if diff >= 0 else away}"
                conf = 50

        # Голи/очки (тільки для футболу)
        goals_hint = ''
        if sport == 'football':
            home_avg = match.get('home_goals_avg', 1.5)
            away_avg = match.get('away_goals_avg', 1.2)
            total_avg = home_avg + away_avg
            goals_hint = f"\n⚽ Очікуваний тотал: {'Більше 2.5' if total_avg >= 2.5 else 'Менше 2.5'}"

        summary = (
            f"📊 Форма {home}: {home_form_str} ({home_pct}%)\n"
            f"📊 Форма {away}: {away_form_str} ({away_pct}%)"
            f"{goals_hint}"
        )

        return {
            'prediction': pred,
            'confidence': conf,
            'summary': summary,
            'home_score': home_pts,
            'away_score': away_pts,
        }

    async def _get_ai_prediction(self, match: dict) -> dict:
        """Отримати AI-прогноз від Claude"""
        if not ANTHROPIC_API_KEY:
            return {'analysis': '⚠️ API ключ не налаштований', 'prediction': '', 'confidence': 0}

        prompt = self._build_prompt(match)

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
                        "max_tokens": 600,
                        "messages": [{"role": "user", "content": prompt}],
                        "system": (
                            "Ти спортивний аналітик. Аналізуй матчі коротко та чітко. "
                            "Відповідай ТІЛЬКИ у форматі JSON: "
                            '{"prediction": "...", "confidence": 70, '
                            '"analysis": "...", "key_factors": "..."}'
                        )
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()

                    if resp.status != 200:
                        logger.error(f"Claude API error: {data}")
                        return self._fallback_ai(match)

                    text = data['content'][0]['text']
                    # Парсимо JSON
                    try:
                        # Видаляємо markdown якщо є
                        clean = text.replace('```json', '').replace('```', '').strip()
                        result = json.loads(clean)
                        return result
                    except json.JSONDecodeError:
                        return {'analysis': text, 'prediction': '', 'confidence': 60}

        except asyncio.TimeoutError:
            logger.warning("Claude API timeout")
            return self._fallback_ai(match)
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return self._fallback_ai(match)

    def _build_prompt(self, match: dict) -> str:
        """Побудувати промпт для Claude"""
        home = match.get('home', 'Господарі')
        away = match.get('away', 'Гості')
        league = match.get('league', '')
        sport = match.get('sport', 'football')
        home_form = match.get('home_form', [])
        away_form = match.get('away_form', [])
        h2h = match.get('h2h', [])

        sport_name = SPORTS_CONFIG.get(sport, {}).get('name', sport)

        prompt = f"""
Проаналізуй матч {sport_name}:

🏟 {home} vs {away}
🏆 Ліга: {league}

📊 Форма (останні 5 матчів):
- {home}: {' '.join(home_form) if home_form else 'немає даних'}
- {away}: {' '.join(away_form) if away_form else 'немає даних'}

H2H останніх 3 зустрічей: {h2h if h2h else 'немає даних'}

Дай прогноз враховуючи:
1. Форму команд
2. Перевагу господарів
3. Загальну якість гравців ліги

Відповідай JSON: {{"prediction": "X перемагає/Нічия", "confidence": 0-100, "analysis": "2-3 речення аналізу", "key_factors": "ключові фактори через кому"}}
"""
        return prompt

    def _combine_predictions(self, stats: dict, ai: dict, match: dict) -> dict:
        """Об'єднати статистичний та AI прогнози"""
        stats_conf = stats.get('confidence', 50)
        ai_conf = ai.get('confidence', 50)
        stats_pred = stats.get('prediction', '')
        ai_pred = ai.get('prediction', '')

        # Зважуємо: 40% статистика + 60% AI
        if ai_pred:
            # Беремо AI прогноз як основний
            final_pred = ai_pred
            final_conf = round(stats_conf * 0.35 + ai_conf * 0.65)
        else:
            final_pred = stats_pred
            final_conf = stats_conf

        key_factors = ai.get('key_factors', '')
        if not key_factors:
            home = match.get('home', '')
            away = match.get('away', '')
            diff = stats.get('home_score', 0) - stats.get('away_score', 0)
            if diff > 0:
                key_factors = f"Краща форма {home}, перевага господарів поля"
            elif diff < 0:
                key_factors = f"Краща форма {away}, гарна виїзна статистика"
            else:
                key_factors = "Рівні команди, важко передбачити"

        return {
            'prediction': final_pred,
            'confidence': max(40, min(95, final_conf)),
            'key_factors': key_factors,
        }

    def _fallback_ai(self, match: dict) -> dict:
        """Резервний варіант якщо Claude недоступний"""
        home = match.get('home', 'Господарі')
        return {
            'analysis': f'Статистичний аналіз вказує на незначну перевагу {home} як господаря поля.',
            'prediction': f'Незначна перевага {home}',
            'confidence': 55,
            'key_factors': 'Перевага господарів, поточна форма'
        }

    async def get_top_picks(self, limit: int = 5) -> list[dict]:
        """Отримати топ прогнози дня"""
        matches = await self.scraper.get_today_matches(limit=20)
        predictions = []

        for match in matches[:10]:  # Аналізуємо перші 10
            try:
                pred = await self.predict_match(match)
                if pred.get('confidence', 0) >= 60:
                    predictions.append(pred)
            except Exception as e:
                logger.warning(f"Prediction error: {e}")

        # Сортуємо по впевненості
        predictions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return predictions[:limit]
