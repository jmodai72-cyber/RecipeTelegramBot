# app.py
import os
import json
import uuid
from flask import Flask, request
import telebot
from telebot import types

# --- Конфигурация бота ---
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
CUSTOM_CATEGORY_ORDER = ["Завтрак", "Супы", "Основные блюда", "Салат", "Vegan", "Десерты"]

# --- Работа с JSON ---
def load_recipes():
    if not os.path.exists(RECIPES_FILE):
        return {}
    try:
        with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
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
    existing = set(r['category'] for r in RECIPES.values())
    markup = types.InlineKeyboardMarkup(row_width=2)
    if any(r.get(FAVORITE_KEY) for r in RECIPES.values()):
        markup.add(types.InlineKeyboardButton(FAVORITE_CATEGORY_NAME, callback_data="cat_favorite"))
    for cat in CUSTOM_CATEGORY_ORDER:
        if cat in existing:
            markup.add(types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    if RECIPES:
        markup.add(types.InlineKeyboardButton("Все рецепты", callback_data="cat_all"))
    return markup

def generate_recipe_actions_markup(rid):
    markup = types.InlineKeyboardMarkup(row_width=2)
    recipe = RECIPES.get(rid, {})
    fav_text = "⭐ Убрать из избранного" if recipe.get(FAVORITE_KEY) else "⭐ Добавить в избранное"
    markup.add(types.InlineKeyboardButton(fav_text, callback_data=f"toggle_fav_{rid}"))
    markup.add(types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{rid}"))
    markup.add(types.InlineKeyboardButton("⬅️ К категориям", callback_data="back_to_cats"))
    return markup

# --- Команды ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Добро пожаловать! Выберите действие:", reply_markup=generate_main_markup())

# --- Категории ---
@bot.message_handler(func=lambda m: m.text == "📖 Категории")
def show_categories(message):
    if not RECIPES:
        bot.send_message(message.chat.id, "Книга рецептов пуста!")
        return
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())

# --- Поиск ---
@bot.message_handler(func=lambda m: m.text == "🔍 Поиск Рецепта")
def start_search(message):
    bot.send_message(message.chat.id, "Введите слово или фразу для поиска:")
    bot.register_next_step_handler(message, process_search_query)

def process_search_query(message):
    query = message.text.lower()
    found = {}
    for rid, r in RECIPES.items():
        text = f"{r['title']} {r['category']} {r['ingredients']} {r.get('keywords','')}".lower()
        if query in text:
            found[rid] = r
    if not found:
        bot.send_message(message.chat.id, f"По запросу '{message.text}' ничего не найдено.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    text_msg = f"Найдено {len(found)} рецептов:\n"
    for rid, r in found.items():
        text_msg += f"▪️ {r['title']}\n"
        markup.add(types.InlineKeyboardButton(r['title'], callback_data=f"show_{rid}"))
    bot.send_message(message.chat.id, text_msg, reply_markup=markup)

# --- Добавление рецепта ---
@bot.message_handler(func=lambda m: m.text == "➕ Добавить Рецепт")
def start_add_recipe(message):
    USER_STATE[message.chat.id] = {"state": STATE_NAME, "temp_recipe": {}}
    bot.send_message(message.chat.id, "Шаг 1/5: Введите название рецепта:")
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    chat_id = message.chat.id
    USER_STATE[chat_id]['temp_recipe']['title'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_CATEGORY
    categories = sorted(list(set(r['category'] for r in RECIPES.values())))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if categories:
        markup.add(*categories)
    bot.send_message(chat_id, "Шаг 2/5: Введите или выберите категорию:", reply_markup=markup)
    bot.register_next_step_handler(message, process_category)

def process_category(message):
    chat_id = message.chat.id
    USER_STATE[chat_id]['temp_recipe']['category'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_INGREDIENTS
    bot.send_message(chat_id, "Шаг 3/5: Введите список ингредиентов:", reply_markup=generate_main_markup())
    bot.register_next_step_handler(message, process_ingredients)

def process_ingredients(message):
    chat_id = message.chat.id
    USER_STATE[chat_id]['temp_recipe']['ingredients'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_VIDEO
    bot.send_message(chat_id, "Шаг 4/5: Отправьте видеофайл или ссылку:")
    bot.register_next_step_handler(message, process_video)

def process_video(message):
    chat_id = message.chat.id
    vid = message.video.file_id if message.video else message.text.strip()
    if not vid:
        bot.send_message(chat_id, "Ничего не отправлено. Повторите:")
        bot.register_next_step_handler(message, process_video)
        return
    USER_STATE[chat_id]['temp_recipe']['video'] = vid
    USER_STATE[chat_id]['temp_recipe']['video_type'] = 'file' if message.video else 'link'
    USER_STATE[chat_id]['temp_recipe'][FAVORITE_KEY] = False
    USER_STATE[chat_id]['state'] = STATE_KEYWORDS
    bot.send_message(chat_id, "Шаг 5/5: Введите ключевые слова через запятую:")
    bot.register_next_step_handler(message, finish_recipe_add)

def finish_recipe_add(message):
    chat_id = message.chat.id
    temp = USER_STATE[chat_id]['temp_recipe']
    temp['keywords'] = message.text.strip().lower()
    rid = str(uuid.uuid4())
    RECIPES[rid] = temp
    save_recipes(RECIPES)
    del USER_STATE[chat_id]
    bot.send_message(chat_id, f"🎉 Рецепт '{temp['title']}' сохранен!", reply_markup=generate_main_markup())

# --- Callbacks ---
@bot.callback_query_handler(func=lambda c: c.data.startswith('cat_'))
def handle_category_selection(call):
    bot.answer_callback_query(call.id)
    cat = call.data.split('_')[1]
    filtered = {}
    if cat == 'all':
        filtered = RECIPES
    elif cat == 'favorite':
        filtered = {rid: r for rid, r in RECIPES.items() if r.get(FAVORITE_KEY)}
    else:
        filtered = {rid: r for rid, r in RECIPES.items() if r['category'] == cat}

    if not filtered:
        bot.send_message(call.message.chat.id, "Рецептов в этой категории нет.")
        return
if not filtered:
    bot.send_message(call.message.chat.id, "Рецептов в этой категории нет.")
    return

markup = types.InlineKeyboardMarkup(row_width=1)
for rid, r in filtered.items():
    markup.add(types.InlineKeyboardButton(r['title'], callback_data=f"show_{rid}"))
bot.send_message(call.message.chat.id, f"Рецепты категории {cat}:", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith('show_'))
def show_recipe_details(call):
    bot.answer_callback_query(call.id)
    rid = call.data.split('_')[1]
    r = RECIPES.get(rid)
    if not r:
        bot.send_message(call.message.chat.id, "Рецепт не найден.")
        return

    text = f"🍽 {r['title']}\n\nИнгредиенты:\n{r['ingredients']}\n\nПриготовление:\n{r['steps']}"
    bot.send_message(call.message.chat.id, text)


# Flask сервер для Render
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return "Бот работает!", 200


if __name__ == "__main__":
    from threading import Thread

    # Запуск бота в отдельном потоке
    Thread(target=lambda: bot.infinity_polling(skip_pending=True)).start()

    # Запуск Flask-сервера
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
