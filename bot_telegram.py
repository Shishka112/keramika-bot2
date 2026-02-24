# bot_telegram.py
# Полная версия с записью на мастер-классы, админ-панелью, каталогом товаров, 
# Google Calendar, автоматическим расписанием, количеством участников и напоминаниями

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import logging
from database import *
from google_calendar import calendar_manager
from auto_schedule import auto_scheduler
from reminder import ReminderSystem
from datetime import datetime, timedelta
import os
import csv
from io import StringIO
import datetime as dt

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ТОКЕН - ВСТАВЬТЕ СВОЙ!
TOKEN = "238579975461:AAGuXTe7W-EVTqWg19e0miG1Xa99r4d2QGk"

# ID администратора (ваш Telegram ID)
ADMIN_ID = "81041244277"
ADMIN_USERNAME = "@sergeynnn03"

# Состояния для ConversationHandler
PEOPLE_COUNT = range(1)

# Создаем таблицы в базе данных при запуске
create_tables()

def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    register_user(
        user_id=str(user.id),
        platform='telegram',
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username
    )
    
    # Базовое меню для всех пользователей
    reply_keyboard = [
        ["Заказать изделие", "Мастер-класс"],
        ["📋 Мои записи"]
    ]
    
    # Если пользователь - админ, добавляем кнопку админки
    if is_admin(user.id):
        reply_keyboard.append(["🔧 Админ-панель"])
        logger.info(f"Админ {user.first_name} вошел в систему")
    
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Добрый день, {user.first_name}! 👋\n\n"
        "Это «Керамика Юноны». Вы хотите записаться на мастер-класс или заказать изделие?",
        reply_markup=markup
    )

# --- Команда /cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    keys_to_clear = ['adding_product', 'editing_product', 'adding_slots', 'people_count']
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]
    
    await update.message.reply_text(
        "✅ Текущая операция отменена. Возвращаю в главное меню."
    )
    await start(update, context)

# --- Функция для создания кнопки связи с админом ---
def get_admin_contact_button():
    """Возвращает кнопку для связи с администратором."""
    keyboard = [
        [InlineKeyboardButton("👩‍🎨 Написать администратору", url=f"tg://user?id={ADMIN_ID}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Обработка ввода количества человек ---
async def people_count_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс ввода количества человек."""
    await update.message.reply_text(
        "👥 Введите количество человек, которые будут участвовать в мастер-классе:\n"
        "(например: 5, 10, 15)"
    )
    return PEOPLE_COUNT

async def people_count_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает и сохраняет количество человек."""
    text = update.message.text
    
    try:
        count = int(text)
        if count <= 0:
            await update.message.reply_text("❌ Количество должно быть положительным числом. Попробуйте еще раз:")
            return PEOPLE_COUNT
        if count > 50:
            await update.message.reply_text("❌ Максимальное количество - 50 человек. Попробуйте еще раз:")
            return PEOPLE_COUNT
            
        context.user_data['people_count'] = count
        
        current_mc = context.user_data.get('current_mc')
        await update.message.reply_text(
            f"✅ Количество сохранено: {count} человек(а)\n\n"
            f"Теперь вы можете выбрать дату для мастер-класса."
        )
        
        # Показываем меню МК
        reply_keyboard = [
            ["📅 Выбрать дату", "🎁 Заказать сертификат"],
            ["❓ Доп. вопрос админу"],
            ["🔙 Назад к МК", "🏠 Главное меню"]
        ]
        markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Что хотите сделать дальше?",
            reply_markup=markup
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число. Попробуйте еще раз:")
        return PEOPLE_COUNT

# --- Обработка текстовых сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    
    logger.info(f"Пользователь {user.first_name} написал: {text}")
    
    # Главное меню
    if text == "Заказать изделие":
        await show_order_menu(update, context)
    
    elif text == "Мастер-класс":
        await show_master_classes_menu(update, context)
    
    elif text == "📋 Мои записи":
        await show_user_bookings(update, context)
    
    elif text == "🔧 Админ-панель" and is_admin(user.id):
        await show_admin_panel(update, context)
    
    elif text == "Назад в главное меню" or text == "🏠 Главное меню":
        await start(update, context)
    
    # Админ-панель
    elif text == "📋 Неподтвержденные записи" and is_admin(user.id):
        await show_pending_bookings(update, context)
    
    elif text == "📅 Управление расписанием" and is_admin(user.id):
        await show_schedule_management(update, context)
    
    elif text == "📦 Управление товарами" and is_admin(user.id):
        await show_product_management(update, context)
    
    elif text == "📊 Статистика" and is_admin(user.id):
        await show_statistics(update, context)
    
    elif text == "📤 Экспорт данных" and is_admin(user.id):
        await export_data(update, context)
    
    elif text == "📅 Проверить календарь" and is_admin(user.id):
        await check_calendar(update, context)
    
    elif text == "🔔 Статистика напоминаний" and is_admin(user.id):
        await check_reminders(update, context)
    
    # Управление расписанием
    elif text == "➕ Добавить слоты" and is_admin(user.id):
        await ask_for_slots(update, context)
    
    elif text == "🗑 Удалить слот" and is_admin(user.id):
        await show_slots_to_delete(update, context)
    
    elif text == "📅 Показать все слоты" and is_admin(user.id):
        await show_all_slots(update, context)
    
    elif text == "📊 Статистика расписания" and is_admin(user.id):
        await show_schedule_stats(update, context)
    
    elif text == "📅 Создать слоты вручную" and is_admin(user.id):
        await manual_create_slots(update, context)
    
    elif text == "🔙 Назад в админку" and is_admin(user.id):
        await show_admin_panel(update, context)
    
    # Управление товарами
    elif text == "➕ Добавить товар" and is_admin(user.id):
        await add_product_start(update, context)
    
    elif text == "📦 Список товаров" and is_admin(user.id):
        await list_all_products(update, context)
    
    elif text == "🗑 Удалить товар" and is_admin(user.id):
        await delete_product_start(update, context)
    
    elif text == "✏️ Редактировать товар" and is_admin(user.id):
        await edit_product_start(update, context)
    
    # Пошаговое добавление товара
    elif 'adding_product' in context.user_data and is_admin(user.id):
        await handle_add_product(update, context)
    
    # Пошаговое редактирование товара
    elif 'editing_product' in context.user_data and is_admin(user.id):
        await handle_edit_product(update, context)
    
    # Обработка мастер-классов
    else:
        mc = get_master_class_by_name(text)
        if mc:
            context.user_data['current_mc'] = dict(mc)
            # Сбрасываем количество человек при выборе нового МК
            if 'people_count' in context.user_data:
                del context.user_data['people_count']
            
            await update.message.reply_text(mc['description'])
            
            # Для групповых и школьных МК добавляем кнопку выбора количества человек
            if mc['name'] in ["Групповой", "Школьный"]:
                reply_keyboard = [
                    ["👥 Указать количество", "📅 Выбрать дату"],
                    ["🎁 Заказать сертификат", "❓ Доп. вопрос админу"],
                    ["🔙 Назад к МК", "🏠 Главное меню"]
                ]
            else:
                reply_keyboard = [
                    ["📅 Выбрать дату", "🎁 Заказать сертификат"],
                    ["❓ Доп. вопрос админу"],
                    ["🔙 Назад к МК", "🏠 Главное меню"]
                ]
            
            markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Что хотите сделать?",
                reply_markup=markup
            )
        
        elif text == "👥 Указать количество":
            if 'current_mc' in context.user_data:
                current_mc = context.user_data['current_mc']
                if current_mc['name'] in ["Групповой", "Школьный"]:
                    await people_count_start(update, context)
                else:
                    await update.message.reply_text("❌ Количество человек можно указать только для групповых и школьных мастер-классов.")
            else:
                await update.message.reply_text("Сначала выберите мастер-класс!")
        
        elif text == "📅 Выбрать дату":
            if 'current_mc' in context.user_data:
                current_mc = context.user_data['current_mc']
                
                # Проверяем, нужно ли указать количество для групповых МК
                if current_mc['name'] in ["Групповой", "Школьный"] and 'people_count' not in context.user_data:
                    await update.message.reply_text(
                        "👥 Пожалуйста, сначала укажите количество человек, которые будут участвовать.\n"
                        "Нажмите кнопку '👥 Указать количество'"
                    )
                else:
                    await show_week_schedule(update, context)
            else:
                await update.message.reply_text("Сначала выберите мастер-класс!")
        
        elif text == "🎁 Заказать сертификат":
            if 'current_mc' in context.user_data:
                mc = context.user_data['current_mc']
                people_text = ""
                if 'people_count' in context.user_data and mc['name'] in ["Групповой", "Школьный"]:
                    people_text = f"\nКоличество человек: {context.user_data['people_count']}"
                
                await update.message.reply_text(
                    f"🎁 Подарочный сертификат на мастер-класс '{mc['name']}'\n\n"
                    f"{mc['description']}{people_text}\n\n"
                    "Для оформления сертификата нажмите кнопку ниже:",
                    reply_markup=get_admin_contact_button()
                )
            else:
                await update.message.reply_text("Сначала выберите мастер-класс!")
        
        elif text == "❓ Доп. вопрос админу":
            mc_name = ""
            people_text = ""
            if 'current_mc' in context.user_data:
                mc = context.user_data['current_mc']
                mc_name = f" по мастер-классу '{mc['name']}'"
                if 'people_count' in context.user_data and mc['name'] in ["Групповой", "Школьный"]:
                    people_text = f" (количество человек: {context.user_data['people_count']})"
            
            await update.message.reply_text(
                f"Задайте ваш вопрос администратору{people_text}{mc_name}. Он скоро ответит!",
                reply_markup=get_admin_contact_button()
            )
        
        elif text == "🔙 Назад к МК":
            await show_master_classes_menu(update, context)
        
        elif text == "Посмотреть наличие":
            await show_product_categories(update, context)
        
        elif text == "Сделать заказ по референсу":
            await update.message.reply_text(
                "Для заказа по вашему референсу свяжитесь с администратором:",
                reply_markup=get_admin_contact_button()
            )
        
        elif text in ["🍽 Тарелки", "☕️ Чашки", "🏺 Вазы", "💍 Украшения"] or \
             any(text.startswith(cat) for cat in ["🍽", "☕️", "🏺", "💍"]):
            if "(" in text:
                category = text.split(" ")[1]
            else:
                category = text.split(" ")[1]
            await show_products_by_category(update, context, category)
        
        else:
            await update.message.reply_text(
                "Пожалуйста, пользуйтесь кнопками меню."
            )

# --- Меню мастер-классов ---
async def show_master_classes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mcs = get_all_master_classes()
    
    reply_keyboard = []
    row = []
    for i, mc in enumerate(mcs):
        row.append(mc['name'])
        if len(row) == 2 or i == len(mcs) - 1:
            reply_keyboard.append(row)
            row = []
    
    reply_keyboard.append(["📋 Мои записи", "🏠 Главное меню"])
    
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите формат мастер-класса:",
        reply_markup=markup
    )

async def show_master_classes_menu_via_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    mcs = get_all_master_classes()
    
    reply_keyboard = []
    row = []
    for i, mc in enumerate(mcs):
        row.append(mc['name'])
        if len(row) == 2 or i == len(mcs) - 1:
            reply_keyboard.append(row)
            row = []
    
    reply_keyboard.append(["📋 Мои записи", "🏠 Главное меню"])
    
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите формат мастер-класса:",
        reply_markup=markup
    )

