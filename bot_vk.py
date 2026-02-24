# bot_vk.py
# Бот для ВКонтакте с записью на мастер-классы и каталогом товаров

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from database import *
from google_calendar import calendar_manager
from datetime import datetime, timedelta
import logging

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен ВК (получить на https://vkhost.github.io/)
VK_TOKEN = "vk1.a.SwHJLz7p_-bT5NegVnK1lmcxdlrnJjR38Yz19-Ra7YVxMjEXrvT8oPlbOHCD5TsmO51LaXkD_MtBpsdqeO387JvaZv1xoBmmsEhGs55rSpBMKwvnobkTtu1ishmiUbKgUxqEbU5kdPukRZIVtKZj3J_q6bdiCJypVHmT2Uwy9nIi1Dq4QtV8Lt4gmRx3iKraGTrrAk7E7fkhjAGu-M9PSg"  # <--- ВСТАВЬТЕ СВОЙ ТОКЕН!

# ID группы ВК (отрицательное число)
GROUP_ID = -236121175  # <--- ВСТАВЬТЕ ID СВОЕЙ ГРУППЫ!

# ID администратора ВК
ADMIN_VK_ID = 182718420  # <--- ВСТАВЬТЕ СВОЙ VK ID!

# Состояния пользователей
user_states = {}
user_data = {}

# Состояния для различных процессов
STATE_MAIN_MENU = 0
STATE_CHOOSING_MC = 1
STATE_CHOOSING_DATE = 2
STATE_ENTERING_PEOPLE_COUNT = 3
STATE_ADDING_PRODUCT_CATEGORY = 4
STATE_ADDING_PRODUCT_PHOTO = 5
STATE_ADDING_PRODUCT_DESCRIPTION = 6
STATE_ADDING_PRODUCT_PRICE = 7
STATE_ADDING_SLOTS = 8

# --- Функции для работы с клавиатурами ---

def get_main_keyboard(is_admin=False):
    """Возвращает главную клавиатуру."""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Заказать изделие", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Мастер-класс", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("📋 Мои записи", color=VkKeyboardColor.SECONDARY)
    
    if is_admin:
        keyboard.add_line()
        keyboard.add_button("🔧 Админ-панель", color=VkKeyboardColor.NEGATIVE)
    
    return keyboard

def get_order_keyboard():
    """Возвращает клавиатуру для заказа изделий."""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Посмотреть наличие", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Сделать заказ по референсу", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("◀️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_categories_keyboard():
    """Возвращает клавиатуру с категориями товаров."""
    counts = get_products_count()
    count_dict = {row['category']: row['count'] for row in counts}
    
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button(f"🍽 Тарелки ({count_dict.get('Тарелки', 0)})", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button(f"☕️ Чашки ({count_dict.get('Чашки', 0)})", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(f"🏺 Вазы ({count_dict.get('Вазы', 0)})", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button(f"💍 Украшения ({count_dict.get('Украшения', 0)})", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("◀️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_master_classes_keyboard():
    """Возвращает клавиатуру с мастер-классами."""
    mcs = get_all_master_classes()
    
    keyboard = VkKeyboard(one_time=False)
    for i, mc in enumerate(mcs):
        keyboard.add_button(mc['name'], color=VkKeyboardColor.PRIMARY)
        if i % 2 == 1:  # каждые 2 кнопки переносим строку
            keyboard.add_line()
    
    if len(mcs) % 2 == 1:
        keyboard.add_line()
    
    keyboard.add_button("📋 Мои записи", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("◀️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_mc_action_keyboard(mc_name):
    """Возвращает клавиатуру с действиями для выбранного МК."""
    keyboard = VkKeyboard(one_time=False)
    
    if mc_name in ["Групповой", "Школьный"]:
        keyboard.add_button("👥 Указать количество", color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
    
    keyboard.add_button("📅 Выбрать дату", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🎁 Заказать сертификат", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("❓ Доп. вопрос админу", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("◀️ Назад к МК", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🏠 Главное меню", color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def get_admin_keyboard():
    """Возвращает клавиатуру админ-панели."""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Неподтвержденные записи", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📅 Управление расписанием", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("📦 Управление товарами", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Статистика", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("📤 Экспорт данных", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("📅 Проверить календарь", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🔔 Статистика напоминаний", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("◀️ Назад", color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def get_schedule_management_keyboard():
    """Возвращает клавиатуру управления расписанием."""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("➕ Добавить слоты", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🗑 Удалить слот", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("📅 Показать все слоты", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Статистика расписания", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("📅 Создать слоты вручную", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("◀️ Назад в админку", color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def get_product_management_keyboard():
    """Возвращает клавиатуру управления товарами."""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("➕ Добавить товар", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("📦 Список товаров", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🗑 Удалить товар", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("✏️ Редактировать товар", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("◀️ Назад в админку", color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def get_cancel_keyboard():
    """Возвращает клавиатуру с кнопкой отмены."""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
    return keyboard

# --- Функции для отправки сообщений ---

def send_message(vk, user_id, message, keyboard=None, attachment=None):
    """Отправляет сообщение пользователю."""
    try:
        params = {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id()
        }
        
        if keyboard:
            params['keyboard'] = keyboard.get_keyboard()
        
        if attachment:
            params['attachment'] = attachment
        
        # ИСПРАВЛЕНО: правильный вызов метода
        vk.messages.send(**params)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

def send_photo(vk, user_id, photo_id, caption=None, keyboard=None):
    """Отправляет фото пользователю."""
    attachment = f"photo{photo_id}"
    send_message(vk, user_id, caption or "", keyboard, attachment)

def is_admin(user_id):
    """Проверяет, является ли пользователь админом."""
    return user_id == ADMIN_VK_ID

# --- Основная логика бота ---

def handle_start(vk, user_id):
    """Обрабатывает команду начала работы."""
    # Регистрируем пользователя
    register_user(
        user_id=str(user_id),
        platform='vk',
        first_name=get_user_name(vk, user_id),
        username=None
    )
    
    user_states[user_id] = STATE_MAIN_MENU
    keyboard = get_main_keyboard(is_admin(user_id))
    send_message(vk, user_id, 
        "Добрый день! 👋\n\n"
        "Это «Керамика Юноны». Вы хотите записаться на мастер-класс или заказать изделие?",
        keyboard
    )

def get_user_name(vk, user_id):
    """Получает имя пользователя ВК."""
    try:
        users = vk.users.get(user_ids=user_id)
        if users:
            return f"{users[0]['first_name']} {users[0]['last_name']}"
    except Exception as e:
        logger.error(f"Ошибка получения имени пользователя {user_id}: {e}")
    return "Пользователь ВК"

def handle_order_menu(vk, user_id):
    """Обрабатывает меню заказа изделий."""
    user_states[user_id] = STATE_MAIN_MENU
    keyboard = get_order_keyboard()
    send_message(vk, user_id, "Выберите действие:", keyboard)

def handle_product_categories(vk, user_id):
    """Показывает категории товаров."""
    user_states[user_id] = STATE_MAIN_MENU
    keyboard = get_categories_keyboard()
    send_message(vk, user_id, "Выберите категорию товаров:", keyboard)

def show_products_by_category(vk, user_id, category):
    """Показывает товары в категории."""
    products = get_products_by_category(category)
    
    if not products:
        send_message(vk, user_id, f"В категории '{category}' пока нет товаров. Загляните позже!")
        return
    
    for i, product in enumerate(products):
        text = f"📦 Товар {i+1} из {len(products)}\n\n"
        text += f"{product['description']}\n\n"
        text += f"💰 Цена: {product['price']} руб."
        
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button("🛒 Заказать", color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        keyboard.add_button("◀️ В категории", color=VkKeyboardColor.SECONDARY)
        
        if product['photo_id']:
            send_photo(vk, user_id, product['photo_id'], text, keyboard)
        else:
            send_message(vk, user_id, text, keyboard)
        
        # Сохраняем ID товара для заказа
        user_data[f"{user_id}_last_product"] = product['id']

def handle_master_classes_menu(vk, user_id):
    """Показывает меню мастер-классов."""
    user_states[user_id] = STATE_CHOOSING_MC
    keyboard = get_master_classes_keyboard()
    send_message(vk, user_id, "Выберите формат мастер-класса:", keyboard)

def handle_mc_selection(vk, user_id, mc_name):
    """Обрабатывает выбор мастер-класса."""
    mc = get_master_class_by_name(mc_name)
    if not mc:
        send_message(vk, user_id, "Мастер-класс не найден.")
        return
    
    user_data[f"{user_id}_current_mc"] = dict(mc)
    if f"{user_id}_people_count" in user_data:
        del user_data[f"{user_id}_people_count"]
    
    send_message(vk, user_id, mc['description'])
    
    keyboard = get_mc_action_keyboard(mc_name)
    send_message(vk, user_id, "Что хотите сделать?", keyboard)

def handle_people_count_start(vk, user_id):
    """Начинает ввод количества человек."""
    user_states[user_id] = STATE_ENTERING_PEOPLE_COUNT
    keyboard = get_cancel_keyboard()
    send_message(vk, user_id, 
        "👥 Введите количество человек, которые будут участвовать в мастер-классе:\n"
        "(например: 5, 10, 15)", keyboard)

def handle_people_count(vk, user_id, text):
    """Обрабатывает ввод количества человек."""
    try:
        count = int(text)
        if count <= 0 or count > 50:
            send_message(vk, user_id, "❌ Количество должно быть от 1 до 50. Попробуйте еще раз:")
            return
        
        user_data[f"{user_id}_people_count"] = count
        user_states[user_id] = STATE_CHOOSING_MC
        
        send_message(vk, user_id, f"✅ Количество сохранено: {count} человек(а)\n\nТеперь вы можете выбрать дату.")
        
        # Возвращаем в меню МК
        mc = user_data.get(f"{user_id}_current_mc")
        if mc:
            keyboard = get_mc_action_keyboard(mc['name'])
            send_message(vk, user_id, "Что хотите сделать?", keyboard)
        
    except ValueError:
        send_message(vk, user_id, "❌ Пожалуйста, введите число. Попробуйте еще раз:")

def show_week_schedule(vk, user_id):
    """Показывает расписание на неделю."""
    mc = user_data.get(f"{user_id}_current_mc")
    if not mc:
        send_message(vk, user_id, "Сначала выберите мастер-класс!")
        return
    
    # Проверяем, нужно ли указать количество
    if mc['name'] in ["Групповой", "Школьный"] and f"{user_id}_people_count" not in user_data:
        send_message(vk, user_id, 
            "👥 Пожалуйста, сначала укажите количество человек.\n"
            "Нажмите '👥 Указать количество'")
        return
    
    slots = get_available_slots_for_week()
    
    if not slots:
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button("✍️ Написать администратору", color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        keyboard.add_button("◀️ Назад", color=VkKeyboardColor.SECONDARY)
        send_message(vk, user_id, 
            f"😔 На ближайшую неделю нет свободных слотов.", keyboard)
        return
    
    # Группируем по датам
    slots_by_date = {}
    for slot in slots:
        date = slot['date']
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)
    
    message = f"📅 Расписание для {mc['name']} на неделю:\n\n"
    
    for date, day_slots in slots_by_date.items():
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        day_num = date_obj.weekday()
        date_str = date_obj.strftime(f'%d.%m.%Y ({days_ru[day_num]})')
        
        message += f"\n{date_str}:\n"
        for slot in day_slots:
            message += f"  • {slot['time']} — {mc['price']} руб.\n"
    
    message += "\nНапишите дату и время, на которые хотите записаться (например: 2024-01-20 15:00)"
    
    user_states[user_id] = STATE_CHOOSING_DATE
    keyboard = get_cancel_keyboard()
    send_message(vk, user_id, message, keyboard)

def handle_date_selection(vk, user_id, text):
    """Обрабатывает выбор даты и времени."""
    try:
        parts = text.strip().split()
        if len(parts) != 2:
            send_message(vk, user_id, "❌ Неверный формат. Используйте: ГГГГ-ММ-ДД ЧЧ:ММ")
            return
        
        date_str, time_str = parts
        datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        
        # Ищем свободный слот
        slots = get_available_slots_for_week()
        slot = next((s for s in slots if s['date'] == date_str and s['time'] == time_str), None)
        
        if not slot:
            send_message(vk, user_id, "❌ Этот слот недоступен. Пожалуйста, выберите из списка.")
            return
        
        mc = user_data.get(f"{user_id}_current_mc")
        people_count = user_data.get(f"{user_id}_people_count", 1)
        
        # Бронируем слот
        success, result = book_slot(
            slot['id'],
            mc['id'],
            str(user_id),
            f"{get_user_name(vk, user_id)}" + (f" (+{people_count} чел)" if people_count > 1 else ""),
            'vk'
        )
        
        if success:
            # Уведомляем админа
            try:
                send_message(vk, ADMIN_VK_ID,
                    f"🔔 Новая заявка на запись!\n\n"
                    f"Клиент: {get_user_name(vk, user_id)}\n"
                    f"МК: {mc['name']}\n"
                    f"Количество: {people_count}\n"
                    f"Дата: {date_str}\n"
                    f"Время: {time_str}\n\n"
                    f"Для подтверждения зайдите в админ-панель."
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления админа: {e}")
            
            people_text = f"\n👥 Количество человек: {people_count}" if people_count > 1 else ""
            send_message(vk, user_id, 
                f"✅ Заявка на запись отправлена!\n\n"
                f"Мастер-класс: {mc['name']}{people_text}\n"
                f"Дата: {date_str}\n"
                f"Время: {time_str}\n\n"
                "Администратор подтвердит вашу запись в ближайшее время.")
            
            user_states[user_id] = STATE_MAIN_MENU
            keyboard = get_main_keyboard(is_admin(user_id))
            send_message(vk, user_id, "Возвращаюсь в главное меню.", keyboard)
        else:
            send_message(vk, user_id, "❌ Произошла ошибка при записи. Попробуйте еще раз.")
            
    except ValueError:
        send_message(vk, user_id, "❌ Неверный формат даты/времени. Используйте: ГГГГ-ММ-ДД ЧЧ:ММ")

def show_user_bookings(vk, user_id):
    """Показывает записи пользователя."""
    bookings = get_user_bookings(str(user_id))
    
    if not bookings:
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button("📅 Записаться на МК", color=VkKeyboardColor.PRIMARY)
        send_message(vk, user_id, "У вас пока нет активных записей.", keyboard)
        return
    
    message = "📋 Ваши записи:\n\n"
    for booking in bookings:
        status_emoji = "⏳" if booking['status'] == 'pending' else "✅" if booking['status'] == 'confirmed' else "❌"
        people_text = ""
        if "+" in booking['user_name']:
            people_text = f" {booking['user_name'].split('+')[1].strip()}"
        
        message += f"{status_emoji} {booking['mc_name']}{people_text}\n"
        message += f"   📅 {booking['date']} в {booking['time']}\n"
        message += f"   Статус: {booking['status']}\n\n"
    
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("◀️ Назад", color=VkKeyboardColor.SECONDARY)
    send_message(vk, user_id, message, keyboard)

# --- Админ-функции ---

def show_admin_panel(vk, user_id):
    """Показывает панель администратора."""
    if not is_admin(user_id):
        return
    
    keyboard = get_admin_keyboard()
    send_message(vk, user_id, "🔧 Панель администратора\n\nВыберите действие:", keyboard)

def show_pending_bookings(vk, user_id):
    """Показывает неподтвержденные записи."""
    if not is_admin(user_id):
        return
    
    pending = get_pending_bookings()
    
    if not pending:
        send_message(vk, user_id, "✅ Нет неподтвержденных записей.")
        return
    
    for booking in pending:
        people_info = ""
        if "+" in booking['user_name']:
            people_info = f"\n👥 {booking['user_name'].split('+')[1].strip()}"
        
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button(f"✅ Подтвердить {booking['id']}", color=VkKeyboardColor.POSITIVE)
        keyboard.add_button(f"❌ Отклонить {booking['id']}", color=VkKeyboardColor.NEGATIVE)
        
        message = (
            f"🔔 Новая заявка\n\n"
            f"ID: {booking['id']}\n"
            f"Клиент: {booking['first_name']} {booking['last_name'] or ''}{people_info}\n"
            f"Username: {booking['username'] or 'нет'}\n"
            f"Платформа: {booking['platform']}\n"
            f"МК: {booking['mc_name']}\n"
            f"Дата: {booking['date']}\n"
            f"Время: {booking['time']}\n"
            f"Запись создана: {booking['created_at']}"
        )
        
        send_message(vk, user_id, message, keyboard)

def confirm_booking_vk(vk, user_id, booking_id):
    """Подтверждает запись."""
    if not is_admin(user_id):
        return
    
    confirm_booking(booking_id)
    
    # Уведомляем пользователя
    booking = get_booking_by_id(booking_id)
    if booking:
        try:
            send_message(vk, int(booking['user_id']),
                f"✅ Ваша запись подтверждена!\n\n"
                f"Мастер-класс: {booking['mc_name']}\n"
                f"Дата: {booking['date']}\n"
                f"Время: {booking['time']}\n\n"
                f"Ждем вас в мастерской! 🏺"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
    
    send_message(vk, user_id, f"✅ Запись {booking_id} подтверждена!")

def cancel_booking_vk(vk, user_id, booking_id):
    """Отменяет запись."""
    if not is_admin(user_id):
        return
    
    cancel_booking(booking_id)
    
    # Уведомляем пользователя
    booking = get_booking_by_id(booking_id)
    if booking:
        try:
            send_message(vk, int(booking['user_id']),
                f"❌ Запись отклонена\n\n"
                f"Мастер-класс: {booking['mc_name']}\n"
                f"Дата: {booking['date']}\n"
                f"Время: {booking['time']}\n\n"
                f"Пожалуйста, свяжитесь с администратором."
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
    
    send_message(vk, user_id, f"❌ Запись {booking_id} отклонена")

def show_schedule_management(vk, user_id):
    """Показывает меню управления расписанием."""
    if not is_admin(user_id):
        return
    
    keyboard = get_schedule_management_keyboard()
    send_message(vk, user_id, 
        "📅 Управление расписанием\n\n"
        "Автоматическое расписание:\n"
        "• Будни: 12:00, 18:00\n"
        "• Выходные: 12:00, 15:00, 18:00",
        keyboard
    )

def ask_for_slots(vk, user_id):
    """Запрашивает ввод слотов."""
    if not is_admin(user_id):
        return
    
    user_states[user_id] = STATE_ADDING_SLOTS
    keyboard = get_cancel_keyboard()
    send_message(vk, user_id, 
        "Введите дату и время для слотов в формате:\n"
        "ГГГГ-ММ-ДД ЧЧ:ММ\n"
        "Например: 2024-01-20 15:00\n\n"
        "Можно добавить несколько слотов, каждый с новой строки:", 
        keyboard
    )

def handle_adding_slots(vk, user_id, text):
    """Обрабатывает добавление слотов."""
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
                send_message(vk, user_id, f"❌ Неверный формат: {line}")
                continue
    
    send_message(vk, user_id, f"✅ Добавлено {added_count} новых слотов!")
    user_states[user_id] = STATE_MAIN_MENU

def show_all_slots(vk, user_id):
    """Показывает все будущие слоты."""
    if not is_admin(user_id):
        return
    
    slots = get_all_future_slots()
    
    if not slots:
        send_message(vk, user_id, "Нет будущих слотов.")
        return
    
    message = "📅 Все будущие слоты:\n\n"
    for slot in slots[:20]:
        status = "✅ свободен" if slot['is_available'] else "❌ занят"
        message += f"• {slot['date']} {slot['time']} ({status})\n"
    
    if len(slots) > 20:
        message += f"\n... и еще {len(slots) - 20} слотов"
    
    send_message(vk, user_id, message)

def show_schedule_stats(vk, user_id):
    """Показывает статистику расписания."""
    if not is_admin(user_id):
        return
    
    stats = get_slots_stats()
    
    message = "📊 СТАТИСТИКА РАСПИСАНИЯ\n\n"
    message += f"📅 Всего будущих слотов: {stats['total_future']}\n"
    message += f"✅ Свободно: {stats['total_available']}\n"
    message += f"❌ Занято: {stats['total_future'] - stats['total_available']}\n\n"
    
    message += "Ближайшие 14 дней:\n"
    for slot in stats['daily_stats']:
        date_obj = datetime.strptime(slot['date'], '%Y-%m-%d')
        date_str = date_obj.strftime('%d.%m.%Y')
        message += f"• {date_str}: {slot['slots']} слотов ({slot['available']} свободно)\n"
    
    send_message(vk, user_id, message)

def show_statistics(vk, user_id):
    """Показывает подробную статистику."""
    if not is_admin(user_id):
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE platform = 'vk'")
    vk_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'confirmed' AND platform = 'vk'")
    vk_confirmed = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'confirmed'")
    total_confirmed = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'pending' AND platform = 'vk'")
    vk_pending = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'pending'")
    total_pending = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM products")
    total_products = cursor.fetchone()['count']
    
    reminder_stats = get_reminder_stats()
    
    conn.close()
    
    message = "📊 СТАТИСТИКА ВК БОТА\n\n"
    
    message += "👥 Пользователи ВК:\n"
    message += f"• Всего: {vk_users}\n"
    message += f"• Из всех платформ: {total_users}\n\n"
    
    message += "📅 Записи на МК (ВК):\n"
    message += f"• Подтверждено: {vk_confirmed}\n"
    message += f"• Ожидают: {vk_pending}\n"
    message += f"• Всего по всем платформам: {total_confirmed + total_pending}\n\n"
    
    message += "📦 Товары:\n"
    message += f"• Всего: {total_products}\n\n"
    
    message += "🔔 Напоминания:\n"
    message += f"• Ожидают отправки: {reminder_stats['pending']}\n"
    message += f"• Отправлено всего: {reminder_stats['sent']}\n"
    
    send_message(vk, user_id, message)

def export_data(vk, user_id):
    """Экспортирует данные."""
    if not is_admin(user_id):
        return
    
    send_message(vk, user_id, "⏳ Формирую файлы... (функция в разработке для ВК)")

def check_calendar(vk, user_id):
    """Проверяет статус календаря."""
    if not is_admin(user_id):
        return
    
    if calendar_manager.service and calendar_manager.authenticated:
        send_message(vk, user_id, "✅ Google Calendar подключен и работает!")
    else:
        send_message(vk, user_id, 
            "❌ Google Calendar не подключен.\n"
            "Настройте его в Telegram боте.")

def show_reminder_stats(vk, user_id):
    """Показывает статистику напоминаний."""
    if not is_admin(user_id):
        return
    
    stats = get_reminder_stats()
    
    send_message(vk, user_id, 
        f"🔔 СТАТИСТИКА НАПОМИНАНИЙ\n\n"
        f"⏳ Ожидают отправки: {stats['pending']}\n"
        f"✅ Отправлено всего: {stats['sent']}")

# --- Основной цикл бота ---

def main():
    """Запускает бота ВКонтакте."""
    # Авторизация
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)
    
    print("🤖 ВК Бот запущен и готов к работе!")
    print(f"👤 ID администратора ВК: {ADMIN_VK_ID}")
    print("📝 Ожидаю сообщения...")
    
    # Основной цикл обработки сообщений
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text.lower()
            original_text = event.text
            
            # Получаем состояние пользователя
            state = user_states.get(user_id, STATE_MAIN_MENU)
            
            # Обработка команд
            if text == "начать" or text == "start" or text == "/start":
                handle_start(vk, user_id)
                continue
            
            if text == "❌ отмена":
                user_states[user_id] = STATE_MAIN_MENU
                keyboard = get_main_keyboard(is_admin(user_id))
                send_message(vk, user_id, "Операция отменена. Возвращаюсь в главное меню.", keyboard)
                continue
            
            # Обработка в зависимости от состояния
            if state == STATE_ENTERING_PEOPLE_COUNT:
                handle_people_count(vk, user_id, original_text)
                
            elif state == STATE_CHOOSING_DATE:
                handle_date_selection(vk, user_id, original_text)
                
            elif state == STATE_ADDING_SLOTS and is_admin(user_id):
                handle_adding_slots(vk, user_id, original_text)
                
            else:
                # Обработка команд меню
                if original_text == "Заказать изделие":
                    handle_order_menu(vk, user_id)
                    
                elif original_text == "Посмотреть наличие":
                    handle_product_categories(vk, user_id)
                    
                elif original_text.startswith("🍽 Тарелки") or original_text.startswith("☕️ Чашки") or \
                     original_text.startswith("🏺 Вазы") or original_text.startswith("💍 Украшения"):
                    category = original_text.split(" ")[1]
                    show_products_by_category(vk, user_id, category)
                    
                elif original_text == "Сделать заказ по референсу":
                    send_message(vk, user_id, 
                        "Для заказа по референсу свяжитесь с администратором.", 
                        get_main_keyboard(is_admin(user_id)))
                    
                elif original_text == "Мастер-класс":
                    handle_master_classes_menu(vk, user_id)
                    
                elif original_text in ["Индивидуальный", "Свидание", "Групповой", "Школьный"]:
                    handle_mc_selection(vk, user_id, original_text)
                    
                elif original_text == "👥 Указать количество":
                    handle_people_count_start(vk, user_id)
                    
                elif original_text == "📅 Выбрать дату":
                    show_week_schedule(vk, user_id)
                    
                elif original_text == "🎁 Заказать сертификат":
                    mc = user_data.get(f"{user_id}_current_mc")
                    if mc:
                        send_message(vk, user_id, 
                            f"Для заказа сертификата на '{mc['name']}' свяжитесь с администратором.",
                            get_main_keyboard(is_admin(user_id)))
                    else:
                        send_message(vk, user_id, "Сначала выберите мастер-класс!")
                        
                elif original_text == "❓ Доп. вопрос админу":
                    send_message(vk, user_id, 
                        "Задайте ваш вопрос администратору, написав ему лично.",
                        get_main_keyboard(is_admin(user_id)))
                        
                elif original_text == "📋 Мои записи":
                    show_user_bookings(vk, user_id)
                    
                elif original_text == "◀️ Назад":
                    handle_start(vk, user_id)
                    
                elif original_text == "◀️ Назад к МК":
                    mc = user_data.get(f"{user_id}_current_mc")
                    if mc:
                        handle_mc_selection(vk, user_id, mc['name'])
                    else:
                        handle_master_classes_menu(vk, user_id)
                        
                elif original_text == "🏠 Главное меню":
                    handle_start(vk, user_id)
                    
                # Админские команды
                elif original_text == "🔧 Админ-панель" and is_admin(user_id):
                    show_admin_panel(vk, user_id)
                    
                elif original_text == "📋 Неподтвержденные записи" and is_admin(user_id):
                    show_pending_bookings(vk, user_id)
                    
                elif original_text.startswith("✅ Подтвердить") and is_admin(user_id):
                    try:
                        parts = original_text.split()
                        if len(parts) >= 3:
                            booking_id = int(parts[2])
                            confirm_booking_vk(vk, user_id, booking_id)
                    except:
                        pass
                        
                elif original_text.startswith("❌ Отклонить") and is_admin(user_id):
                    try:
                        parts = original_text.split()
                        if len(parts) >= 3:
                            booking_id = int(parts[2])
                            cancel_booking_vk(vk, user_id, booking_id)
                    except:
                        pass
                        
                elif original_text == "📅 Управление расписанием" and is_admin(user_id):
                    show_schedule_management(vk, user_id)
                    
                elif original_text == "➕ Добавить слоты" and is_admin(user_id):
                    ask_for_slots(vk, user_id)
                    
                elif original_text == "📅 Показать все слоты" and is_admin(user_id):
                    show_all_slots(vk, user_id)
                    
                elif original_text == "📊 Статистика расписания" and is_admin(user_id):
                    show_schedule_stats(vk, user_id)
                    
                elif original_text == "📅 Создать слоты вручную" and is_admin(user_id):
                    from auto_schedule import auto_scheduler
                    added = auto_scheduler.create_default_slots()
                    send_message(vk, user_id, f"✅ Добавлено {added} новых слотов!")
                    
                elif original_text == "📦 Управление товарами" and is_admin(user_id):
                    keyboard = get_product_management_keyboard()
                    send_message(vk, user_id, "📦 Управление товарами", keyboard)
                    
                elif original_text == "➕ Добавить товар" and is_admin(user_id):
                    user_states[user_id] = STATE_ADDING_PRODUCT_CATEGORY
                    keyboard = VkKeyboard(one_time=True)
                    keyboard.add_button("🍽 Тарелки", color=VkKeyboardColor.PRIMARY)
                    keyboard.add_button("☕️ Чашки", color=VkKeyboardColor.PRIMARY)
                    keyboard.add_line()
                    keyboard.add_button("🏺 Вазы", color=VkKeyboardColor.PRIMARY)
                    keyboard.add_button("💍 Украшения", color=VkKeyboardColor.PRIMARY)
                    keyboard.add_line()
                    keyboard.add_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE)
                    send_message(vk, user_id, "Выберите категорию товара:", keyboard)
                    
                elif original_text == "📦 Список товаров" and is_admin(user_id):
                    products = get_all_products()
                    if not products:
                        send_message(vk, user_id, "📦 В каталоге нет товаров.")
                    else:
                        message = "📦 Все товары:\n\n"
                        for product in products:
                            message += f"• ID: {product['id']} | {product['category']}\n"
                            message += f"  {product['description'][:50]}...\n"
                            message += f"  💰 {product['price']} руб.\n\n"
                        send_message(vk, user_id, message)
                        
                elif original_text == "📊 Статистика" and is_admin(user_id):
                    show_statistics(vk, user_id)
                    
                elif original_text == "📤 Экспорт данных" and is_admin(user_id):
                    export_data(vk, user_id)
                    
                elif original_text == "📅 Проверить календарь" and is_admin(user_id):
                    check_calendar(vk, user_id)
                    
                elif original_text == "🔔 Статистика напоминаний" and is_admin(user_id):
                    show_reminder_stats(vk, user_id)
                    
                elif original_text == "◀️ Назад в админку" and is_admin(user_id):
                    show_admin_panel(vk, user_id)
                    
                elif original_text == "🛒 Заказать":
                    product_id = user_data.get(f"{user_id}_last_product")
                    if product_id:
                        send_message(vk, user_id, 
                            "Для заказа товара свяжитесь с администратором.",
                            get_main_keyboard(is_admin(user_id)))
                        
                elif original_text == "◀️ В категории":
                    handle_product_categories(vk, user_id)
                    
                else:
                    keyboard = get_main_keyboard(is_admin(user_id))
                    send_message(vk, user_id, 
                        "Я не понимаю эту команду. Пожалуйста, пользуйтесь кнопками.",
                        keyboard)

if __name__ == "__main__":
    main()