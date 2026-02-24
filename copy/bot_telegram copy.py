# bot_telegram.py
# Обновленная версия с поддержкой базы данных

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import logging
from database import (
    create_tables, get_master_class_by_name, get_all_master_classes,
    register_user, get_available_slots_for_week, book_slot,
    get_all_bookings, confirm_booking, cancel_booking,
    add_product, get_products_by_category, delete_product, update_product
)
from datetime import datetime
import os

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ТОКЕН - ВСТАВЬТЕ СВОЙ!
TOKEN = "8579975461:AAGuXTe7W-EVTqWg19e0miG1Xa99r4d2QGk"  # Я вижу ваш токен в логах, он уже здесь

# ID администратора (ваш Telegram ID)
# Как узнать свой ID: напишите боту @userinfobot в Telegram
ADMIN_ID = "810412477"  # <--- ЗАМЕНИТЕ НА СВОЙ ID!

# Создаем таблицы в базе данных при запуске
create_tables()

# --- Функция для проверки, является ли пользователь админом ---
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором."""
    return str(user_id) == ADMIN_ID

# --- Функция для команды /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветствие и показывает главное меню."""
    user = update.effective_user
    
    # Регистрируем пользователя в базе данных
    register_user(
        user_id=str(user.id),
        platform='telegram',
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username
    )
    
    # Главное меню
    reply_keyboard = [
        ["Заказать изделие", "Мастер-класс"],
    ]
    
    # Если пользователь - админ, добавляем кнопку админки
    if is_admin(user.id):
        reply_keyboard.append(["🔧 Админ-панель"])
    
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Добрый день, {user.first_name}! 👋\n\n"
        "Это «Керамика Юноны». Вы хотите записаться на мастер-класс или заказать изделие?",
        reply_markup=markup
    )

