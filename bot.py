#!/usr/bin/env python3
"""🏆 Sports Predictor Telegram Bot"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from scraper import FlashscoreScraper
from predictor import SportsPredictor
from config import TELEGRAM_TOKEN, SPORTS_CONFIG

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ОДИН спільний скрапер для бота і предиктора
scraper = FlashscoreScraper()
predictor = SportsPredictor(scraper)  # Передаємо той самий скрапер


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏆 *Sports Predictor Bot*\n\n"
        "Аналізую матчі та генерую прогнози:\n"
        "📊 Статистика форми команд\n"
        "🤖 AI-аналіз (Claude)\n"
        "📅 Прогноз по таймах/чвертях\n\n"
        "Оберіть вид спорту:"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=_build_sport_keyboard())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Команди:*\n\n"
        "/start — головне меню\n"
        "/today — всі матчі сьогодні\n"
        "/football — футбол\n"
        "/basketball — баскетбол\n"
        "/tennis — теніс\n"
        "/top — топ прогнози дня\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def today_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Завантажую матчі...")
    matches = await scraper.get_today_matches()
    if not matches:
        await msg.edit_text("😔 Матчів не знайдено")
        return
    keyboard = _build_matches_keyboard(matches[:15])
    await msg.edit_text(f"📅 *Матчі сьогодні* ({len(matches)})\nОберіть матч:", parse_mode='Markdown', reply_markup=keyboard)


async def football_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_sport(update, 'football')

async def basketball_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_sport(update, 'basketball')

async def tennis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_sport(update, 'tennis')

async def _show_sport(update: Update, sport: str):
    emoji = SPORTS_CONFIG[sport]['emoji']
    name = SPORTS_CONFIG[sport]['name']
    msg = await update.message.reply_text(f"⏳ Завантажую {emoji} матчі...")
    matches = await scraper.get_matches_by_sport(sport)
    if not matches:
        await msg.edit_text(f"😔 {emoji} Матчів не знайдено")
        return
    keyboard = _build_matches_keyboard(matches[:12])
    await msg.edit_text(f"{emoji} *{name}*\nОберіть матч для прогнозу:", parse_mode='Markdown', reply_markup=keyboard)


async def top_picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔮 Генерую топ прогнози...")
    picks = await predictor.get_top_picks(limit=5)
    if not picks:
        await msg.edit_text("😔 Не вдалося згенерувати прогнози")
        return
    text = "🏆 *Топ прогнози дня:*\n\n"
    for i, pick in enumerate(picks, 1):
        conf = pick.get('confidence', 0)
        text += (
            f"{i}. {pick['sport_emoji']} *{pick['home']} vs {pick['away']}*\n"
            f"   🎯 {pick['prediction']}\n"
            f"   {_confidence_bar(conf)} {conf}%\n"
            f"   🕐 {pick['time']}\n\n"
        )
    await msg.edit_text(text, parse_mode='Markdown')


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("sport_"):
        sport = data.replace("sport_", "")
        if sport == 'all':
            matches = await scraper.get_today_matches()
        else:
            matches = await scraper.get_matches_by_sport(sport)

        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '🏆')
        name = SPORTS_CONFIG.get(sport, {}).get('name', sport)

        if not matches:
            await query.edit_message_text(f"😔 Матчів не знайдено")
            return
        keyboard = _build_matches_keyboard(matches[:12])
        await query.edit_message_text(
            f"{emoji} *{name}* — оберіть матч:",
            parse_mode='Markdown', reply_markup=keyboard
        )

    elif data.startswith("match_"):
        match_id = data.replace("match_", "")
        await query.edit_message_text("🔮 Генерую детальний прогноз... (15-30 сек)")

        match_data = await scraper.get_match_details(match_id)
        prediction = await predictor.predict_match(match_data)

        text = _format_prediction(prediction)
        sport = match_data.get('sport', 'football')
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data=f"sport_{sport}")
        ]])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    elif data == "menu":
        await query.edit_message_text(
            "🏆 *Sports Predictor Bot*\nОберіть вид спорту:",
            parse_mode='Markdown', reply_markup=_build_sport_keyboard()
        )


def _build_sport_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚽ Футбол", callback_data="sport_football"),
         InlineKeyboardButton("🏀 Баскетбол", callback_data="sport_basketball")],
        [InlineKeyboardButton("🎾 Теніс", callback_data="sport_tennis"),
         InlineKeyboardButton("🏒 Хокей", callback_data="sport_hockey")],
        [InlineKeyboardButton("📅 Всі матчі сьогодні", callback_data="sport_all")],
    ])


def _build_matches_keyboard(matches: list):
    buttons = []
    for match in matches:
        label = f"{match['home']} vs {match['away']} • {match['time']}"
        if len(label) > 60:
            label = label[:57] + "..."
        buttons.append([InlineKeyboardButton(label, callback_data=f"match_{match['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Меню", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def _format_prediction(pred: dict) -> str:
    conf = pred.get('confidence', 0)
    home = pred.get('home', '?')
    away = pred.get('away', '?')

    text = (
        f"{pred.get('sport_emoji','🏆')} *{home} vs {away}*\n"
        f"🏆 {pred.get('league','')}\n"
        f"🕐 {pred.get('time','')}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎯 *ПРОГНОЗ: {pred['prediction']}*\n"
        f"📈 Впевненість: {_confidence_bar(conf)} *{conf}%*\n\n"
    )

    if pred.get('win_probs'):
        text += f"📊 *Імовірності:*\n{pred['win_probs']}\n\n"

    if pred.get('stats_prediction'):
        text += f"📋 *Статистика:*\n{pred['stats_prediction']}\n\n"

    if pred.get('totals_forecast'):
        text += f"🎰 *Тотали:*\n{pred['totals_forecast']}\n\n"

    if pred.get('periods_forecast'):
        text += f"📅 *По таймах/чвертях:*\n{pred['periods_forecast']}\n\n"

    if pred.get('key_factors'):
        text += f"🔑 *Ключові фактори:*\n{pred['key_factors']}\n\n"

    text += "⚠️ _Прогноз носить інформаційний характер_"
    return text


def _confidence_bar(confidence: int) -> str:
    filled = round(confidence / 10)
    return "🟩" * filled + "⬜" * (10 - filled)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today_matches))
    app.add_handler(CommandHandler("football", football_cmd))
    app.add_handler(CommandHandler("basketball", basketball_cmd))
    app.add_handler(CommandHandler("tennis", tennis_cmd))
    app.add_handler(CommandHandler("top", top_picks))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("🚀 Бот запущено!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
