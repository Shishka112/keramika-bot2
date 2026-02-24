# reminder.py
# Отправка напоминаний о предстоящих мастер-классах

from database import get_connection
from datetime import datetime, timedelta
import logging
import asyncio
import threading
import time

logger = logging.getLogger(__name__)

class ReminderSystem:
    def __init__(self, bot_app):
        self.bot_app = bot_app
        self.running = False
        self.thread = None
    
    def check_and_send_reminders(self):
        """Проверяет предстоящие мастер-классы и отправляет напоминания."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Ищем подтвержденные записи на завтра
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            tomorrow_str = tomorrow.isoformat()
            
            cursor.execute('''
                SELECT b.*, s.date, s.time, mc.name as mc_name, u.user_id, u.first_name
                FROM bookings b
                JOIN schedule s ON b.schedule_id = s.id
                JOIN master_classes mc ON b.mc_id = mc.id
                JOIN users u ON b.user_id = u.user_id
                WHERE s.date = ? AND b.status = 'confirmed' AND b.reminder_sent = 0
            ''', (tomorrow_str,))
            
            bookings = cursor.fetchall()
            
            # Отправляем напоминания
            for booking in bookings:
                try:
                    # Формируем время для отправки (в 9 утра предыдущего дня)
                    send_time = datetime.strptime(f"{tomorrow_str} 09:00", '%Y-%m-%d %H:%M')
                    now = datetime.now()
                    
                    if now >= send_time:
                        people_text = ""
                        if "+" in booking['user_name']:
                            people_count = booking['user_name'].split('+')[1].strip()
                            people_text = f" (на {people_count})"
                        
                        # Создаем задачу для отправки в главном цикле бота
                        asyncio.run_coroutine_threadsafe(
                            self.bot_app.bot.send_message(
                                chat_id=booking['user_id'],
                                text=f"🔔 **НАПОМИНАНИЕ**\n\n"
                                     f"Завтра в {booking['time']} у вас мастер-класс:\n"
                                     f"🎨 {booking['mc_name']}{people_text}\n\n"
                                     f"Ждем вас в мастерской! 🏺\n"
                                     f"📍 Адрес: уточните у администратора\n"
                                     f"❗️ Не забудьте, в мастерской живут кошки",
                                parse_mode='Markdown'
                            ),
                            self.bot_app.loop
                        )
                        
                        # Отмечаем, что напоминание отправлено
                        cursor.execute(
                            "UPDATE bookings SET reminder_sent = 1 WHERE id = ?",
                            (booking['id'],)
                        )
                        conn.commit()
                        
                        logger.info(f"✅ Напоминание отправлено пользователю {booking['user_id']}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания: {e}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Ошибка в check_and_send_reminders: {e}")
    
    def start(self):
        """Запускает систему напоминаний."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._reminder_loop, daemon=True)
        self.thread.start()
        logger.info("✅ Система напоминаний запущена")
        print("🔔 Напоминания о мастер-классах запущены")
    
    def _reminder_loop(self):
        """Фоновый цикл проверки напоминаний."""
        while self.running:
            self.check_and_send_reminders()
            time.sleep(3600)  # Проверяем каждый час
    
    def stop(self):
        """Останавливает систему напоминаний."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹ Система напоминаний остановлена")