# 🏆 Sports Predictor Telegram Bot

Telegram-бот для прогнозів на спортивні матчі з інтеграцією Flashscore та Claude AI.

## 🚀 Швидкий старт

### 1. Встановити залежності
```bash
pip install -r requirements.txt
```

### 2. Отримати API ключі

**Telegram Bot Token:**
1. Відкрийте [@BotFather](https://t.me/BotFather) у Telegram
2. Напишіть `/newbot`
3. Скопіюйте токен

**Anthropic API Key:**
1. Зареєструйтесь на [console.anthropic.com](https://console.anthropic.com)
2. Створіть API ключ у Settings → API Keys

### 3. Налаштувати ключі

**Варіант А — через змінні середовища (рекомендовано):**
```bash
export TELEGRAM_TOKEN="your_token_here"
export ANTHROPIC_API_KEY="your_key_here"
```

**Варіант Б — напряму в config.py:**
```python
TELEGRAM_TOKEN = "your_token_here"
ANTHROPIC_API_KEY = "your_key_here"
```

### 4. Запустити бота
```bash
python bot.py
```

---

## 📁 Структура проєкту

```
sports_predictor_bot/
├── bot.py          — Telegram бот (команди, кнопки)
├── scraper.py      — Flashscore скрапер
├── predictor.py    — Генератор прогнозів (статистика + AI)
├── config.py       — Конфігурація та API ключі
└── requirements.txt
```

---

## 🤖 Команди бота

| Команда | Опис |
|---------|------|
| `/start` | Головне меню |
| `/today` | Всі матчі на сьогодні |
| `/football` | Футбольні матчі |
| `/basketball` | Баскетбол |
| `/tennis` | Теніс |
| `/top` | Топ прогнози дня |
| `/help` | Довідка |

---

## ⚙️ Як працює прогноз

1. **Статистичний модуль** — аналізує форму команд (останні 5 матчів), H2H, середню кількість голів. Дає базову впевненість 40-75%.

2. **Claude AI** — отримує всі дані матчу та генерує глибокий аналіз з поясненням ключових факторів. Впевненість AI: 0-95%.

3. **Об'єднаний результат** — фінальний прогноз зважує: 35% статистика + 65% AI.

---

## 📡 Джерела даних

### Безкоштовно:
- **Flashscore** (через скрапінг) — матчі в реальному часі
- **API-Football** (100 запитів/день безкоштовно) — детальна статистика

### Платно (надійніше):
- **Apify Flashscore Scraper** — готовий REST API
- **Sportradar / Opta** — професійні спортивні дані

---

## 🔧 Розширення

### Додати API-Football (більше статистики):
```python
# config.py
API_FOOTBALL_KEY = "your_key"  # https://www.api-football.com/
```

### Запустити на сервері (systemd):
```ini
[Unit]
Description=Sports Predictor Bot
After=network.target

[Service]
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 bot.py
Environment=TELEGRAM_TOKEN=xxx
Environment=ANTHROPIC_API_KEY=xxx
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## ⚠️ Відмова від відповідальності
Прогнози носять виключно інформаційний характер. Не є закликом до ставок.
