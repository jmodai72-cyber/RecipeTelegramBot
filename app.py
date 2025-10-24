import os
print(f"\n[DEBUG] TELEGRAM_TOKEN from env: {os.environ.get('TELEGRAM_TOKEN')!r}\n")

import telebot
from telebot import types
import json
import uuid
import os
from flask import Flask, request

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Меняй на свой токен через секреты переменных Render!
bot = telebot.TeleBot(BOT_TOKEN)

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
    "Завтрак",
    "Супы",
    "Основные блюда",
    "Салат",
    "Vegan",
    "Десерты"
]

# --- ФУНКЦИИ РАБОТЫ С JSON ---
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
        print(f"Ошибка чтения recipes.json: {e}")
        return {}

def save_recipes(recipes_data):
    try:
        with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
            json.dump(recipes_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении рецептов: {e}")

RECIPES = load_recipes()

# --- КЛАВИАТУРЫ ---
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

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    print("=== /start обработан ===")
    bot.send_message(message.chat.id, "Тест!")


@bot.message_handler(func=lambda message: message.text == "📖 Категории")
def show_categories(message):
    if not RECIPES:
        bot.send_message(message.chat.id, "Книга рецептов пуста. Добавьте первый рецепт!")
        return
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())

@bot.message_handler(func=lambda message: message.text == "🔍 Поиск Рецепта")
def start_search(message):
    bot.send_message(message.chat.id, "Введите слово или фразу для поиска (по названию, ингредиентам или ключевым словам):")
    bot.register_next_step_handler(message, process_search_query)

def process_search_query(message):
    query = message.text.lower()
    found_recipes = {}
    for recipe_id, recipe in RECIPES.items():
        searchable_text = f"{recipe['title']} {recipe['category']} {recipe['ingredients']} {recipe.get('keywords', '')}".lower()
        if query in searchable_text:
            found_recipes[recipe_id] = recipe
    if found_recipes:
        text = f"Найдено {len(found_recipes)} рецепт(ов):\n"
        markup = types.InlineKeyboardMarkup(row_width=1)
        for recipe_id, recipe in found_recipes.items():
            text += f"▪️ {recipe['title']}\n"
            markup.add(types.InlineKeyboardButton(recipe['title'], callback_data=f"show_{recipe_id}"))
        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f"По запросу '{message.text}' ничего не найдено.")