# --- Заказ изделий ---
async def show_order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ["Посмотреть наличие", "Сделать заказ по референсу"],
        ["Назад в главное меню"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=markup
    )

# --- Каталог товаров ---
async def show_product_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counts = get_products_count()
    count_dict = {row['category']: row['count'] for row in counts}
    
    reply_keyboard = [
        [f"🍽 Тарелки ({count_dict.get('Тарелки', 0)})", f"☕️ Чашки ({count_dict.get('Чашки', 0)})"],
        [f"🏺 Вазы ({count_dict.get('Вазы', 0)})", f"💍 Украшения ({count_dict.get('Украшения', 0)})"],
        ["🏠 Главное меню"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите категорию товаров:",
        reply_markup=markup
    )

async def show_products_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    products = get_products_by_category(category)
    
    if not products:
        await update.message.reply_text(
            f"В категории '{category}' пока нет товаров. Загляните позже!"
        )
        return
    
    context.user_data['current_category'] = category
    context.user_data['category_products'] = products
    context.user_data['current_product_index'] = 0
    
    await show_product(update, context, 0)

async def show_product(obj, context: ContextTypes.DEFAULT_TYPE, index):
    products = context.user_data.get('category_products', [])
    
    if not products or index < 0 or index >= len(products):
        return
    
    product = products[index]
    total = len(products)
    
    text = f"📦 **Товар {index + 1} из {total}**\n\n"
    text += f"{product['description']}\n\n"
    text += f"💰 **Цена:** {product['price']} руб."
    
    keyboard = []
    
    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"product_prev_{index}"))
    if index < total - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"product_next_{index}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    action_buttons = [
        InlineKeyboardButton("🛒 Заказать", callback_data=f"order_product_{product['id']}"),
        InlineKeyboardButton("🔙 В категории", callback_data="back_to_categories")
    ]
    keyboard.append(action_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(obj, 'message'):
        if product['photo_id']:
            await obj.message.reply_photo(
                photo=product['photo_id'],
                caption=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await obj.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    else:
        if product['photo_id']:
            await obj.message.reply_photo(
                photo=product['photo_id'],
                caption=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await obj.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

# --- Расписание ---
async def show_week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает расписание на неделю (общее для всех МК)."""
    
    current_mc = context.user_data.get('current_mc')
    if not current_mc:
        await update.message.reply_text("Сначала выберите мастер-класс!")
        return
    
    mc_name = current_mc['name']
    
    # Получаем все доступные слоты на неделю (общие для всех МК)
    slots = get_available_slots_for_week()
    
    if not slots:
        keyboard = [
            [InlineKeyboardButton("✍️ Написать администратору", url=f"tg://user?id={ADMIN_ID}")],
            [InlineKeyboardButton("🔙 Назад к МК", callback_data="back_to_mc_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"😔 На ближайшую неделю нет свободных слотов для мастер-класса '{mc_name}'.",
            reply_markup=reply_markup
        )
        return
    
    # Группируем по датам
    slots_by_date = {}
    for slot in slots:
        date = slot['date']
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)
    
    # Создаем инлайн-кнопки для каждой даты
    keyboard = []
    keyboard.append([InlineKeyboardButton(f"🎯 {mc_name}", callback_data="no_action")])
    
    for date, day_slots in slots_by_date.items():
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        day_num = date_obj.weekday()
        date_str = date_obj.strftime(f'%d.%m.%Y ({days_ru[day_num]})')
        
        keyboard.append([InlineKeyboardButton(f"📅 {date_str}", callback_data=f"date_{date}")])
        
        time_buttons = []
        for slot in day_slots:
            time_buttons.append(InlineKeyboardButton(
                f"{slot['time']}", 
                callback_data=f"slot_{slot['id']}"
            ))
        
        for i in range(0, len(time_buttons), 3):
            keyboard.append(time_buttons[i:i+3])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к МК", callback_data="back_to_mc_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📅 **Расписание для {mc_name} на неделю:**\n\n"
        "Нажмите на время для записи:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

# --- Обработка инлайн-кнопок ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = update.effective_user
    
    if data == "back_to_mc_menu":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user.id,
            text="Выберите формат мастер-класса:"
        )
        await show_master_classes_menu_via_message(user.id, context)
    
    elif data.startswith("date_"):
        date = data.replace("date_", "")
        
        current_mc = context.user_data.get('current_mc')
        if not current_mc:
            await query.message.edit_text("Ошибка: не выбран мастер-класс.")
            return
        
        mc_id = current_mc['id']
        
        all_slots = get_slots_by_date(date)
        slots = [slot for slot in all_slots if slot['is_available']]
        
        if slots:
            keyboard = []
            for slot in slots:
                # Показываем цену выбранного МК
                keyboard.append([InlineKeyboardButton(
                    f"{slot['time']} ({current_mc['price']} руб.)",
                    callback_data=f"slot_{slot['id']}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_week")])
            
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            date_str = date_obj.strftime('%d.%m.%Y (%A)')
            
            if query.message.text:
                await query.message.edit_text(
                    f"📅 **Слоты на {date_str} для {current_mc['name']}:**\n\nВыберите время:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"📅 **Слоты на {date_str} для {current_mc['name']}:**\n\nВыберите время:",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
    
    elif data.startswith("slot_"):
        slot_id = int(data.replace("slot_", ""))
        
        # Получаем выбранный МК из контекста
        current_mc = context.user_data.get('current_mc')
        if not current_mc:
            if query.message.text:
                await query.message.edit_text(
                    "❌ Ошибка: не выбран мастер-класс. Пожалуйста, начните заново.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К мастер-классам", callback_data="back_to_mc_menu")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text="❌ Ошибка: не выбран мастер-класс. Пожалуйста, начните заново.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К мастер-классам", callback_data="back_to_mc_menu")
                    ]])
                )
            return
        
        slot_info = get_slot_by_id(slot_id)
        
        if not slot_info or not slot_info['is_available']:
            if query.message.text:
                await query.message.edit_text(
                    "❌ К сожалению, этот слот уже занят.\n"
                    "Пожалуйста, выберите другое время.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К расписанию", callback_data="back_to_week")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text="❌ К сожалению, этот слот уже занят.\n"
                         "Пожалуйста, выберите другое время.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К расписанию", callback_data="back_to_week")
                    ]])
                )
            return
        
        # Получаем количество человек (для групповых и школьных)
        people_count = context.user_data.get('people_count', 1)
        people_text = f"\n👥 Количество человек: {people_count}" if people_count > 1 else ""
        
        success, result = book_slot(
            slot_id, 
            current_mc['id'],  # ID выбранного МК из контекста
            str(user.id), 
            f"{user.first_name}" + (f" (+{people_count} чел)" if people_count > 1 else ""), 
            'telegram'
        )
        
        if success:
            if slot_info:
                # Добавляем событие в Google Calendar
                calendar_status = ""
                try:
                    event_id = calendar_manager.add_master_class_event(
                        mc_name=current_mc['name'] + (f" ({people_count} чел)" if people_count > 1 else ""),
                        client_name=user.first_name,
                        client_username=user.username or 'нет_username',
                        date_str=slot_info['date'],
                        time_str=slot_info['time']
                    )
                    
                    if event_id:
                        update_booking_event_id(result, event_id)
                        calendar_status = "✅ Событие добавлено в календарь"
                    else:
                        calendar_status = "⚠️ Не удалось добавить в календарь"
                except Exception as e:
                    logger.error(f"Ошибка календаря: {e}")
                    calendar_status = "⚠️ Ошибка интеграции с календарем"
                
                if query.message.text:
                    await query.message.edit_text(
                        f"✅ **Заявка на запись отправлена!**\n\n"
                        f"Мастер-класс: {current_mc['name']}{people_text}\n"
                        f"Дата: {slot_info['date']}\n"
                        f"Время: {slot_info['time']}\n\n"
                        f"{calendar_status}\n\n"
                        "Администратор подтвердит вашу запись в ближайшее время.\n"
                        "Вы получите уведомление о подтверждении.",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")
                        ]])
                    )
                else:
                    await query.message.delete()
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=f"✅ **Заявка на запись отправлена!**\n\n"
                             f"Мастер-класс: {current_mc['name']}{people_text}\n"
                             f"Дата: {slot_info['date']}\n"
                             f"Время: {slot_info['time']}\n\n"
                             f"{calendar_status}\n\n"
                             "Администратор подтвердит вашу запись в ближайшее время.\n"
                             "Вы получите уведомление о подтверждении.",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")
                        ]])
                    )
                
                await notify_admin_new_booking(context, current_mc, slot_info, user, people_count)
        else:
            if query.message.text:
                await query.message.edit_text(
                    "❌ Произошла ошибка при записи. Попробуйте еще раз.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✍️ Написать админу", url=f"tg://user?id={ADMIN_ID}")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text="❌ Произошла ошибка при записи. Попробуйте еще раз.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✍️ Написать админу", url=f"tg://user?id={ADMIN_ID}")
                    ]])
                )
    
    elif data == "back_to_week":
        await show_week_schedule_callback(query, context)
    
    elif data == "my_bookings":
        await show_user_bookings_callback(query, context)
    
    elif data.startswith("confirm_booking_"):
        if is_admin(user.id):
            booking_id = int(data.replace("confirm_booking_", ""))
            confirm_booking(booking_id)
            
            try:
                booking = get_booking_by_id(booking_id)
                if booking and booking['event_id']:
                    calendar_manager.update_event_status(
                        booking['event_id'], 
                        'confirmed',
                        booking['username']
                    )
            except Exception as e:
                logger.error(f"Ошибка обновления статуса в календаре: {e}")
            
            if query.message.text:
                await query.message.edit_text(
                    "✅ Запись подтверждена!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К заявкам", callback_data="admin_pending")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text="✅ Запись подтверждена!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К заявкам", callback_data="admin_pending")
                    ]])
                )
            await notify_user_booking_confirmed(context, booking_id)
    
    elif data.startswith("cancel_booking_"):
        if is_admin(user.id):
            booking_id = int(data.replace("cancel_booking_", ""))
            cancel_booking(booking_id)
            
            try:
                booking = get_booking_by_id(booking_id)
                if booking and booking['event_id']:
                    calendar_manager.update_event_status(
                        booking['event_id'], 
                        'cancelled',
                        booking['username']
                    )
            except Exception as e:
                logger.error(f"Ошибка обновления статуса в календаре: {e}")
            
            if query.message.text:
                await query.message.edit_text(
                    "❌ Запись отклонена",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К заявкам", callback_data="admin_pending")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text="❌ Запись отклонена",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К заявкам", callback_data="admin_pending")
                    ]])
                )
            await notify_user_booking_cancelled(context, booking_id)
    
    elif data.startswith("product_prev_"):
        index = int(data.replace("product_prev_", ""))
        new_index = index - 1
        await query.message.delete()
        await show_product(query, context, new_index)
    
    elif data.startswith("product_next_"):
        index = int(data.replace("product_next_", ""))
        new_index = index + 1
        await query.message.delete()
        await show_product(query, context, new_index)
    
    elif data == "back_to_categories":
        await query.message.delete()
        counts = get_products_count()
        count_dict = {row['category']: row['count'] for row in counts}
        
        reply_keyboard = [
            [f"🍽 Тарелки ({count_dict.get('Тарелки', 0)})", f"☕️ Чашки ({count_dict.get('Чашки', 0)})"],
            [f"🏺 Вазы ({count_dict.get('Вазы', 0)})", f"💍 Украшения ({count_dict.get('Украшения', 0)})"],
            ["🏠 Главное меню"]
        ]
        markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=user.id,
            text="Выберите категорию товаров:",
            reply_markup=markup
        )
    
    elif data.startswith("order_product_"):
        product_id = int(data.replace("order_product_", ""))
        product = get_product_by_id(product_id)
        if product:
            keyboard = [
                [InlineKeyboardButton("🛒 Связаться с администратором", url=f"tg://user?id={ADMIN_ID}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query.message.text:
                await query.message.edit_text(
                    f"🛒 **Заказ товара**\n\n"
                    f"Вы хотите заказать:\n{product['description']}\n\n"
                    f"Цена: {product['price']} руб.\n\n"
                    f"Нажмите кнопку ниже, чтобы связаться с администратором:",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🛒 **Заказ товара**\n\n"
                         f"Вы хотите заказать:\n{product['description']}\n\n"
                         f"Цена: {product['price']} руб.\n\n"
                         f"Нажмите кнопку ниже, чтобы связаться с администратором:",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
    
    elif data.startswith("delete_slot_"):
        if is_admin(user.id):
            slot_id = int(data.replace("delete_slot_", ""))
            success, message = delete_slot(slot_id)
            if query.message.text:
                await query.message.edit_text(
                    f"🗑 {message}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К списку слотов", callback_data="back_to_delete_slots")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🗑 {message}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К списку слотов", callback_data="back_to_delete_slots")
                    ]])
                )
    
    elif data.startswith("admin_del_product_"):
        if is_admin(user.id):
            product_id = int(data.replace("admin_del_product_", ""))
            product = get_product_by_id(product_id)
            if product:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_confirm_del_{product_id}"),
                        InlineKeyboardButton("❌ Нет, отмена", callback_data="back_to_product_management")
                    ]
                ]
                if query.message.text:
                    await query.message.edit_text(
                        f"Вы уверены, что хотите удалить товар?\n\n"
                        f"{product['description'][:100]}...\n"
                        f"Цена: {product['price']} руб.",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await query.message.delete()
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=f"Вы уверены, что хотите удалить товар?\n\n"
                             f"{product['description'][:100]}...\n"
                             f"Цена: {product['price']} руб.",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
    
    elif data.startswith("admin_confirm_del_"):
        if is_admin(user.id):
            product_id = int(data.replace("admin_confirm_del_", ""))
            delete_product(product_id)
            if query.message.text:
                await query.message.edit_text(
                    "✅ Товар успешно удален!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К управлению", callback_data="back_to_product_management")
                    ]])
                )
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=user.id,
                    text="✅ Товар успешно удален!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 К управлению", callback_data="back_to_product_management")
                    ]])
                )
    
    elif data.startswith("admin_edit_product_"):
        if is_admin(user.id):
            product_id = int(data.replace("admin_edit_product_", ""))
            context.user_data['editing_product_id'] = product_id
            context.user_data['editing_product'] = 'waiting_for_category'
            
            reply_keyboard = [
                ["🍽 Тарелки", "☕️ Чашки"],
                ["🏺 Вазы", "💍 Украшения"],
                ["🔙 Отмена"]
            ]
            markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
            await query.message.delete()
            await context.bot.send_message(
                chat_id=user.id,
                text="Выберите новую категорию для товара:",
                reply_markup=markup
            )
    
    elif data == "back_to_product_management":
        if is_admin(user.id):
            await query.message.delete()
            await show_product_management_callback(user.id, context)
    
    elif data == "back_to_schedule_management":
        if is_admin(user.id):
            await query.message.delete()
            await show_schedule_management_callback(user.id, context)
    
    elif data == "back_to_delete_slots":
        if is_admin(user.id):
            await query.message.delete()
            await show_slots_to_delete_callback(user.id, context)
    
    elif data == "admin_pending":
        if is_admin(user.id):
            await query.message.delete()
            await show_pending_bookings_callback(user.id, context)

# --- Вспомогательные callback-функции ---
async def show_week_schedule_callback(query, context):
    current_mc = context.user_data.get('current_mc')
    if not current_mc:
        await query.message.edit_text(
            "Ошибка: не выбран мастер-класс.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_mc_menu")
            ]])
        )
        return
    
    mc_name = current_mc['name']
    
    slots = get_available_slots_for_week()
    
    if not slots:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад к МК", callback_data="back_to_mc_menu")]
        ]
        await query.message.edit_text(
            f"😔 Нет свободных слотов для {mc_name}.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    slots_by_date = {}
    for slot in slots:
        date = slot['date']
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)
    
    keyboard = []
    keyboard.append([InlineKeyboardButton(f"🎯 {mc_name}", callback_data="no_action")])
    
    for date, day_slots in slots_by_date.items():
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        day_num = date_obj.weekday()
        date_str = date_obj.strftime(f'%d.%m.%Y ({days_ru[day_num]})')
        
        keyboard.append([InlineKeyboardButton(f"📅 {date_str}", callback_data=f"date_{date}")])
        
        time_buttons = []
        for slot in day_slots:
            time_buttons.append(InlineKeyboardButton(
                f"{slot['time']}", 
                callback_data=f"slot_{slot['id']}"
            ))
        
        for i in range(0, len(time_buttons), 3):
            keyboard.append(time_buttons[i:i+3])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к МК", callback_data="back_to_mc_menu")])
    
    if query.message.text:
        await query.message.edit_text(
            f"📅 **Расписание для {mc_name} на неделю:**\n\nНажмите на время для записи:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"📅 **Расписание для {mc_name} на неделю:**\n\nНажмите на время для записи:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_user_bookings_callback(query, context):
    user = query.from_user
    bookings = get_user_bookings(str(user.id))
    
    if not bookings:
        keyboard = [
            [InlineKeyboardButton("📅 Записаться на МК", callback_data="back_to_mc_menu")]
        ]
        if query.message.text:
            await query.message.edit_text(
                "У вас пока нет активных записей.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=user.id,
                text="У вас пока нет активных записей.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    text = "📋 **Ваши записи:**\n\n"
    for booking in bookings:
        status_emoji = "⏳" if booking['status'] == 'pending' else "✅" if booking['status'] == 'confirmed' else "❌"
        people_text = ""
        if "+" in booking['user_name']:
            people_text = f" {booking['user_name'].split('+')[1].strip()}"
        
        text += f"{status_emoji} {booking['mc_name']}{people_text}\n"
        text += f"   📅 {booking['date']} в {booking['time']}\n"
        text += f"   Статус: {booking['status']}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_mc_menu")]]
    
    if query.message.text:
        await query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- Админ-панель ---
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ["📋 Неподтвержденные записи", "📅 Управление расписанием"],
        ["📦 Управление товарами", "📊 Статистика"],
        ["📤 Экспорт данных", "📅 Проверить календарь"],
        ["🔔 Статистика напоминаний", "🔙 Назад в админку"],
        ["🏠 Главное меню"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🔧 **Панель администратора**\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=markup
    )

async def show_pending_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = get_pending_bookings()
    
    if not pending:
        await update.message.reply_text("✅ Нет неподтвержденных записей.")
        return
    
    for booking in pending:
        # Извлекаем количество человек из user_name если есть
        people_info = ""
        if "+" in booking['user_name']:
            people_info = f"\n👥 {booking['user_name'].split('+')[1].strip()}"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking['id']}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"cancel_booking_{booking['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"🔔 **Новая заявка**\n\n"
            f"Клиент: {booking['first_name']} "
            f"{booking['last_name'] or ''}{people_info}\n"
            f"Username: @{booking['username'] or 'нет'}\n"
            f"Платформа: {booking['platform']}\n"
            f"МК: {booking['mc_name']}\n"
            f"Дата: {booking['date']}\n"
            f"Время: {booking['time']}\n"
            f"Запись создана: {booking['created_at']}"
        )
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_schedule_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления расписанием."""
    reply_keyboard = [
        ["➕ Добавить слоты", "🗑 Удалить слот"],
        ["📅 Показать все слоты", "📊 Статистика расписания"],
        ["📅 Создать слоты вручную", "🔙 Назад в админку"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📅 **Управление расписанием**\n\n"
        "Автоматическое расписание:\n"
        "• Будни: 12:00, 18:00\n"
        "• Выходные: 12:00, 15:00, 18:00\n\n"
        "Слоты создаются автоматически на 14 дней вперед.\n"
        "Вы также можете добавить слоты вручную.",
        parse_mode='Markdown',
        reply_markup=markup
    )

async def show_product_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ["➕ Добавить товар", "📦 Список товаров"],
        ["🗑 Удалить товар", "✏️ Редактировать товар"],
        ["🔙 Назад в админку"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📦 **Управление товарами**\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=markup
    )

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подробную статистику."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE date(registered_at) = date('now')")
    new_users_today = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'confirmed'")
    confirmed_bookings = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'pending'")
    pending_bookings = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE date(created_at) = date('now')")
    new_bookings_today = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM products")
    total_products = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM products 
        GROUP BY category
    ''')
    products_by_category = cursor.fetchall()
    
    cursor.execute('''
        SELECT mc.name, COUNT(*) as count 
        FROM bookings b
        JOIN master_classes mc ON b.mc_id = mc.id
        WHERE b.status = 'confirmed'
        GROUP BY mc.name
    ''')
    bookings_by_mc = cursor.fetchall()
    
    # Статистика напоминаний
    reminder_stats = get_reminder_stats()
    
    conn.close()
    
    text = "📊 **ПОДРОБНАЯ СТАТИСТИКА**\n\n"
    
    text += "👥 **Пользователи:**\n"
    text += f"• Всего: {total_users}\n"
    text += f"• Новых сегодня: {new_users_today}\n\n"
    
    text += "📅 **Записи на МК:**\n"
    text += f"• Всего подтвержденных: {confirmed_bookings}\n"
    text += f"• Ожидают: {pending_bookings}\n"
    text += f"• Новых сегодня: {new_bookings_today}\n\n"
    
    if bookings_by_mc:
        text += "📌 **По типам МК:**\n"
        for mc in bookings_by_mc:
            text += f"• {mc['name']}: {mc['count']}\n"
        text += "\n"
    
    text += "📦 **Товары:**\n"
    text += f"• Всего: {total_products}\n"
    
    if products_by_category:
        for cat in products_by_category:
            text += f"• {cat['category']}: {cat['count']}\n"
    
    text += "\n🔔 **Напоминания:**\n"
    text += f"• Ожидают отправки: {reminder_stats['pending']}\n"
    text += f"• Отправлено всего: {reminder_stats['sent']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспортирует данные в CSV файл."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    await update.message.reply_text("⏳ Формирую файл с данными...")
    
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, first_name, last_name, username, platform, registered_at 
        FROM users 
        ORDER BY registered_at DESC
    ''')
    users = cursor.fetchall()
    
    if users:
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['user_id', 'first_name', 'last_name', 'username', 'platform', 'registered_at'])
        
        for user in users:
            writer.writerow([
                user['user_id'],
                user['first_name'] or '',
                user['last_name'] or '',
                user['username'] or '',
                user['platform'],
                user['registered_at']
            ])
        
        output.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=output.getvalue().encode('utf-8'),
            filename=f"users_{timestamp}.csv",
            caption="📊 Экспорт пользователей"
        )
    
    cursor.execute('''
        SELECT b.*, s.date, s.time, mc.name as mc_name, u.username
        FROM bookings b
        JOIN schedule s ON b.schedule_id = s.id
        JOIN master_classes mc ON b.mc_id = mc.id
        JOIN users u ON b.user_id = u.user_id
        ORDER BY s.date DESC, s.time DESC
    ''')
    bookings = cursor.fetchall()
    
    if bookings:
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['id', 'user_id', 'username', 'mc_name', 'date', 'time', 'status', 'created_at', 'event_id', 'reminder_sent', 'people_count'])
        
        for booking in bookings:
            # Извлекаем количество человек из user_name
            people_count = 1
            if "+" in booking['user_name']:
                try:
                    people_count = int(booking['user_name'].split('+')[1].replace('чел', '').strip())
                except:
                    pass
            
            writer.writerow([
                booking['id'],
                booking['user_id'],
                booking['username'] or '',
                booking['mc_name'],
                booking['date'],
                booking['time'],
                booking['status'],
                booking['created_at'],
                booking['event_id'] or '',
                booking['reminder_sent'],
                people_count
            ])
        
        output.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=output.getvalue().encode('utf-8'),
            filename=f"bookings_{timestamp}.csv",
            caption="📊 Экспорт записей"
        )
    
    products = get_all_products()
    if products:
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['id', 'category', 'description', 'price', 'created_at'])
        
        for product in products:
            writer.writerow([
                product['id'],
                product['category'],
                product['description'],
                product['price'],
                product['created_at']
            ])
        
        output.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=output.getvalue().encode('utf-8'),
            filename=f"products_{timestamp}.csv",
            caption="📊 Экспорт товаров"
        )
    
    conn.close()
    await update.message.reply_text("✅ Экспорт завершен! Файлы отправлены.")

