# --- Импорт библиотек ---
import telebot
from telebot import types
import json
import uuid
import os
from flask import Flask, request

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = "8497669891:AAHMtQafkZ_6VpbbmN4dQjcXkH-o_et1QwA"
bot = telebot.TeleBot(BOT_TOKEN)

# --- Константы ---
RECIPES_FILE = 'recipes.json'
USER_STATE = {}
STATE_NAME = 1
STATE_CATEGORY = 2
STATE_INGREDIENTS = 3
STATE_VIDEO = 4
STATE_KEYWORDS = 5
FAVORITE_KEY = "is_favorite"
FAVORITE_CATEGORY_NAME = "⭐ Избранное"

CUSTOM_CATEGORY_ORDER = [
    "Завтрак", "Супы", "Основные блюда", "Салат", "Vegan", "Десерты"
]

# --- Работа с JSON ---
def load_recipes():
    if not os.path.exists(RECIPES_FILE):
        print("Файл рецептов не найден, инициализируем пустым словарем.")
        return {}
    try:
        with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"Загружено {len(data)} рецептов из {RECIPES_FILE}.")
            return data
    except Exception as e:
        print(f"Ошибка при загрузке: {e}")
        return {}

def save_recipes(data):
    try:
        with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении: {e}")

RECIPES = load_recipes()

# --- Генерация клавиатур ---
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

# --- Обработчики команд ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    print(f"DEBUG: /start от {message.chat.id}")
    bot.send_message(message.chat.id, "Добро пожаловать в вашу книгу рецептов! Выберите действие:", 
                     reply_markup=generate_main_markup())

# --- Категории ---
@bot.message_handler(func=lambda message: message.text == "📖 Категории")
def show_categories(message):
    if not RECIPES:
        bot.send_message(message.chat.id, "Книга рецептов пуста. Добавьте первый рецепт!")
        return
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())

# --- Поиск ---
@bot.message_handler(func=lambda message: message.text == "🔍 Поиск Рецепта")
def start_search(message):
    bot.send_message(message.chat.id, "Введите слово или фразу для поиска:")
    bot.register_next_step_handler(message, process_search_query)

def process_search_query(message):
    query = message.text.lower()
    found_recipes = {}
    for rid, recipe in RECIPES.items():
        text = f"{recipe['title']} {recipe['category']} {recipe['ingredients']} {recipe.get('keywords','')}".lower()
        if query in text:
            found_recipes[rid] = recipe
    if found_recipes:
        text = f"Найдено {len(found_recipes)} рецепт(ов):\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for rid, recipe in found_recipes.items():
            text += f"▪️ {recipe['title']}\n"
            markup.add(types.InlineKeyboardButton(recipe['title'], callback_data=f"show_{rid}"))
        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f"По запросу '{message.text}' ничего не найдено.")

# --- Добавление рецепта ---
@bot.message_handler(func=lambda message: message.text == "➕ Добавить Рецепт")
def start_add_recipe(message):
    chat_id = message.chat.id
    USER_STATE[chat_id] = {"state": STATE_NAME, "temp_recipe": {}}
    bot.send_message(chat_id, "Шаг 1/5: Введите название рецепта:")
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE: return
    USER_STATE[chat_id]['temp_recipe']['title'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_CATEGORY
    categories = sorted(list(set(r['category'] for r in RECIPES.values())))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if categories: markup.add(*categories)
    bot.send_message(chat_id, "Шаг 2/5: Введите или выберите категорию:", reply_markup=markup)
    bot.register_next_step_handler(message, process_category)

def process_category(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE: return
    USER_STATE[chat_id]['temp_recipe']['category'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_INGREDIENTS
    bot.send_message(chat_id, "Шаг 3/5: Введите список ингредиентов:", reply_markup=generate_main_markup())
    bot.register_next_step_handler(message, process_ingredients)

def process_ingredients(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE: return
    USER_STATE[chat_id]['temp_recipe']['ingredients'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_VIDEO
    bot.send_message(chat_id, "Шаг 4/5: Отправьте видео или ссылку:")
    bot.register_next_step_handler(message, process_video)

def process_video(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE: return
    video_info = None
    if message.video:
        video_info = message.video.file_id
        USER_STATE[chat_id]['temp_recipe']['video_type'] = 'file'
    elif message.text:
        video_info = message.text.strip()
        USER_STATE[chat_id]['temp_recipe']['video_type'] = 'link'
    else:
        bot.send_message(chat_id, "Ошибка: отправьте видео или ссылку.")
        bot.register_next_step_handler(message, process_video)
        return
    USER_STATE[chat_id]['temp_recipe']['video'] = video_info
    USER_STATE[chat_id]['temp_recipe'][FAVORITE_KEY] = False
    USER_STATE[chat_id]['state'] = STATE_KEYWORDS
    bot.send_message(chat_id, "Шаг 5/5: Введите ключевые слова через запятую:")
    bot.register_next_step_handler(message, finish_recipe_add)

def finish_recipe_add(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE: return
    temp_recipe = USER_STATE[chat_id]['temp_recipe']
    temp_recipe['keywords'] = message.text.strip().lower()
    rid = str(uuid.uuid4())
    RECIPES[rid] = temp_recipe
    save_recipes(RECIPES)
    del USER_STATE[chat_id]
    bot.send_message(chat_id, f"🎉 Рецепт '{temp_recipe['title']}' добавлен!", reply_markup=generate_main_markup())

# --- Callbacks для категорий и рецептов ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category_selection(call):
    bot.answer_callback_query(call.id)
    cat = call.data.split('_')[1]
    filtered = {}
    if cat == 'all': filtered = RECIPES
    elif cat == 'favorite': filtered = {rid: r for rid, r in RECIPES.items() if r.get(FAVORITE_KEY)}
    else: filtered = {rid: r for rid, r in RECIPES.items() if r['category'] == cat}
    if not filtered:
       