# --- Функция для обработки текстовых сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки и другие текстовые сообщения."""
    text = update.message.text
    user = update.effective_user
    
    logger.info(f"Пользователь {user.first_name} написал: {text}")
    
    # --- ОБРАБОТКА ГЛАВНОГО МЕНЮ ---
    if text == "Заказать изделие":
        reply_keyboard = [
            ["Посмотреть наличие", "Сделать заказ по референсу"],
            ["Назад в главное меню"]
        ]
        markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=markup
        )
        
    elif text == "Мастер-класс":
        # Получаем все мастер-классы из базы данных
        mcs = get_all_master_classes()
        
        # Создаем кнопки для каждого МК
        reply_keyboard = []
        row = []
        for i, mc in enumerate(mcs):
            row.append(mc['name'])
            if len(row) == 2 or i == len(mcs) - 1:  # По 2 кнопки в ряд
                reply_keyboard.append(row)
                row = []
        
        reply_keyboard.append(["Назад в главное меню"])
        
        markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите формат мастер-класса:",
            reply_markup=markup
        )
        
    elif text == "🔧 Админ-панель" and is_admin(user.id):
        await show_admin_panel(update, context)
        
    # --- ОБРАБОТКА НАЗАД ---
    elif text == "Назад в главное меню":
        await start(update, context)
        
    # --- ОБРАБОТКА МАСТЕР-КЛАССОВ (динамически из базы) ---
    else:
        # Проверяем, не является ли текст названием мастер-класса
        mc = get_master_class_by_name(text)
        if mc:
            # Сохраняем ID выбранного МК в контексте
            context.user_data['current_mc'] = dict(mc)
            
            # Показываем описание МК
            await update.message.reply_text(mc['description'])
            
            # Кнопки для действий
            reply_keyboard = [
                ["Выбрать дату", "Заказать сертификат"],
                ["Доп. вопрос админу"],
                ["Назад в меню МК", "Назад в главное меню"]
            ]
            markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Что хотите сделать?",
                reply_markup=markup
            )
            
        # --- ОБРАБОТКА ДЕЙСТВИЙ С МК ---
        elif text == "Выбрать дату":
            if 'current_mc' in context.user_data:
                # Показываем расписание на неделю
                await show_schedule(update, context)
            else:
                await update.message.reply_text("Сначала выберите мастер-класс!")
                
        elif text == "Заказать сертификат":
            if 'current_mc' in context.user_data:
                mc = context.user_data['current_mc']
                await update.message.reply_text(
                    f"🎁 Подарочный сертификат на мастер-класс '{mc['name']}'\n\n"
                    f"{mc['description']}\n\n"
                    "Для оформления сертификата напишите администратору: @sergeynnn03"
                )
            else:
                await update.message.reply_text("Сначала выберите мастер-класс!")
                
        elif text == "Доп. вопрос админу":
            await update.message.reply_text(
                "Задайте ваш вопрос администратору: @sergeynnn03"
            )
            
        elif text == "Назад в меню МК":
            # Показываем меню МК снова
            mcs = get_all_master_classes()
            reply_keyboard = []
            row = []
            for i, mc in enumerate(mcs):
                row.append(mc['name'])
                if len(row) == 2 or i == len(mcs) - 1:
                    reply_keyboard.append(row)
                    row = []
            reply_keyboard.append(["Назад в главное меню"])
            markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "Выберите формат мастер-класса:",
                reply_markup=markup
            )
            
        # --- ОБРАБОТКА ЗАКАЗА ИЗДЕЛИЙ ---
        elif text == "Посмотреть наличие":
            await show_product_categories(update, context)
            
        elif text == "Сделать заказ по референсу":
            await update.message.reply_text(
                "Сейчас я перекину вас на администратора. Напишите ему ваш заказ! 👩‍🎨\n"
                "@sergeynnn03"
            )
            
        # --- ОБРАБОТКА КАТЕГОРИЙ ТОВАРОВ ---
        elif text in ["🍽 Тарелки", "☕️ Чашки", "🏺 Вазы", "💍 Украшения"]:
            # Обработка категорий будет позже
            category = text.split(" ")[1]  # Убираем эмодзи
            await show_products_by_category(update, context, category)
            
        else:
            await update.message.reply_text(
                "Я не понимаю эту команду. Пожалуйста, пользуйтесь кнопками."
            )

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С РАСПИСАНИЕМ ---
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает доступные слоты на неделю."""
    slots = get_available_slots_for_week()
    
    if not slots:
        await update.message.reply_text(
            "😔 На ближайшую неделю нет свободных слотов. "
            "Вы можете написать администратору и мы подберем другое время!"
        )
        return
    
    # Группируем слоты по датам
    slots_by_date = {}
    for slot in slots:
        date = slot['date']
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)
    
    # Формируем сообщение
    message = "📅 **Доступные слоты на неделю:**\n\n"
    
    for date, day_slots in slots_by_date.items():
        # Преобразуем дату в читаемый формат
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        date_str = date_obj.strftime('%d.%m.%Y (%A)')
        message += f"*{date_str}:*\n"
        
        for slot in day_slots:
            message += f"  • {slot['time']} - {slot['mc_name']} ({slot['price']} руб.)\n"
        message += "\n"
    
    message += "Для записи напишите администратору: @sergeynnn03"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# --- ФУНКЦИИ ДЛЯ ТОВАРОВ ---
async def show_product_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории товаров."""
    reply_keyboard = [
        ["🍽 Тарелки", "☕️ Чашки"],
        ["🏺 Вазы", "💍 Украшения"],
        ["Назад в главное меню"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите категорию товаров:",
        reply_markup=markup
    )

async def show_products_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    """Показывает товары в выбранной категории."""
    products = get_products_by_category(category)
    
    if not products:
        await update.message.reply_text(
            f"В категории '{category}' пока нет товаров. Загляните позже!"
        )
        return
    
    # Пока показываем просто списком, позже добавим листание с фото
    message = f"📦 **Товары в категории {category}:**\n\n"
    for product in products:
        message += f"• {product['description']}\n  Цена: {product['price']} руб.\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# --- АДМИН-ПАНЕЛЬ ---
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает панель администратора."""
    reply_keyboard = [
        ["📋 Все записи", "➕ Добавить запись"],
        ["📦 Товары", "➕ Добавить товар"],
        ["📊 Статистика"],
        ["Назад в главное меню"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🔧 Панель администратора\n\n"
        "Выберите действие:",
        reply_markup=markup
    )

# --- ОСНОВНАЯ ФУНКЦИЯ ---
def main():
    """Запускает бота."""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот с базой данных запущен и готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()