async def check_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет и настраивает интеграцию с Google Calendar."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    if calendar_manager.service and calendar_manager.authenticated:
        await update.message.reply_text(
            "✅ Google Calendar уже подключен и работает!\n\n"
            "Все новые записи автоматически добавляются в ваш календарь."
        )
    else:
        await update.message.reply_text(
            "🔄 Начинаю настройку Google Calendar...\n"
            "Проверьте наличие файла credentials.json в папке с ботом.\n\n"
            "Если файл есть - сейчас откроется браузер для авторизации.\n"
            "Если файла нет - следуйте инструкции в calendar_setup.txt"
        )
        
        success = calendar_manager.authenticate()
        
        if success:
            await update.message.reply_text(
                "✅ Google Calendar успешно подключен!\n\n"
                "Теперь все новые записи будут добавляться в календарь."
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось подключить Google Calendar.\n\n"
                "Проверьте наличие файла credentials.json и повторите попытку."
            )

async def check_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус системы напоминаний."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    stats = get_reminder_stats()
    
    await update.message.reply_text(
        f"🔔 **СТАТИСТИКА НАПОМИНАНИЙ**\n\n"
        f"⏳ Ожидают отправки: {stats['pending']}\n"
        f"✅ Отправлено всего: {stats['sent']}",
        parse_mode='Markdown'
    )

