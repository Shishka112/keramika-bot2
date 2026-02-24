# database.py
# Этот файл отвечает за связь с базой данных

import sqlite3
import os
from datetime import datetime, timedelta

# Имя файла базы данных
DB_NAME = 'bot_database.db'

# --- Функция для получения соединения с базой ---
def get_connection():
    """Создает и возвращает соединение с базой данных."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- Функция для создания всех таблиц ---
def create_tables():
    """Создает таблицы в базе данных, если их еще нет."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица для товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            photo_id TEXT,
            photo_file_id TEXT,
            description TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица для мастер-классов (виды МК)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS master_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL,
            duration INTEGER DEFAULT 90
        )
    ''')
    
    # Таблица для расписания (слоты для записи)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            is_available BOOLEAN DEFAULT TRUE,
            UNIQUE(date, time)
        )
    ''')
    
    # Таблица для записей клиентов (ДОБАВЛЕНО ПОЛЕ reminder_sent)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL,
            mc_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            event_id TEXT,
            reminder_sent INTEGER DEFAULT 0,  -- 0 - не отправлено, 1 - отправлено
            FOREIGN KEY (schedule_id) REFERENCES schedule (id),
            FOREIGN KEY (mc_id) REFERENCES master_classes (id)
        )
    ''')
    
    # Таблица для клиентов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Таблицы в базе данных созданы (или уже существовали)")

# --- Функции для работы с мастер-классами ---
def add_master_class(name, description, price, duration=90):
    """Добавляет новый вид мастер-класса."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO master_classes (name, description, price, duration) VALUES (?, ?, ?, ?)",
        (name, description, price, duration)
    )
    conn.commit()
    mc_id = cursor.lastrowid
    conn.close()
    return mc_id

def get_all_master_classes():
    """Возвращает список всех мастер-классов."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM master_classes")
    mcs = cursor.fetchall()
    conn.close()
    return mcs

def get_master_class_by_name(name):
    """Ищет мастер-класс по имени."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM master_classes WHERE name = ?", (name,))
    mc = cursor.fetchone()
    conn.close()
    return mc

def get_master_class_by_id(mc_id):
    """Возвращает мастер-класс по ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM master_classes WHERE id = ?", (mc_id,))
    mc = cursor.fetchone()
    conn.close()
    return mc

# --- Функции для работы с расписанием ---
def add_schedule_slots_bulk(date_str, times_list):
    """
    Добавляет несколько слотов в указанную дату.
    Слоты теперь общие для всех МК!
    times_list - список времени, например ['12:00', '15:00', '18:00']
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    added_count = 0
    for time_str in times_list:
        try:
            cursor.execute(
                "INSERT INTO schedule (date, time, is_available) VALUES (?, ?, 1)",
                (date_str, time_str)
            )
            added_count += 1
        except sqlite3.IntegrityError:
            # Слот с таким временем уже существует
            continue
    
    conn.commit()
    conn.close()
    return added_count

def get_available_slots_for_week():
    """
    Возвращает все доступные слоты на неделю вперед.
    """
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=7)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM schedule
        WHERE date BETWEEN ? AND ? 
          AND is_available = 1
        ORDER BY date, time
    ''', (start_date.isoformat(), end_date.isoformat()))
    slots = cursor.fetchall()
    conn.close()
    return slots

def get_slots_by_date(date_str):
    """Возвращает все слоты на указанную дату."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM schedule
        WHERE date = ?
        ORDER BY time
    ''', (date_str,))
    slots = cursor.fetchall()
    conn.close()
    return slots

def get_slot_by_id(slot_id):
    """Возвращает информацию о слоте по его ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM schedule WHERE id = ?
    ''', (slot_id,))
    slot = cursor.fetchone()
    conn.close()
    return slot

def delete_slot(slot_id):
    """Удаляет слот из расписания."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM bookings WHERE schedule_id = ? AND status != 'cancelled'", (slot_id,))
    if cursor.fetchone():
        conn.close()
        return False, "Нельзя удалить слот, на который есть записи"
    
    cursor.execute("DELETE FROM schedule WHERE id = ?", (slot_id,))
    conn.commit()
    conn.close()
    return True, "Слот удален"

def get_all_future_slots():
    """Возвращает все будущие слоты."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM schedule
        WHERE date >= date('now')
        ORDER BY date, time
    ''')
    slots = cursor.fetchall()
    conn.close()
    return slots

def get_slots_stats():
    """Возвращает статистику по слотам."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM schedule WHERE date >= date('now')")
    total_future = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM schedule WHERE date >= date('now') AND is_available = 1")
    total_available = cursor.fetchone()['total']
    
    cursor.execute('''
        SELECT date, COUNT(*) as slots, 
               SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available
        FROM schedule 
        WHERE date >= date('now') AND date < date('now', '+14 days')
        GROUP BY date
        ORDER BY date
    ''')
    daily_stats = cursor.fetchall()
    
    conn.close()
    return {
        'total_future': total_future,
        'total_available': total_available,
        'daily_stats': daily_stats
    }

# --- Функции для работы с записями ---
def book_slot(schedule_id, mc_id, user_id, user_name, platform):
    """Бронирует слот для пользователя с указанием выбранного МК."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_available FROM schedule WHERE id = ?", (schedule_id,))
    slot = cursor.fetchone()
    
    if not slot or not slot['is_available']:
        conn.close()
        return False, "Слот уже занят"
    
    cursor.execute('''
        INSERT INTO bookings (schedule_id, mc_id, user_id, user_name, platform, status, reminder_sent)
        VALUES (?, ?, ?, ?, ?, 'pending', 0)
    ''', (schedule_id, mc_id, user_id, user_name, platform))
    
    cursor.execute("UPDATE schedule SET is_available = 0 WHERE id = ?", (schedule_id,))
    
    conn.commit()
    booking_id = cursor.lastrowid
    conn.close()
    return True, booking_id

