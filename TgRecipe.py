# Импорт необходимых библиотек
import telebot
from telebot import types
import json
import uuid
import os
from flask import Flask, request

# --- КОНФИГУРАЦИЯ БОТА ---
# !!! Вставьте сюда ваш реальный токен от BotFather !!!
BOT_TOKEN = "8416255020:AAG20WDAfIa4wMnjSqGtGZBoVFFEoGe4kAo"
bot = telebot.TeleBot(BOT_TOKEN)

# Константы для работы с файлами и состояниями
RECIPES_FILE = 'recipes.json'
USER_STATE = {} # Для хранения состояния пользователя при пошаговом вводе рецепта
STATE_NAME = 1
STATE_CATEGORY = 2
STATE_INGREDIENTS = 3
STATE_VIDEO = 4
STATE_KEYWORDS = 5
FAVORITE_KEY = "is_favorite"
FAVORITE_CATEGORY_NAME = "⭐ Избранное"

# --- ПОЛЬЗОВАТЕЛЬСКИЙ ПОРЯДОК КАТЕГОРИЙ ---
# Категории будут отображаться в этом порядке
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
    """Загружает рецепты из JSON-файла или возвращает пустой словарь."""
    if not os.path.exists(RECIPES_FILE):
        print("Файл рецептов не найден, инициализируем пустым словарем.")
        return {}
    try:
        with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"Загружено {len(data)} рецептов из {RECIPES_FILE}.")
            return data
    except json.JSONDecodeError as e:
        print(f"Ошибка чтения JSON-файла ({e}). Инициализируем пустым словарем.")
        return {}
    except Exception as e:
        print(f"Неизвестная ошибка при загрузке: {e}")
        return {}