async def manual_create_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ручное создание слотов на 14 дней вперед."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    await update.message.reply_text("🔄 Создаю слоты на 14 дней вперед...")
    
    added = auto_scheduler.create_default_slots()
    
    if added > 0:
        await update.message.reply_text(f"✅ Добавлено {added} новых слотов!")
    else:
        await update.message.reply_text("✅ Все слоты уже существуют. Новых не добавлено.")

async def show_schedule_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику по расписанию."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    stats = get_slots_stats()
    
    text = "📊 **СТАТИСТИКА РАСПИСАНИЯ**\n\n"
    text += f"📅 Всего будущих слотов: {stats['total_future']}\n"
    text += f"✅ Свободно: {stats['total_available']}\n"
    text += f"❌ Занято: {stats['total_future'] - stats['total_available']}\n\n"
    
    text += "**Ближайшие 14 дней:**\n"
    for slot in stats['daily_stats']:
        date_obj = datetime.strptime(slot['date'], '%Y-%m-%d')
        date_str = date_obj.strftime('%d.%m.%Y')
        text += f"• {date_str}: {slot['slots']} слотов ({slot['available']} свободно)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def ask_for_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос на добавление слотов (теперь без выбора МК, так как слоты общие)."""
    context.user_data['adding_slots'] = True
    await update.message.reply_text(
        "Введите дату и время для слотов в формате:\n"
        "ГГГГ-ММ-ДД ЧЧ:ММ\n"
        "Например: 2024-01-20 15:00\n\n"
        "Можно добавить несколько слотов, каждый с новой строки:"
    )