@bot.message_handler(func=lambda message: message.text == "➕ Добавить Рецепт")
def start_add_recipe(message):
    chat_id = message.chat.id
    USER_STATE[chat_id] = {"state": STATE_NAME, "temp_recipe": {}}
    bot.send_message(chat_id, "Шаг 1/5: Введите название рецепта:")
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_NAME:
        return send_welcome(message)
    USER_STATE[chat_id]['temp_recipe']['title'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_CATEGORY
    categories = sorted(list(set(r['category'] for r in RECIPES.values())))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if categories:
        markup.add(*categories, row_width=2)
    bot.send_message(chat_id, "Шаг 2/5: Введите или выберите категорию:", reply_markup=markup)
    bot.register_next_step_handler(message, process_category)

def process_category(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_CATEGORY:
        return send_welcome(message)
    USER_STATE[chat_id]['temp_recipe']['category'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_INGREDIENTS
    bot.send_message(chat_id, "Шаг 3/5: Введите список ингредиентов:", reply_markup=generate_main_markup())
    bot.register_next_step_handler(message, process_ingredients)

def process_ingredients(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_INGREDIENTS:
        return send_welcome(message)
    USER_STATE[chat_id]['temp_recipe']['ingredients'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_VIDEO
    bot.send_message(chat_id, "Шаг 4/5: Отправьте видеофайл или ссылку (например, на YouTube):")
    bot.register_next_step_handler(message, process_video)

def process_video(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_VIDEO:
        return send_welcome(message)
    video_info = None
    if message.video:
        video_info = message.video.file_id
        USER_STATE[chat_id]['temp_recipe']['video_type'] = 'file'
    elif message.text:
        video_info = message.text.strip()
        USER_STATE[chat_id]['temp_recipe']['video_type'] = 'link'
    if not video_info:
        bot.send_message(chat_id, "Не получено ни видео, ни ссылки. Пожалуйста, отправьте видеофайл или ссылку.")
        bot.register_next_step_handler(message, process_video)
        return
    USER_STATE[chat_id]['temp_recipe']['video'] = video_info
    USER_STATE[chat_id]['temp_recipe'][FAVORITE_KEY] = False 
    USER_STATE[chat_id]['state'] = STATE_KEYWORDS
    bot.send_message(chat_id, "Шаг 5/5: Введите ключевые слова через запятую:")
    bot.register_next_step_handler(message, finish_recipe_add)

def finish_recipe_add(message):
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_KEYWORDS:
        return send_welcome(message)
    temp_recipe = USER_STATE[chat_id]['temp_recipe']
    temp_recipe['keywords'] = message.text.strip().lower()
    recipe_id = str(uuid.uuid4())
    RECIPES[recipe_id] = temp_recipe
    save_recipes(RECIPES)
    del USER_STATE[chat_id]
    bot.send_message(chat_id, f"Рецепт '{temp_recipe['title']}' сохранён в '{temp_recipe['category']}'!", reply_markup=generate_main_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category_selection(call):
    bot.answer_callback_query(call.id)
    category_id = call.data.split('_')[1]
    filtered_recipes = {}
    if category_id == 'all':
        filtered_recipes = RECIPES
        title = "Все рецепты"
    elif category_id == 'favorite':
        filtered_recipes = {id: r for id, r in RECIPES.items() if r.get(FAVORITE_KEY)}
        title = FAVORITE_CATEGORY_NAME
    else:
        title = f"Рецепты в категории: {category_id}"
        filtered_recipes = {id: r for id, r in RECIPES.items() if r['category'] == category_id}
    if not filtered_recipes:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text=f"В категории '{title}' нет рецептов.", reply_markup=generate_categories_markup())
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for recipe_id, recipe in filtered_recipes.items():
        star = "⭐ " if recipe.get(FAVORITE_KEY) else ""
        markup.add(types.InlineKeyboardButton(f"{star}{recipe['title']}", callback_data=f"show_{recipe_id}"))
    bot.edit_message_text(chat_id=call.message.chat.id, 
                          message_id=call.message.message_id, 
                          text=title, 
                          reply_markup=markup)

def send_recipe_details(chat_id, message_id, recipe_id):
    recipe = RECIPES.get(recipe_id)
    if not recipe:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Рецепт не найден.")
        return
    favorite_status = " (⭐ В избранном)" if recipe.get(FAVORITE_KEY) else ""
    recipe_text = (
        f"Рецепт: {recipe['title']}{favorite_status}\n"
        f"Категория: {recipe['category']}\n\n"
        f"Ингредиенты:\n{recipe['ingredients']}\n\n"
        f"Ключевые слова: {recipe.get('keywords', 'Нет')}"
    )
    back_markup = generate_recipe_actions_markup(recipe_id)
    video_info = recipe.get('video')
    video_type = recipe.get('video_type')
    if video_info and video_type == 'file':
        try:
            bot.send_video(chat_id, video_info, caption=recipe_text)
            bot.delete_message(chat_id, message_id)
            bot.send_message(chat_id, "Выберите действие с рецептом:", reply_markup=back_markup)
        except Exception as e:
            error_text = f"Ошибка при отправке видео.\n\n{recipe_text}"
            bot.send_message(chat_id, error_text, reply_markup=back_markup)
            bot.delete_message(chat_id, message_id)
    elif video_info and video_type == 'link':
        recipe_text += f"\nВидео-инструкция: {video_info}"
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                              text=recipe_text, reply_markup=back_markup)
    else:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                              text=recipe_text, reply_markup=back_markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_'))
def show_recipe_details(call):
    bot.answer_callback_query(call.id)
    recipe_id = call.data.split('_')[1]
    send_recipe_details(call.message.chat.id, call.message.message_id, recipe_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_fav_'))
def handle_toggle_favorite(call):
    bot.answer_callback_query(call.id)
    recipe_id = call.data.split('_')[2]
    if recipe_id in RECIPES:
        is_fav = RECIPES[recipe_id].get(FAVORITE_KEY, False)
        RECIPES[recipe_id][FAVORITE_KEY] = not is_fav
        save_recipes(RECIPES)
        send_recipe_details(call.message.chat.id, call.message.message_id, recipe_id)
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text="Рецепт не найден.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def handle_delete_recipe(call):
    bot.answer_callback_query(call.id)
    recipe_id = call.data.split('_')[1]
    recipe = RECIPES.get(recipe_id)
    if recipe:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{recipe_id}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data=f"show_{recipe_id}")
        )
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Удалить рецепт '{recipe['title']}'?", reply_markup=markup)
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Рецепт не найден.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
def handle_confirm_delete(call):
    bot.answer_callback_query(call.id, text="Рецепт удален!")
    recipe_id = call.data.split('_')[2]
    if recipe_id in RECIPES:
        recipe_title = RECIPES[recipe_id]['title']
        del RECIPES[recipe_id]
        save_recipes(RECIPES)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Рецепт '{recipe_title}' удален. Выберите категорию:",
                              reply_markup=generate_categories_markup())
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Рецепт не найден.")

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_cats')
def back_to_categories(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(chat_id=call.message.chat.id, 
                          message_id=call.message.message_id, 
                          text="Выберите категорию:", 
                          reply_markup=generate_categories_markup())

# --- WEBHOOK И FLASK ---
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
            print(f"== Получен апдейт от Telegram: {json_string}")  # <-- ЭТУ СТРОКУ Я ДОБАВИЛ!
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return '', 200
        except Exception as e:
            print(f"Ошибка при обработке обновления: {e}")
            return 'Processing Error', 200
    return 'Content-Type Error', 403

RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
if RENDER_URL:
    WEBHOOK_URL = RENDER_URL + WEBHOOK_PATH
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"Ошибка установки webhook: {e}")

# --- Локальный запуск Polling ---
# if __name__ == "__main__":
#     print("--- Локальный режим ---")
#     port = int(os.environ.get("PORT", 5000))
#     print("Запуск в режиме Polling...")
#     bot.remove_webhook()
#     bot.polling(none_stop=True)
