# Импорт необходимых библиотек
import telebot
from telebot import types
import json
import uuid
import os
from flask import Flask, request

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = "8497669891:AAHMtQafkZ_6VpbbmN4dQjcXkH-o_et1QwA" 
bot = telebot.TeleBot(BOT_TOKEN)

# Константы
RECIPES_FILE = 'recipes.json'
USER_STATE = {}
STATE_NAME = 1
STATE_CATEGORY = 2
STATE_INGREDIENTS = 3
STATE_VIDEO = 4
STATE_KEYWORDS = 5
FAVORITE_KEY = "is_favorite"
FAVORITE_CATEGORY_NAME = "⭐ Избранное"
CUSTOM_CATEGORY_ORDER = ["Завтрак", "Супы", "Основные блюда", "Салат", "Vegan", "Десерты"]

# --- ФУНКЦИИ РАБОТЫ С JSON ---
def load_recipes():
    if not os.path.exists(RECIPES_FILE):
        return {}
    try:
        with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_recipes(recipes_data):
    with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
        json.dump(recipes_data, f, ensure_ascii=False, indent=4)

RECIPES = load_recipes()

# --- ГЕНЕРАЦИЯ КЛАВИАТУР ---
def generate_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📖 Категории", "🔍 Поиск Рецепта")
    markup.add("➕ Добавить Рецепт")
    return markup

def generate_categories_markup():
    existing_categories = set(r['category'] for r in RECIPES.values())
    markup = types.InlineKeyboardMarkup(row_width=2)
    if any(r.get(FAVORITE_KEY) for r in RECIPES.values()):
        markup.add(types.InlineKeyboardButton(FAVORITE_CATEGORY_NAME, callback_data="cat_favorite"))
    for cat in CUSTOM_CATEGORY_ORDER:
        if cat in existing_categories:
            markup.add(types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    if RECIPES:
        markup.add(types.InlineKeyboardButton("Все рецепты", callback_data="cat_all"))
    return markup

def generate_recipe_actions_markup(recipe_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    recipe = RECIPES.get(recipe_id, {})
    is_fav = recipe.get(FAVORITE_KEY, False)
    fav_text = "⭐ Убрать из избранного" if is_fav else "⭐ Добавить в избранное"
    markup.add(types.InlineKeyboardButton(fav_text, callback_data=f"toggle_fav_{recipe_id}"))
    markup.add(types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{recipe_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ К категориям", callback_data="back_to_cats"))
    return markup

# --- НАСТРОЙКА WEBHOOK ---
app = Flask(__name__)
WEBHOOK_PATH = f'/{BOT_TOKEN}'

@app.route('/', methods=['GET'])
def index():
    return 'Recipe Telegram Bot is running.', 200

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return '', 200
        except Exception as e:
            print(f"Ошибка при обработке обновления: {e}")
            return 'Processing Error', 200
    return 'Content-Type Error', 403

# --- УСТАНОВКА WEBHOOK (Только для Render) ---
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
if RENDER_URL:
    WEBHOOK_URL = RENDER_URL + WEBHOOK_PATH
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Автоматический Webhook установлен на: {WEBHOOK_URL}")
    except Exception as e:
        print(f"Ошибка при автоматической установке Webhook: {e}")

# --- ОБРАБОТЧИК ДЛЯ ЛОГОВ И ДИАГНОСТИКИ ---
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video'])
def echo_all(message):
    print(f"DEBUG: Получено сообщение от {message.chat.id}: {message.text[:20] if message.text else 'Медиа'}")