async def show_slots_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slots = get_all_future_slots()
    
    if not slots:
        await update.message.reply_text("Нет будущих слотов для удаления.")
        return
    
    keyboard = []
    for slot in slots[:20]:
        status = "✅" if slot['is_available'] else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{status} {slot['date']} {slot['time']}",
            callback_data=f"delete_slot_{slot['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_schedule_management")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите слот для удаления:\n✅ - свободен, ❌ - занят",
        reply_markup=reply_markup
    )

async def show_all_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slots = get_all_future_slots()
    
    if not slots:
        await update.message.reply_text("Нет будущих слотов.")
        return
    
    text = "📅 **Все будущие слоты:**\n\n"
    for slot in slots:
        status = "✅ свободен" if slot['is_available'] else "❌ занят"
        text += f"• {slot['date']} {slot['time']} ({status})\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000], parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

# --- Управление товарами (админ) ---
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ["🍽 Тарелки", "☕️ Чашки"],
        ["🏺 Вазы", "💍 Украшения"],
        ["🔙 Отмена"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите категорию товара:",
        reply_markup=markup
    )
    context.user_data['adding_product'] = 'waiting_for_category'

async def handle_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    if not is_admin(user.id):
        return
    
    step = context.user_data.get('adding_product')
    
    if step == 'waiting_for_category':
        if text in ["🍽 Тарелки", "☕️ Чашки", "🏺 Вазы", "💍 Украшения"]:
            category = text.split(" ")[1]
            context.user_data['new_product_category'] = category
            context.user_data['adding_product'] = 'waiting_for_photo'
            await update.message.reply_text(
                "📸 Отправьте фото товара (или отправьте 'пропустить' если без фото):"
            )
        elif text == "🔙 Отмена":
            del context.user_data['adding_product']
            await show_product_management(update, context)
        else:
            await update.message.reply_text("Пожалуйста, выберите категорию из кнопок!")
    
    elif step == 'waiting_for_photo':
        if update.message.photo:
            photo = update.message.photo[-1]
            context.user_data['new_product_photo'] = photo.file_id
            context.user_data['adding_product'] = 'waiting_for_description'
            await update.message.reply_text("📝 Введите описание товара:")
        elif text and text.lower() == 'пропустить':
            context.user_data['new_product_photo'] = None
            context.user_data['adding_product'] = 'waiting_for_description'
            await update.message.reply_text("📝 Введите описание товара:")
        else:
            await update.message.reply_text("Пожалуйста, отправьте фото или напишите 'пропустить'")
    
    elif step == 'waiting_for_description':
        if len(text) > 1000:
            await update.message.reply_text("❌ Описание слишком длинное! Максимум 1000 символов.")
            return
        context.user_data['new_product_description'] = text
        context.user_data['adding_product'] = 'waiting_for_price'
        await update.message.reply_text("💰 Введите цену товара (только число):")
    
    elif step == 'waiting_for_price':
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть положительным числом!")
                return
            if price > 1000000:
                await update.message.reply_text("❌ Цена слишком большая!")
                return
                
            category = context.user_data['new_product_category']
            description = context.user_data['new_product_description']
            photo_id = context.user_data.get('new_product_photo')
            
            product_id = add_product(category, description, price, photo_id)
            
            await update.message.reply_text(
                f"✅ Товар успешно добавлен!\n"
                f"Категория: {category}\n"
                f"Цена: {price} руб."
            )
            
            for key in ['adding_product', 'new_product_category', 'new_product_description', 'new_product_photo']:
                if key in context.user_data:
                    del context.user_data[key]
            
            await show_product_management(update, context)
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число!")

