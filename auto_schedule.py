# auto_schedule.py
# Автоматическое создание слотов расписания

from database import add_schedule_slots_bulk
from datetime import datetime, timedelta
import logging
import time
import threading

# Пытаемся импортировать schedule, если не получается - используем заглушку
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    print("⚠️ Библиотека 'schedule' не установлена. Автоматическое расписание будет работать ограниченно.")
    print("   Установите: pip install schedule")

logger = logging.getLogger(__name__)

class AutoScheduler:
    def __init__(self):
        self.running = False
        self.thread = None
        self.schedule_available = SCHEDULE_AVAILABLE
    
    def create_default_slots(self):
        """Создает слоты по умолчанию на 14 дней вперед."""
        try:
            start_date = datetime.now().date()
            
            # Базовое расписание
            base_times = ['12:00', '18:00']
            weekend_times = ['12:00', '15:00', '18:00']
            
            total_added = 0
            for day in range(14):  # На 14 дней вперед
                current_date = start_date + timedelta(days=day)
                date_str = current_date.isoformat()
                weekday = current_date.weekday()
                
                # Выбираем время в зависимости от дня недели
                if weekday >= 5:  # Суббота и воскресенье
                    times = weekend_times
                else:
                    times = base_times
                
                # Добавляем слоты (теперь они общие, без привязки к МК)
                added = add_schedule_slots_bulk(date_str, times)
                total_added += added
            
            if total_added > 0:
                logger.info(f"✅ Автоматически добавлено {total_added} новых слотов")
            return total_added
            
        except Exception as e:
            logger.error(f"Ошибка в create_default_slots: {e}")
            return 0
    
    def run_daily_check(self):
        """Запускает ежедневную проверку и добавление слотов."""
        logger.info("🔄 Запущена ежедневная проверка расписания")
        self.create_default_slots()
    
    def start_scheduler(self):
        """Запускает фоновый поток с планировщиком."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        
        if self.schedule_available:
            logger.info("✅ Автоматическое планирование слотов запущено")
            print("📅 Автоматическое расписание запущено (слоты на 14 дней вперед)")
        else:
            logger.info("⚠️ Автоматическое планирование запущено в упрощенном режиме")
            print("📅 Автоматическое расписание запущено в упрощенном режиме (без schedule)")
    
    def _scheduler_loop(self):
        """Фоновый цикл планировщика."""
        # Создаем слоты при запуске
        self.create_default_slots()
        
        if self.schedule_available:
            # Полноценный режим с schedule
            import schedule
            schedule.every().day.at("00:01").do(self.run_daily_check)
            schedule.every().day.at("12:00").do(self.run_daily_check)
            
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
        else:
            # Упрощенный режим - проверяем каждый час
            last_check = datetime.now().date()
            while self.running:
                current_date = datetime.now().date()
                # Проверяем раз в день (если день изменился)
                if current_date > last_check:
                    self.run_daily_check()
                    last_check = current_date
                time.sleep(3600)  # Спим час
    
    def stop_scheduler(self):
        """Останавливает планировщик."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹ Планировщик остановлен")

# Создаем глобальный экземпляр
auto_scheduler = AutoScheduler()