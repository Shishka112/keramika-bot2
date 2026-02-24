# google_calendar.py
# Интеграция с Google Calendar API

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import pickle
import datetime
from datetime import timedelta
import logging
import webbrowser
import time

logger = logging.getLogger(__name__)

# Если изменяете эти scope, удалите файл token.pickle
SCOPES = ['https://www.googleapis.com/auth/calendar']

# ID вашего календаря (можно использовать 'primary' для основного календаря)
CALENDAR_ID = 'primary'

class GoogleCalendarManager:
    def __init__(self):
        self.creds = None
        self.service = None
        self.authenticated = False
        # Не вызываем authenticate автоматически, чтобы бот запускался без календаря
    
    def authenticate(self):
        """Аутентификация и получение сервиса Google Calendar."""
        try:
            # Файл с токеном сохраняем после первой авторизации
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    self.creds = pickle.load(token)
            
            # Если нет действительных credentials, авторизуемся
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    # Проверяем наличие файла credentials.json
                    if not os.path.exists('credentials.json'):
                        logger.error("Файл credentials.json не найден!")
                        print("\n" + "="*60)
                        print("❌ ОШИБКА: Файл credentials.json не найден!")
                        print("="*60)
                        print("\nИнструкция по настройке Google Calendar:")
                        print("1. Перейдите на https://console.cloud.google.com/")
                        print("2. Создайте новый проект")
                        print("3. Включите Google Calendar API")
                        print("4. Создайте credentials (OAuth 2.0 Client ID)")
                        print("5. Скачайте файл и переименуйте в credentials.json")
                        print("6. Поместите файл в папку с ботом")
                        print("\nПосле этого запустите бота снова")
                        print("="*60 + "\n")
                        return False
                    
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            'credentials.json', SCOPES)
                        
                        # Пробуем разные способы запуска сервера
                        try:
                            self.creds = flow.run_local_server(
                                host='localhost',
                                port=8080,
                                authorization_prompt_message='',
                                success_message='Авторизация успешна! Можно закрыть это окно.',
                                open_browser=True
                            )
                        except:
                            # Если не получается, пробуем альтернативный метод
                            self.creds = flow.run_local_server(port=0)
                            
                    except Exception as e:
                        logger.error(f"Ошибка при запуске локального сервера: {e}")
                        print(f"\n❌ Ошибка авторизации: {e}")
                        print("\nПопробуйте альтернативный способ:")
                        print("1. Удалите папку __pycache__ если есть")
                        print("2. Убедитесь, что порт 8080 не занят")
                        print("3. Попробуйте запустить бота снова")
                        return False
                
                # Сохраняем credentials для будущих запусков
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)
            
            self.service = build('calendar', 'v3', credentials=self.creds)
            self.authenticated = True
            logger.info("✅ Google Calendar авторизация успешна")
            print("\n✅ Google Calendar успешно подключен!")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка авторизации Google Calendar: {e}")
            print(f"\n❌ Ошибка авторизации Google Calendar: {e}")
            return False
    
    def ensure_authenticated(self):
        """Проверяет и обновляет аутентификацию при необходимости."""
        if not self.service or not self.authenticated:
            return self.authenticate()
        return True
    
    def add_event(self, summary, description, start_time, end_time, attendees=None):
        """
        Добавляет событие в календарь.
        
        Args:
            summary: Название события
            description: Описание
            start_time: datetime начала
            end_time: datetime окончания
            attendees: список email участников (опционально)
        
        Returns:
            ID созданного события или None
        """
        try:
            if not self.ensure_authenticated():
                logger.warning("Невозможно добавить событие: нет аутентификации")
                return None
            
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Europe/Moscow',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Europe/Moscow',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 60},
                        {'method': 'popup', 'minutes': 1440},  # за 1 день
                    ],
                },
                'colorId': '2',  # Зеленый цвет для мастер-классов
            }
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            event = self.service.events().insert(
                calendarId=CALENDAR_ID, 
                body=event
            ).execute()
            
            logger.info(f"✅ Событие создано: {event.get('htmlLink')}")
            return event.get('id')
            
        except HttpError as error:
            logger.error(f"Ошибка Google Calendar API: {error}")
            return None
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {e}")
            return None
    
    def add_master_class_event(self, mc_name, client_name, client_username, date_str, time_str):
        """
        Добавляет событие мастер-класса в календарь.
        
        Args:
            mc_name: Название мастер-класса
            client_name: Имя клиента
            client_username: Username клиента
            date_str: Дата в формате YYYY-MM-DD
            time_str: Время в формате HH:MM
        
        Returns:
            ID созданного события или None
        """
        try:
            # Парсим дату и время
            start_datetime = datetime.datetime.strptime(
                f"{date_str} {time_str}", 
                '%Y-%m-%d %H:%M'
            )
            
            # Длительность МК (по умолчанию 1.5 часа)
            duration_hours = 1.5
            end_datetime = start_datetime + timedelta(hours=duration_hours)
            
            # Формируем название и описание
            summary = f"🎨 {mc_name} - {client_name}"
            
            description = (
                f"Мастер-класс: {mc_name}\n"
                f"Клиент: {client_name}\n"
                f"Telegram: @{client_username}\n"
                f"Дата: {date_str}\n"
                f"Время: {time_str}\n"
                f"Длительность: {duration_hours} часа\n\n"
                f"Подготовить:\n"
                f"✅ Глину\n"
                f"✅ Инструменты\n"
                f"✅ Фартук\n"
                f"✅ Полотенце\n\n"
                f"❗️ В мастерской живут кошки"
            )
            
            return self.add_event(summary, description, start_datetime, end_datetime)
            
        except Exception as e:
            logger.error(f"Ошибка создания события МК: {e}")
            return None
    
    def delete_event(self, event_id):
        """
        Удаляет событие из календаря.
        
        Args:
            event_id: ID события
        """
        try:
            if not self.ensure_authenticated():
                return False
            
            self.service.events().delete(
                calendarId=CALENDAR_ID, 
                eventId=event_id
            ).execute()
            
            logger.info(f"✅ Событие {event_id} удалено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления события: {e}")
            return False
    
    def update_event_status(self, event_id, status, client_contact):
        """
        Обновляет статус события (подтверждено/отменено).
        
        Args:
            event_id: ID события
            status: Статус ('confirmed' или 'cancelled')
            client_contact: Контакт клиента
        """
        try:
            if not self.ensure_authenticated():
                return False
            
            event = self.service.events().get(
                calendarId=CALENDAR_ID, 
                eventId=event_id
            ).execute()
            
            # Добавляем информацию о статусе в описание
            current_description = event.get('description', '')
            status_text = f"\n\n📌 Статус: {'✅ Подтверждено' if status == 'confirmed' else '❌ Отменено'}"
            
            event['description'] = current_description + status_text
            
            # Меняем цвет в зависимости от статуса
            if status == 'confirmed':
                event['colorId'] = '2'  # Зеленый
            else:
                event['colorId'] = '4'  # Красный для отмененных
            
            updated_event = self.service.events().update(
                calendarId=CALENDAR_ID,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"✅ Статус события {event_id} обновлен на {status}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return False
    
    def test_connection(self):
        """Тестирует соединение с Google Calendar."""
        try:
            if self.ensure_authenticated():
                # Пробуем получить список событий (тестовый запрос)
                now = datetime.datetime.utcnow().isoformat() + 'Z'
                events_result = self.service.events().list(
                    calendarId=CALENDAR_ID,
                    timeMin=now,
                    maxResults=1,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка тестирования соединения: {e}")
            return False

# Создаем глобальный экземпляр менеджера календаря
calendar_manager = GoogleCalendarManager()