def save_recipes(recipes_data):
    """Сохраняет рецепты в JSON-файл."""
    try:
        with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
            json.dump(recipes_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении рецептов: {e}")

# Инициализация рецептов при запуске
RECIPES = load_recipes()

# --- ФУНКЦИИ ГЕНЕРАЦИИ КЛАВИАТУР ---

def generate_main_markup():
    """Генерирует главную клавиатуру."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📖 Категории", "🔍 Поиск Рецепта")
    markup.add("➕ Добавить Рецепт")
    return markup

def generate_categories_markup():
    """Генерирует клавиатуру категорий в пользовательском порядке."""
    
    # 1. Список всех существующих категорий в базе
    existing_categories = set(r['category'] for r in RECIPES.values())
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # 2. Добавляем "Избранное" первым
    if any(r.get(FAVORITE_KEY) for r in RECIPES.values()):
        markup.add(types.InlineKeyboardButton(FAVORITE_CATEGORY_NAME, callback_data="cat_favorite"))

    # 3. Добавляем основные категории в пользовательском порядке
    for cat in CUSTOM_CATEGORY_ORDER:
        # Добавляем кнопку, только если такая категория существует
        if cat in existing_categories:
            markup.add(types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    
    # 4. Кнопка "Все рецепты"
    if RECIPES:
        markup.add(types.InlineKeyboardButton("Все рецепты", callback_data="cat_all"))

    return markup

def generate_recipe_actions_markup(recipe_id):
    """Генерирует клавиатуру действий для конкретного рецепта."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    recipe = RECIPES.get(recipe_id, {})
    
    # Кнопка Избранное/Убрать из избранного
    is_fav = recipe.get(FAVORITE_KEY, False)
    fav_text = "⭐ Убрать из избранного" if is_fav else "⭐ Добавить в избранное"
    markup.add(types.InlineKeyboardButton(fav_text, callback_data=f"toggle_fav_{recipe_id}"))

    # Кнопка Удалить
    markup.add(types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{recipe_id}"))
    
    # Кнопка Назад
    markup.add(types.InlineKeyboardButton("⬅️ К категориям", callback_data="back_to_cats"))
    
    return markup

# --- ОБРАБОТЧИКИ КОМАНД И ТЕКСТА ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Отправляет приветственное сообщение и главное меню."""
    text = "Добро пожаловать в вашу книгу рецептов! Выберите действие:"
    bot.send_message(message.chat.id, text, reply_markup=generate_main_markup())

@bot.message_handler(func=lambda message: message.text == "📖 Категории")
def show_categories(message):
    """Показывает список категорий в виде встроенной клавиатуры."""
    if not RECIPES:
        bot.send_message(message.chat.id, "Книга рецептов пуста. Добавьте первый рецепт!")
        return
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())

@bot.message_handler(func=lambda message: message.text == "🔍 Поиск Рецепта")
def start_search(message):
    """Активирует режим поиска."""
    bot.send_message(message.chat.id, 
                     "Введите слово или фразу для поиска (по названию, ингредиентам или ключевым словам):")
    # Регистрируем следующий шаг как поиск
    bot.register_next_step_handler(message, process_search_query)

def process_search_query(message):
    """Обрабатывает введенный поисковый запрос."""
    query = message.text.lower()
    found_recipes = {}

    for recipe_id, recipe in RECIPES.items():
        # Формируем строку для поиска по всем полям
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

# --- ДОБАВЛЕНИЕ РЕЦЕПТА (Пошаговый ввод) ---

@bot.message_handler(func=lambda message: message.text == "➕ Добавить Рецепт")
def start_add_recipe(message):
    """Начинает пошаговый процесс добавления рецепта."""
    chat_id = message.chat.id
    USER_STATE[chat_id] = {"state": STATE_NAME, "temp_recipe": {}}
    bot.send_message(chat_id, "Шаг 1/5: Введите название рецепта:")
    # Регистрируем следующий шаг
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    """Обрабатывает название рецепта."""
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_NAME:
        return send_welcome(message)
    
    USER_STATE[chat_id]['temp_recipe']['title'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_CATEGORY
    
    # Предлагаем существующие категории
    categories = sorted(list(set(r['category'] for r in RECIPES.values())))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if categories:
        markup.add(*categories, row_width=2)
    
    bot.send_message(chat_id, "Шаг 2/5: Введите или выберите категорию (например, 'Завтрак', 'Супы'):", reply_markup=markup)
    bot.register_next_step_handler(message, process_category)

def process_category(message):
    """Обрабатывает категорию рецепта."""
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_CATEGORY:
        return send_welcome(message)
    
    USER_STATE[chat_id]['temp_recipe']['category'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_INGREDIENTS
    
    # Возвращаем основную клавиатуру
    bot.send_message(chat_id, "Шаг 3/5: Введите список ингредиентов:", reply_markup=generate_main_markup())
    bot.register_next_step_handler(message, process_ingredients)

def process_ingredients(message):
    """Обрабатывает список ингредиентов."""
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_INGREDIENTS:
        return send_welcome(message)

    USER_STATE[chat_id]['temp_recipe']['ingredients'] = message.text.strip()
    USER_STATE[chat_id]['state'] = STATE_VIDEO
    
    bot.send_message(chat_id, "Шаг 4/5: Отправьте видеофайл или текстовую ссылку (например, на YouTube):")
    bot.register_next_step_handler(message, process_video)

def process_video(message):
    """Обрабатывает видеофайл (сохраняет file_id) или текстовую ссылку."""
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_VIDEO:
        return send_welcome(message)
    
    video_info = None

    if message.video:
        # Пользователь отправил видеофайл
        video_info = message.video.file_id
        USER_STATE[chat_id]['temp_recipe']['video_type'] = 'file'
    elif message.text:
        # Пользователь отправил текстовую ссылку
        video_info = message.text.strip()
        USER_STATE[chat_id]['temp_recipe']['video_type'] = 'link'
    
    if not video_info:
        # Ничего не отправлено, просим повторить
        bot.send_message(chat_id, "Не получено ни видео, ни ссылки. Пожалуйста, отправьте видеофайл или ссылку.")
        bot.register_next_step_handler(message, process_video) # Повторяем шаг
        return

    USER_STATE[chat_id]['temp_recipe']['video'] = video_info
    # Инициализируем статус избранного по умолчанию
    USER_STATE[chat_id]['temp_recipe'][FAVORITE_KEY] = False 
    USER_STATE[chat_id]['state'] = STATE_KEYWORDS
    
    bot.send_message(chat_id, "Шаг 5/5: Введите ключевые слова через запятую для поиска (например, быстро, ужин, курица):")
    bot.register_next_step_handler(message, finish_recipe_add)

def finish_recipe_add(message):
    """Завершает процесс и сохраняет рецепт."""
    chat_id = message.chat.id
    if chat_id not in USER_STATE or USER_STATE[chat_id]['state'] != STATE_KEYWORDS:
        return send_welcome(message)
    
    # Финализация данных
    temp_recipe = USER_STATE[chat_id]['temp_recipe']
    temp_recipe['keywords'] = message.text.strip().lower()
    recipe_id = str(uuid.uuid4())
    
    # Сохранение и очистка состояния
    RECIPES[recipe_id] = temp_recipe
    save_recipes(RECIPES)
    del USER_STATE[chat_id]

    bot.send_message(chat_id, 
                     f"🎉 Рецепт '{temp_recipe['title']}' успешно сохранен и доступен в категории '{temp_recipe['category']}'!", 
                     reply_markup=generate_main_markup())

# --- ОБРАБОТЧИКИ ВСТРОЕННОЙ КЛАВИАТУРЫ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category_selection(call):
    """Обрабатывает выбор категории."""
    bot.answer_callback_query(call.id)
    category_id = call.data.split('_')[1]
    
    filtered_recipes = {}
    
    if category_id == 'all':
        filtered_recipes = RECIPES
        title = "Все рецепты"
    elif category_id == 'favorite':
        # Фильтрация по флагу is_favorite
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
        # Добавляем эмодзи звезды, если рецепт избранный
        star = "⭐ " if recipe.get(FAVORITE_KEY) else ""
        markup.add(types.InlineKeyboardButton(f"{star}{recipe['title']}", callback_data=f"show_{recipe_id}"))

    bot.edit_message_text(chat_id=call.message.chat.id, 
                          message_id=call.message.message_id, 
                          text=title, 
                          reply_markup=markup)

def send_recipe_details(chat_id, message_id, recipe_id):
    """Отправляет детали рецепта. Используется для обновления и первого отображения."""
    recipe = RECIPES.get(recipe_id)
    if not recipe:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Рецепт не найден.")
        return

    # --- ИСПРАВЛЕННОЕ ФОРМАТИРОВАНИЕ ТЕКСТА ---
    favorite_status = " (⭐ В избранном)" if recipe.get(FAVORITE_KEY) else ""
    recipe_text = (
        f"📝 *{recipe['title']}*{favorite_status}\n"
        f"🔸 *Категория:* {recipe['category']}\n\n"
        f"🥕 *Ингредиенты:*\n{recipe['ingredients']}\n\n"
        f"🔗 *Ключевые слова:*\n{recipe.get('keywords', 'Нет')}"
    )

    back_markup = generate_recipe_actions_markup(recipe_id)

    video_info = recipe.get('video')
    video_type = recipe.get('video_type')

    if video_info and video_type == 'file':
        # Отправка видеофайла по file_id
        try:
            # Отправляем сначала видео с текстом рецепта в подписи
            bot.send_video(chat_id, video_info, caption=recipe_text, parse_mode="Markdown")
            
            # Удаляем старое сообщение (меню категорий)
            bot.delete_message(chat_id, message_id)
            
            # Отправляем кнопки действий в отдельном сообщении
            bot.send_message(chat_id, "Выберите действие с рецептом:", reply_markup=back_markup)
        except Exception as e:
            error_text = f"Ошибка при отправке видео (возможно, файл устарел).\n\n{recipe_text}"
            bot.send_message(chat_id, error_text, parse_mode="Markdown", reply_markup=back_markup)
            bot.delete_message(chat_id, message_id)

    elif video_info and video_type == 'link':
        # Если это ссылка, добавляем ее в текст
        recipe_text += f"\n\n📺 *Видео-инструкция:*\n{video_info}"
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                              text=recipe_text, parse_mode="Markdown", reply_markup=back_markup)
        
    else:
        # Если видео нет
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                              text=recipe_text, parse_mode="Markdown", reply_markup=back_markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('show_'))
def show_recipe_details(call):
    """Показывает детали рецепта."""
    bot.answer_callback_query(call.id)
    recipe_id = call.data.split('_')[1]
    send_recipe_details(call.message.chat.id, call.message.message_id, recipe_id)

# --- ОБРАБОТЧИКИ ДЕЙСТВИЙ (УДАЛЕНИЕ / ИЗБРАННОЕ) ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_fav_'))
def handle_toggle_favorite(call):
    """Переключает статус "Избранное" для рецепта."""
    bot.answer_callback_query(call.id)
    recipe_id = call.data.split('_')[2]
    
    if recipe_id in RECIPES:
        is_fav = RECIPES[recipe_id].get(FAVORITE_KEY, False)
        
        # Переключение статуса
        RECIPES[recipe_id][FAVORITE_KEY] = not is_fav
        save_recipes(RECIPES)

        # Обновление сообщения
        send_recipe_details(call.message.chat.id, call.message.message_id, recipe_id)
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text="Рецепт не найден.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def handle_delete_recipe(call):
    """Запрашивает подтверждение удаления рецепта."""
    bot.answer_callback_query(call.id)
    recipe_id = call.data.split('_')[1]
    recipe = RECIPES.get(recipe_id)
    
    if recipe:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{recipe_id}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data=f"show_{recipe_id}") # Вернуться к деталям
        )
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"⚠️ Вы уверены, что хотите удалить рецепт '{recipe['title']}'?",
                              reply_markup=markup)
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Рецепт не найден.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
def handle_confirm_delete(call):
    """Выполняет удаление рецепта."""
    bot.answer_callback_query(call.id, text="Рецепт удален!")
    recipe_id = call.data.split('_')[2]

    if recipe_id in RECIPES:
        recipe_title = RECIPES[recipe_id]['title']
        del RECIPES[recipe_id]
        save_recipes(RECIPES)

        # Возвращаем пользователя к списку категорий
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"🗑️ Рецепт '{recipe_title}' удален. Выберите категорию:",
                              reply_markup=generate_categories_markup())
    else:
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Рецепт не найден.")


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_cats')
def back_to_categories(call):
    """Возвращает к списку категорий."""
    bot.answer_callback_query(call.id)
    bot.edit_message_text(chat_id=call.message.chat.id, 
                          message_id=call.message.message_id, 
                          text="Выберите категорию:", 
                          reply_markup=generate_categories_markup())

# --- НАСТРОЙКА WEBHOOK (24/7 ХОСТИНГ) ---

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    """Простая проверка работоспособности сервиса."""
    return 'Recipe Telegram Bot is running.', 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Основной обработчик Webhook, принимает сообщения от Telegram."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Content-Type Error', 403

if __name__ == "__main__":
    # Запуск сервера Flask
    # Gunicorn запускает app, поэтому эта часть не используется на Render.
    # Но оставляем для локального тестирования.
    print("Flask app defined. Use gunicorn to run on Render.")
