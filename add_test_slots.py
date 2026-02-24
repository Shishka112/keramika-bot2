# add_slots.py
from database import add_schedule_slots_bulk, get_all_master_classes
from datetime import datetime, timedelta

# Получаем все мастер-классы
mcs = get_all_master_classes()
mc_dict = {mc['name']: mc['id'] for mc in mcs}

# Создаем слоты на ближайшие 7 дней
start_date = datetime.now().date()

# Расписание на неделю: чередуем разные МК
schedule_plan = {
    0: [  # Понедельник
        ('12:00', 'Индивидуальный'),
        ('18:00', 'Свидание')
    ],
    1: [  # Вторник
        ('12:00', 'Групповой'),
        ('18:00', 'Индивидуальный')
    ],
    2: [  # Среда
        ('12:00', 'Школьный'),
        ('18:00', 'Свидание')
    ],
    3: [  # Четверг
        ('12:00', 'Индивидуальный'),
        ('18:00', 'Групповой')
    ],
    4: [  # Пятница
        ('12:00', 'Свидание'),
        ('18:00', 'Индивидуальный')
    ],
    5: [  # Суббота
        ('12:00', 'Школьный'),
        ('15:00', 'Индивидуальный'),
        ('18:00', 'Свидание')
    ],
    6: [  # Воскресенье
        ('12:00', 'Групповой'),
        ('15:00', 'Индивидуальный')
    ]
}

print("Добавляем слоты на неделю:")

for day in range(7):
    current_date = start_date + timedelta(days=day)
    date_str = current_date.isoformat()
    weekday = current_date.weekday()
    
    if weekday in schedule_plan:
        for time_str, mc_name in schedule_plan[weekday]:
            mc_id = mc_dict.get(mc_name)
            if mc_id:
                added = add_schedule_slots_bulk(mc_id, date_str, [time_str])
                if added:
                    print(f"  {date_str} {time_str}: {mc_name}")

print("\n✅ Слоты добавлены!")