async def list_all_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_all_products()
    
    if not products:
        await update.message.reply_text("📦 В каталоге нет товаров.")
        return
    
    text = "📦 **Все товары:**\n\n"
    for product in products:
        text += f"• ID: {product['id']} | {product['category']}\n"
        text += f"  {product['description'][:50]}...\n"
        text += f"  💰 {product['price']} руб.\n\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000], parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def delete_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_all_products()
    
    if not products:
        await update.message.reply_text("📦 В каталоге нет товаров.")
        return
    
    keyboard = []
    for product in products[:10]:
        btn_text = f"ID:{product['id']} - {product['category']} - {product['price']}руб"
        keyboard.append([InlineKeyboardButton(btn_text[:50], callback_data=f"admin_del_product_{product['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="back_to_product_management")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите товар для удаления:",
        reply_markup=reply_markup
    )

async def edit_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = get_all_products()
    
    if not products:
        await update.message.reply_text("📦 В каталоге нет товаров.")
        return
    
    keyboard = []
    for product in products[:10]:
        btn_text = f"ID:{product['id']} - {product['category']} - {product['price']}руб"
        keyboard.append([InlineKeyboardButton(btn_text[:50], callback_data=f"admin_edit_product_{product['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="back_to_product_management")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите товар для редактирования:",
        reply_markup=reply_markup
    )

async def handle_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    if not is_admin(user.id):
        return
    
    step = context.user_data.get('editing_product')
    product_id = context.user_data.get('editing_product_id')
    
    if step == 'waiting_for_category':
        if text in ["🍽 Тарелки", "☕️ Чашки", "🏺 Вазы", "💍 Украшения"]:
            category = text.split(" ")[1]
            context.user_data['edit_product_category'] = category
            context.user_data['editing_product'] = 'waiting_for_description'
            await update.message.reply_text("📝 Введите новое описание товара (или отправьте 'оставить'):")
        elif text == "🔙 Отмена":
            for key in ['editing_product', 'editing_product_id']:
                if key in context.user_data:
                    del context.user_data[key]
            await show_product_management(update, context)
    
    elif step == 'waiting_for_description':
        if text.lower() == 'оставить':
            product = get_product_by_id(product_id)
            context.user_data['edit_product_description'] = product['description']
        else:
            context.user_data['edit_product_description'] = text
        context.user_data['editing_product'] = 'waiting_for_price'
        await update.message.reply_text("💰 Введите новую цену товара (или отправьте 'оставить'):")
    
    elif step == 'waiting_for_price':
        try:
            if text.lower() == 'оставить':
                product = get_product_by_id(product_id)
                price = product['price']
            else:
                price = int(text)
            
            category = context.user_data['edit_product_category']
            description = context.user_data['edit_product_description']
            
            update_product(product_id, category, description, price)
            
            await update.message.reply_text(f"✅ Товар успешно обновлен!")
            
            for key in ['editing_product', 'editing_product_id', 'edit_product_category', 'edit_product_description']:
                if key in context.user_data:
                    del context.user_data[key]
            
            await show_product_management(update, context)
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число!")

async def handle_edit_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает фото при редактировании товара."""
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    if 'editing_product' in context.user_data and context.user_data['editing_product'] == 'waiting_for_photo':
        if update.message.photo:
            photo = update.message.photo[-1]
            context.user_data['edit_product_photo'] = photo.file_id
            await update.message.reply_text("✅ Фото обновлено! Хотите изменить что-то еще?")

# --- Callback-функции для админа ---
async def show_product_management_callback(chat_id, context):
    reply_keyboard = [
        ["➕ Добавить товар", "📦 Список товаров"],
        ["🗑 Удалить товар", "✏️ Редактировать товар"],
        ["🔙 Назад в админку"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await context.bot.send_message(
        chat_id=chat_id,
        text="📦 **Управление товарами**\n\nВыберите действие:",
        parse_mode='Markdown',
        reply_markup=markup
    )

async def show_schedule_management_callback(chat_id, context):
    reply_keyboard = [
        ["➕ Добавить слоты", "🗑 Удалить слот"],
        ["📅 Показать все слоты", "📊 Статистика расписания"],
        ["📅 Создать слоты вручную", "🔙 Назад в админку"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await context.bot.send_message(
        chat_id=chat_id,
        text="📅 **Управление расписанием**\n\nВыберите действие:",
        parse_mode='Markdown',
        reply_markup=markup
    )

async def show_pending_bookings_callback(chat_id, context):
    pending = get_pending_bookings()
    
    if not pending:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ Нет неподтвержденных записей."
        )
        return
    
    for booking in pending:
        people_info = ""
        if "+" in booking['user_name']:
            people_info = f"\n👥 {booking['user_name'].split('+')[1].strip()}"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_booking_{booking['id']}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"cancel_booking_{booking['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"🔔 **Новая заявка**\n\n"
            f"Клиент: {booking['first_name']} "
            f"{booking['last_name'] or ''}{people_info}\n"
            f"Username: @{booking['username'] or 'нет'}\n"
            f"Платформа: {booking['platform']}\n"
            f"МК: {booking['mc_name']}\n"
            f"Дата: {booking['date']}\n"
            f"Время: {booking['time']}\n"
            f"Запись создана: {booking['created_at']}"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def show_slots_to_delete_callback(chat_id, context):
    slots = get_all_future_slots()
    
    if not slots:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Нет будущих слотов для удаления."
        )
        return
    
    keyboard = []
    for slot in slots[:20]:
        status = "✅" if slot['is_available'] else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{status} {slot['date']} {slot['time']}",
            callback_data=f"delete_slot_{slot['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_schedule_management")])
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите слот для удаления:\n✅ - свободен, ❌ - занят",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Уведомления ---
async def notify_admin_new_booking(context, mc_info, slot_info, user, people_count=1):
    try:
        people_text = f"\n👥 Количество человек: {people_count}" if people_count > 1 else ""
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **Новая заявка на запись!**\n\n"
                 f"Клиент: {user.first_name} (@{user.username}){people_text}\n"
                 f"МК: {mc_info['name']}\n"
                 f"Дата: {slot_info['date']}\n"
                 f"Время: {slot_info['time']}\n\n"
                 f"Для подтверждения зайдите в админ-панель.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить админа: {e}")

async def notify_user_booking_confirmed(context, booking_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, s.date, s.time, mc.name as mc_name, u.user_id
            FROM bookings b
            JOIN schedule s ON b.schedule_id = s.id
            JOIN master_classes mc ON b.mc_id = mc.id
            JOIN users u ON b.user_id = u.user_id
            WHERE b.id = ?
        ''', (booking_id,))
        booking = cursor.fetchone()
        conn.close()
        
        if booking:
            people_text = ""
            if "+" in booking['user_name']:
                people_text = f" ({booking['user_name'].split('+')[1].strip()})"
            
            await context.bot.send_message(
                chat_id=booking['user_id'],
                text=f"✅ **Ваша запись подтверждена!**\n\n"
                     f"Мастер-класс: {booking['mc_name']}{people_text}\n"
                     f"Дата: {booking['date']}\n"
                     f"Время: {booking['time']}\n\n"
                     f"Ждем вас в мастерской! 🏺\n"
                     f"❗️ Не забудьте, в мастерской живут кошки",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")

async def notify_user_booking_cancelled(context, booking_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, s.date, s.time, mc.name as mc_name, u.user_id
            FROM bookings b
            JOIN schedule s ON b.schedule_id = s.id
            JOIN master_classes mc ON b.mc_id = mc.id
            JOIN users u ON b.user_id = u.user_id
            WHERE b.id = ?
        ''', (booking_id,))
        booking = cursor.fetchone()
        conn.close()
        
        if booking:
            people_text = ""
            if "+" in booking['user_name']:
                people_text = f" ({booking['user_name'].split('+')[1].strip()})"
            
            await context.bot.send_message(
                chat_id=booking['user_id'],
                text=f"❌ **Запись отклонена**\n\n"
                     f"Мастер-класс: {booking['mc_name']}{people_text}\n"
                     f"Дата: {booking['date']}\n"
                     f"Время: {booking['time']}\n\n"
                     f"Пожалуйста, свяжитесь с администратором для выбора другого времени.",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")

# --- Мои записи ---
async def show_user_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bookings = get_user_bookings(str(user.id))
    
    if not bookings:
        keyboard = [
            [InlineKeyboardButton("📅 Записаться на МК", callback_data="back_to_mc_menu")]
        ]
        await update.message.reply_text(
            "У вас пока нет активных записей.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    text = "📋 **Ваши записи:**\n\n"
    for booking in bookings:
        status_emoji = "⏳" if booking['status'] == 'pending' else "✅" if booking['status'] == 'confirmed' else "❌"
        people_text = ""
        if "+" in booking['user_name']:
            people_text = f" {booking['user_name'].split('+')[1].strip()}"
        
        text += f"{status_emoji} {booking['mc_name']}{people_text}\n"
        text += f"   📅 {booking['date']} в {booking['time']}\n"
        text += f"   Статус: {booking['status']}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_mc_menu")]]
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Обработка текстового ввода от админа ---
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    if not is_admin(user.id):
        return
    
    if 'adding_slots' in context.user_data:
        lines = text.strip().split('\n')
        added_count = 0
        
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 2:
                date_str, time_str = parts
                try:
                    datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
                    added = add_schedule_slots_bulk(date_str, [time_str])
                    added_count += added
                except ValueError:
                    await update.message.reply_text(f"❌ Неверный формат: {line}")
                    continue
        
        await update.message.reply_text(
            f"✅ Добавлено {added_count} новых слотов!"
        )
        
        del context.user_data['adding_slots']

# --- Основная функция ---
def main():
    app = Application.builder().token(TOKEN).build()

    # ConversationHandler для ввода количества человек
    people_count_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^👥 Указать количество$'), people_count_start)],
        states={
            PEOPLE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, people_count_received)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(people_count_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.User(user_id=int(ADMIN_ID)), 
        handle_add_product
    ))
    
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.User(user_id=int(ADMIN_ID)), 
        handle_edit_product_photo
    ))
    
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(user_id=int(ADMIN_ID)), 
        handle_admin_text
    ), group=1)

    # Запускаем автоматическое планирование слотов
    try:
        auto_scheduler.start_scheduler()
        print("📅 Автоматическое расписание запущено (слоты на 14 дней вперед)")
    except Exception as e:
        print(f"⚠️ Ошибка запуска планировщика: {e}")

    # Запускаем систему напоминаний
    try:
        reminder_system = ReminderSystem(app)
        reminder_system.start()
    except Exception as e:
        print(f"⚠️ Ошибка запуска системы напоминаний: {e}")

    print("🤖 Бот с админ-панелью, каталогом и Google Calendar запущен!")
    print(f"👤 ID администратора: {ADMIN_ID}")
    print(f"📞 Username администратора: {ADMIN_USERNAME}")
    print("📝 Команды: /start - начало работы, /cancel - отмена операции")
    print("👥 Для групповых и школьных МК можно указать количество человек")
    print("🔔 Напоминания о мастер-классах запущены")
    print("📅 Google Calendar: проверьте настройки в админ-панели")
    app.run_polling()

if __name__ == "__main__":
    main()
