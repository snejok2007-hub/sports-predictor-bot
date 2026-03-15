#!/usr/bin/env python3
"""
🏆 Sports Predictor Telegram Bot
Отримує матчі з Flashscore та генерує AI-прогнози через Claude
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from predictor import SportsPredictor
from scraper import FlashscoreScraper
from config import TELEGRAM_TOKEN, SPORTS_CONFIG

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

scraper = FlashscoreScraper()
predictor = SportsPredictor()


# ─── КОМАНДИ ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Привітальне повідомлення"""
    text = (
        "🏆 *Sports Predictor Bot*\n\n"
        "Я аналізую матчі та генерую прогнози на основі:\n"
        "📊 Статистики та форми команд\n"
        "🤖 AI-аналізу (Claude)\n\n"
        "Оберіть вид спорту:"
    )
    keyboard = _build_sport_keyboard()
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Команди бота:*\n\n"
        "/start — головне меню\n"
        "/today — матчі на сьогодні\n"
        "/football — футбольні прогнози\n"
        "/basketball — баскетбольні прогнози\n"
        "/tennis — тенісні прогнози\n"
        "/top — топ прогнози дня\n"
        "/help — ця довідка\n\n"
        "💡 Натисніть на матч щоб отримати детальний прогноз"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def today_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Всі матчі на сьогодні"""
    msg = await update.message.reply_text("⏳ Завантажую матчі...")
    matches = await scraper.get_today_matches()

    if not matches:
        await msg.edit_text("😔 На сьогодні матчів не знайдено")
        return

    keyboard = _build_matches_keyboard(matches[:15])
    count = len(matches)
    await msg.edit_text(
        f"📅 *Матчі на сьогодні* ({count} матчів)\nОберіть матч для прогнозу:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def sport_command(update: Update, context: ContextTypes.DEFAULT_TYPE, sport: str):
    """Матчі за видом спорту"""
    emoji = SPORTS_CONFIG[sport]['emoji']
    msg = await update.message.reply_text(f"⏳ Завантажую {emoji} матчі...")
    matches = await scraper.get_matches_by_sport(sport)

    if not matches:
        await msg.edit_text(f"😔 {emoji} Матчів не знайдено")
        return

    keyboard = _build_matches_keyboard(matches[:12])
    await msg.edit_text(
        f"{emoji} *{SPORTS_CONFIG[sport]['name']}* — матчі сьогодні\nОберіть для прогнозу:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def football_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sport_command(update, context, 'football')

async def basketball_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sport_command(update, context, 'basketball')

async def tennis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await sport_command(update, context, 'tennis')


async def top_picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ прогнози дня (найвища впевненість)"""
    msg = await update.message.reply_text("🔮 Генерую топ прогнози дня...")
    picks = await predictor.get_top_picks(limit=5)

    if not picks:
        await msg.edit_text("😔 Не вдалося згенерувати прогнози")
        return

    text = "🏆 *Топ прогнози дня:*\n\n"
    for i, pick in enumerate(picks, 1):
        conf = pick.get('confidence', 0)
        conf_bar = _confidence_bar(conf)
        text += (
            f"{i}. {pick['sport_emoji']} *{pick['home']} vs {pick['away']}*\n"
            f"   🎯 Прогноз: *{pick['prediction']}*\n"
            f"   {conf_bar} {conf}%\n"
            f"   🕐 {pick['time']}\n\n"
        )

    await msg.edit_text(text, parse_mode='Markdown')


# ─── CALLBACK ──────────────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("sport_"):
        sport = data.replace("sport_", "")
        matches = await scraper.get_matches_by_sport(sport)
        emoji = SPORTS_CONFIG.get(sport, {}).get('emoji', '⚽')
        name = SPORTS_CONFIG.get(sport, {}).get('name', sport)

        if not matches:
            await query.edit_message_text(f"😔 {emoji} Матчів не знайдено")
            return

        keyboard = _build_matches_keyboard(matches[:12])
        await query.edit_message_text(
            f"{emoji} *{name}* — оберіть матч:",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    elif data.startswith("match_"):
        match_id = data.replace("match_", "")
        await query.edit_message_text("🔮 Генерую прогноз... (15-30 сек)")

        match_data = await scraper.get_match_details(match_id)
        prediction = await predictor.predict_match(match_data)

        text = _format_prediction(prediction)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад до матчів", callback_data=f"sport_{match_data.get('sport', 'football')}")]
        ])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    elif data == "menu":
        await query.edit_message_text(
            "🏆 *Sports Predictor Bot*\nОберіть вид спорту:",
            parse_mode='Markdown',
            reply_markup=_build_sport_keyboard()
        )


# ─── ХЕЛПЕРИ ───────────────────────────────────────────────────────────────────

def _build_sport_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚽ Футбол", callback_data="sport_football"),
            InlineKeyboardButton("🏀 Баскетбол", callback_data="sport_basketball"),
        ],
        [
            InlineKeyboardButton("🎾 Теніс", callback_data="sport_tennis"),
            InlineKeyboardButton("🏒 Хокей", callback_data="sport_hockey"),
        ],
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
    conf_bar = _confidence_bar(conf)

    text = (
        f"{pred.get('sport_emoji','🏆')} *{pred['home']} vs {pred['away']}*\n"
        f"🏆 {pred.get('league','')}\n"
        f"🕐 {pred.get('time','')}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎯 *ПРОГНОЗ: {pred['prediction']}*\n"
        f"📈 Впевненість: {conf_bar} *{conf}%*\n\n"
    )

    if pred.get('stats_prediction'):
        text += (
            f"📊 *Статистичний прогноз:*\n"
            f"{pred['stats_prediction']}\n\n"
        )

    if pred.get('ai_analysis'):
        text += (
            f"🤖 *AI-аналіз:*\n"
            f"{pred['ai_analysis']}\n\n"
        )

    if pred.get('key_factors'):
        text += f"🔑 *Ключові фактори:*\n{pred['key_factors']}\n\n"

    text += f"⚠️ _Прогноз носить інформаційний характер_"
    return text


def _confidence_bar(confidence: int) -> str:
    filled = round(confidence / 10)
    return "🟩" * filled + "⬜" * (10 - filled)


# ─── ЗАПУСК ────────────────────────────────────────────────────────────────────

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
