# add_slots.py
from database import add_schedule_slots_bulk
from datetime import datetime, timedelta

print("🚀 ПЕРВОНАЧАЛЬНОЕ ЗАПОЛНЕНИЕ СЛОТОВ")
print("=" * 60)
print("ВНИМАНИЕ: Этот скрипт нужно запустить только ОДИН раз!")
print("Далее слоты будут создаваться автоматически каждый день.")
print("=" * 60)

# Создаем слоты на ближайшие 14 дней
start_date = datetime.now().date()

# Базовое расписание
base_times = ['12:00', '18:00']
weekend_times = ['12:00', '15:00', '18:00']

total_added = 0
for day in range(14):
    current_date = start_date + timedelta(days=day)
    date_str = current_date.isoformat()
    weekday = current_date.weekday()
    
    days_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    if weekday >= 5:
        times = weekend_times
    else:
        times = base_times
    
    print(f"\n📅 {days_ru[weekday]} ({date_str}):")
    
    added = add_schedule_slots_bulk(date_str, times)
    print(f"  ✅ Добавлено {added} слотов: {', '.join(times)}")
    total_added += added

print("\n" + "=" * 60)
print(f"✨ Готово! Добавлено {total_added} слотов.")
print("📅 Теперь бот будет автоматически создавать слоты каждый день!")
print("✅ Слоты общие для всех мастер-классов - если время занято, оно занято для всех!")