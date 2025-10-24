import os
from flask import Flask, request
import telebot

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def index():
    return 'OK', 200

WEBHOOK_PATH = f'/{BOT_TOKEN}'
@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        print(f"== Получен апдейт от Telegram: {json_string}")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Content-Type Error', 403

RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
if RENDER_URL:
    WEBHOOK_URL = RENDER_URL + WEBHOOK_PATH
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook установлен: {WEBHOOK_URL}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    print("=== ОБРАБОТЧИК /start ===")
    bot.send_message(message.chat.id, "Test! Ответ бота.")