def confirm_booking(booking_id):
    """Подтверждает запись (админом)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET status = 'confirmed' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()

def cancel_booking(booking_id):
    """Отменяет запись и освобождает слот."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT schedule_id FROM bookings WHERE id = ?", (booking_id,))
    booking = cursor.fetchone()
    
    if booking:
        cursor.execute("UPDATE schedule SET is_available = 1 WHERE id = ?", (booking['schedule_id'],))
        cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    
    conn.commit()
    conn.close()

def get_pending_bookings():
    """Возвращает все неподтвержденные записи."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.*, s.date, s.time, mc.name as mc_name, mc.price,
               u.first_name, u.last_name, u.username, u.platform
        FROM bookings b
        JOIN schedule s ON b.schedule_id = s.id
        JOIN master_classes mc ON b.mc_id = mc.id
        JOIN users u ON b.user_id = u.user_id
        WHERE b.status = 'pending'
        ORDER BY s.date, s.time
    ''')
    bookings = cursor.fetchall()
    conn.close()
    return bookings

def get_user_bookings(user_id):
    """Возвращает все записи пользователя."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.*, s.date, s.time, mc.name as mc_name, mc.price
        FROM bookings b
        JOIN schedule s ON b.schedule_id = s.id
        JOIN master_classes mc ON b.mc_id = mc.id
        WHERE b.user_id = ? AND b.status != 'cancelled'
        ORDER BY s.date DESC
    ''', (user_id,))
    bookings = cursor.fetchall()
    conn.close()
    return bookings

def get_booking_by_id(booking_id):
    """Возвращает запись по ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.*, s.date, s.time, mc.name as mc_name, mc.price, u.username, u.first_name
        FROM bookings b
        JOIN schedule s ON b.schedule_id = s.id
        JOIN master_classes mc ON b.mc_id = mc.id
        JOIN users u ON b.user_id = u.user_id
        WHERE b.id = ?
    ''', (booking_id,))
    booking = cursor.fetchone()
    conn.close()
    return booking

def update_booking_event_id(booking_id, event_id):
    """Сохраняет ID события Google Calendar для записи."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE bookings SET event_id = ? WHERE id = ?",
        (event_id, booking_id)
    )
    conn.commit()
    conn.close()

def get_reminder_stats():
    """Возвращает статистику по напоминаниям."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as count 
        FROM bookings b
        JOIN schedule s ON b.schedule_id = s.id
        WHERE s.date = date('now', '+1 day') 
          AND b.status = 'confirmed' 
          AND b.reminder_sent = 0
    ''')
    pending = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT COUNT(*) as count 
        FROM bookings 
        WHERE reminder_sent = 1
    ''')
    sent = cursor.fetchone()['count']
    
    conn.close()
    return {'pending': pending, 'sent': sent}

# --- Функции для работы с пользователями ---
def register_user(user_id, platform, first_name, last_name=None, username=None):
    """Регистрирует или обновляет информацию о пользователе."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, platform, first_name, last_name, username)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, platform, first_name, last_name, username))
    conn.commit()
    conn.close()

# --- Функции для управления товарами ---
def add_product(category, description, price, photo_id=None):
    """Добавляет новый товар в базу."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (category, description, price, photo_id) VALUES (?, ?, ?, ?)",
        (category, description, price, photo_id)
    )
    conn.commit()
    product_id = cursor.lastrowid
    conn.close()
    return product_id

def get_products_by_category(category):
    """Возвращает все товары из указанной категории."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM products WHERE category = ? ORDER BY created_at DESC",
        (category,)
    )
    products = cursor.fetchall()
    conn.close()
    return products

def get_all_products():
    """Возвращает все товары из всех категорий."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY category, created_at DESC")
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    """Возвращает товар по его ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def update_product(product_id, category, description, price, photo_id=None):
    """Обновляет информацию о товаре."""
    conn = get_connection()
    cursor = conn.cursor()
    if photo_id:
        cursor.execute(
            "UPDATE products SET category = ?, description = ?, price = ?, photo_id = ? WHERE id = ?",
            (category, description, price, photo_id, product_id)
        )
    else:
        cursor.execute(
            "UPDATE products SET category = ?, description = ?, price = ? WHERE id = ?",
            (category, description, price, product_id)
        )
    conn.commit()
    conn.close()
    return True

def delete_product(product_id):
    """Удаляет товар по его ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return True

def get_products_count():
    """Возвращает количество товаров в каждой категории."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM products 
        GROUP BY category
    ''')
    counts = cursor.fetchall()
    conn.close()
    return counts

if __name__ == "__main__":
    create_tables()
    print("База данных готова к работе!")