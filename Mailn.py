import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8116429501:AAFTKf72NJWuosxVYzv7-b1PZ70BrufovE0"
CHAT_ID = int(os.getenv("CHAT_ID", "-1002086936856"))
THREAD_ID = int(os.getenv("THREAD_ID", "254"))
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "0.2"))
SYMBOL = "BTCUSDT"
INTERVAL = "3m"
API_URL = "https://data-api.binance.vision/api/v3/klines"

# Глобальное состояние для отслеживания
last_alert_sent = False
last_message_id = None

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_klines():
    try:
        response = requests.get(API_URL, params={"symbol": SYMBOL, "interval": INTERVAL, "limit": 5})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка API: {e}")
        return None

def calculate_volatility(candle):
    try:
        high = float(candle[2])
        low = float(candle[3])
        return ((high - low) / low) * 100
    except:
        return None

async def volatility_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    klines = get_klines()
    if not klines:
        await update.message.reply_text("Ошибка получения данных с Binance.")
        return

    report = ["<b>Анализ волатильности BTC/USDT (3m)</b>", "<pre>",
              "| Свеча | High    | Low     | Волатильность |", "-"*40]

    vols = []
    for i, candle in enumerate(klines[-3:], 1):
        vol = calculate_volatility(candle)
        if vol is None:
            continue
        vols.append(vol)
        report.append(f"| {i:^5} | {float(candle[2]):<7.2f} | {float(candle[3]):<7.2f} | {vol:<12.2f}% |")

    report.append("</pre>")
    avg = sum(vols) / len(vols) if vols else 0
    report.append(f"📈 <b>Средняя волатильность:</b> {avg:.2f}%")

    await update.message.reply_text("
".join(report), parse_mode="HTML")

async def check_volatility(app):
    global last_alert_sent, last_message_id
    klines = get_klines()
    if not klines or len(klines) < 3:
        return

    vols = [calculate_volatility(c) for c in klines[-3:]]
    vols = [v for v in vols if v is not None]
    if not vols:
        return
    avg = sum(vols) / len(vols)

    if avg >= ALERT_THRESHOLD:
        if not last_alert_sent:
            msg = await app.bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=THREAD_ID,
                text=f"⚠️ <b>Порог волатильности превышен!</b>
Средняя за 3 свечи: {avg:.2f}%",
                parse_mode="HTML"
            )
            try:
                await app.bot.pin_chat_message(chat_id=CHAT_ID, message_id=msg.message_id, disable_notification=True)
                if last_message_id:
                    await app.bot.unpin_chat_message(chat_id=CHAT_ID, message_id=last_message_id)
                last_message_id = msg.message_id
            except Exception as e:
                logger.warning(f"Не удалось закрепить сообщение: {e}")
            last_alert_sent = True
    else:
        last_alert_sent = False

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("volatility", volatility_command))
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.create_task(check_volatility(app)), "interval", seconds=180)
    scheduler.start()
    app.run_polling()

if __name__ == "__main__":
    main()
