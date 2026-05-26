from __future__ import print_function

import datetime
import os.path
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Константы
DIFFICULTY_DURATION = {
    'л': 60,            # лёгкая: 1 час (с запасом)
    'с': 120,           # средняя: 2 часа (с запасом)
    'т': 240,           # сложная: 4 часа (с запасом)
    'д': None           # долгосрочная: разбиваем на слоты до 4 часов в день
}

import json

CONFIG_FILE = 'config.json'

MAX_SLOT_DURATION = 240  # Максимальная длительность слота для долгосрочных задач (4 часа)

REST_TIME = {
    ('учебная', 'учебная'): 30,       # между учебными задачами
    ('другая', 'учебная'): 60,        # между другой и учебной
    ('учебная', 'другая'): 60,        # между учебной и другой
    ('другая', 'другая'): 30,         # между другими задачами
}

WORKING_DAY_MINUTE = 0  # Начало рабочего дня (полночь, чтобы не считать ночные слоты)
WORKING_DAY_END_MINUTE = 1440  # Конец рабочего дня (23:59)

# Коды типов задач
TASK_TYPES = {
    'дз': 'учебная',
    'доклад': 'учебная',
    'проект': 'учебная',
    'курсовая': 'учебная',
    'др': 'учебная'
}

MAX_SLOT_DURATION = 240  # Максимальная длительность слота для долгосрочных задач (4 часа)


def create_task_calendar(service, calendar_name='Учебные задачи'):
    calendar_body = {
        'summary': calendar_name,
        'timeZone': 'Europe/Istanbul'
    }
    created_calendar = service.calendars().insert(body=calendar_body).execute()
    return created_calendar['id']


def get_personal_calendar_id(service):
    #Получает id личного календаря (primary)
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list.get('items', []):
        if calendar_list_entry.get('primary') == True:
            return calendar_list_entry['id']
    return None


def get_pairs_calendar_id(service):
    #Получает id календаря 'пары'
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list.get('items', []):
        if calendar_list_entry['summary'] == 'пары':
            return calendar_list_entry['id']
    return None


def get_all_calendar_events(service, calendar_ids, start_date, end_date):

    #Получает все события из нескольких календарей за заданный период.
    #Возвращает список: [{'event': ..., 'calendar_id': ...}, ...]
   
    all_events = []
    for calendar_id in calendar_ids:
        if calendar_id:
            events = get_events_for_period(service, calendar_id, start_date, end_date)
            for event in events:
                all_events.append({
                    'event': event,
                    'calendar_id': calendar_id
                })
    return all_events


def load_config():
    #Загружает конфигурацию из файла
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Ошибка чтения config.json: {e}")
    return None


def save_config(work_start_hour, work_end_hour):
    #Сохраняет конфигурацию в файл
    config = {'work_start_hour': work_start_hour, 'work_end_hour': work_end_hour}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_working_hours():
    #Запрашивает у пользователя границы рабочих часов или загружает из файла
    config = load_config()
    
    if config:
        use_saved = input(f"Использовать сохранённые границы (начало: {config['work_start_hour']}, конец: {config['work_end_hour']})? (y/n): ").strip().lower()
        if use_saved == 'y':
            return config['work_start_hour'], config['work_end_hour']
    
    print("Настройка рабочих часов:")
    while True:
        try:
            start_hour = int(input("Введите начало рабочего дня (час, 0-23): "))
            if 0 <= start_hour <= 23:
                break
            print("Введите число от 0 до 23")
        except ValueError:
            print("Введите корректное число")
    
    while True:
        try:
            end_hour = int(input("Введите конец рабочего дня (час, 0-23): "))
            if 0 <= end_hour <= 23:
                break
            print("Введите число от 0 до 23")
        except ValueError:
            print("Введите корректное число")
    
    save = input("Сохранить границы для следующих запусков? (y/n): ").strip().lower()
    if save == 'y':
        save_config(start_hour, end_hour)
        print(f"Границы сохранены в {CONFIG_FILE}")
    
    return start_hour, end_hour


def parse_date(date_str):
    #Парсит дату в формате ДД.ММ.ГГГГ
    try:
        parts = date_str.split('.')
        if len(parts) != 3:
            return None
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return datetime.date(year, month, day)
    except (ValueError, IndexError):
        return None


def parse_task_input(input_str):

    #Парсит строку ввода задачи.
    Формат: <тип> <сложность> <гибкость> <дедлайн>
    Пример: дз л н 26.05.2026

    parts = input_str.strip().split()
    if len(parts) != 4:
        return None, "Неверный формат. Используйте: <тип> <сложность> <гибкость> <дедлайн>"
    
    task_type_code, difficulty_code, flexibility, deadline_str = parts
    
    # Проверка типа
    if task_type_code not in TASK_TYPES:
        return None, f"Неизвестный тип '{task_type_code}'. Доступные: {', '.join(TASK_TYPES.keys())}"
    
    # Проверка сложности
    if difficulty_code not in DIFFICULTY_DURATION:
        return None, f"Неизвестная сложность '{difficulty_code}'. Доступные: л, с, т, д"
    
    # Проверка гибкости
    if flexibility not in ('д', 'н'):
        return None, f"Неизвестная гибкость '{flexibility}'. Доступные: д (да), н (нет)"
    
    # Парсинг дедлайна
    deadline = parse_date(deadline_str)
    if not deadline:
        return None, f"Неверный формат даты '{deadline_str}'. Используйте: ДД.ММ.ГГГГ"
    
    # Получение длительности
    duration = DIFFICULTY_DURATION[difficulty_code]
    
    # Для долгосрочных задач по умолчанию гибкость = да
    if difficulty_code == 'д' and flexibility == 'н':
        print("Внимание: долгосрочные задачи по умолчанию гибкие (можно разбивать на слоты)")
        flexibility = 'д'
    
    return {
        'type_code': task_type_code,
        'type': TASK_TYPES[task_type_code],
        'difficulty': difficulty_code,
        'flexible': (flexibility == 'д'),
        'duration': duration,  # фиксированная длительность (в минутах)
        'is_long_term': (difficulty_code == 'д'),
        'deadline': deadline
    }, None


def get_events_for_period(service, calendar_id, start_date, end_date):
    #Получает все события из календаря за заданный период
    events_result = []
    page_token = None
    
    # Конвертируем даты в ISO формат
    start_datetime = datetime.datetime.combine(start_date, datetime.time.min).replace(tzinfo=pytz.timezone('Europe/Istanbul'))
    end_datetime = datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min).replace(tzinfo=pytz.timezone('Europe/Istanbul'))
    
    while True:
        events_result_page = service.events().list(
            calendarId=calendar_id,
            timeMin=start_datetime.isoformat(),
            timeMax=end_datetime.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            pageToken=page_token
        ).execute()
        
        events_result.extend(events_result_page.get('items', []))
        page_token = events_result_page.get('nextPageToken')
        
        if not page_token:
            break
    
    return events_result


def find_free_slots(events, work_start_hour, work_end_hour, min_slot_duration=60, deadline=None, today=None, study_calendar_id=None, pairs_calendar_id=None, use_current_time=False):

    #Находит свободные слоты в календаре с учётом времени отдыха между событиями.
    Возвращает словарь: {'ДД.ММ.ГГГГ': {'HH:MM-HH:MM': duration_minutes, ...}, ...}
    study_calendar_id - идентификатор календаря с учебными задачами (отдых 30 мин после)
    pairs_calendar_id - идентификатор календаря с парами (отдых 30 мин после, как учебные)

    if today is None:
        today = datetime.date.today()
    
    tz = pytz.timezone('Europe/Istanbul')
    
    free_slots = {}
    
    # Обработка каждого день от сегодня до дедлайна
    if deadline is None:
        deadline = today + datetime.timedelta(days=30)  # По умолчанию ищем на следующие 30 дней
    
    current_date = today
    while current_date <= deadline:
        date_key = current_date.strftime('%d.%m.%Y')
        free_slots[date_key] = {}
        
        # Определяем временные границы дня (с timezone)
        work_start = tz.localize(datetime.datetime.combine(current_date, datetime.time(work_start_hour, 0, 0)))
        work_end = tz.localize(datetime.datetime.combine(current_date, datetime.time(work_end_hour, 0, 0)))
        
        #Учитываем текущее время для сегодняшнего дня
        if use_current_time and current_date == today:
            now = tz.localize(datetime.datetime.now())
            # Если сейчас после конца рабочего дня, не искать слоты сегодня
            if now > work_end:
                current_date += datetime.timedelta(days=1)
                continue
            # Если сейчас до начала рабочего дня, использовать start
            slot_start = max(work_start, now)
        else:
            slot_start = work_start
        
        #Получаем события для текущего дня
        day_events = []
        for item in events:
            event = item.get('event', item)  # Поддержка обоих форматов: с calendar_id и без
            event_start = event.get('start', {}).get('dateTime', None)
            event_end = event.get('end', {}).get('dateTime', None)
            calendar_id = item.get('calendar_id', study_calendar_id)  # Если нет calendar_id, используем study_calendar_id
            
            if event_start and event_end:
                try:
                    start_dt = datetime.datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                    end_dt = datetime.datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                    
                    # Конвертируем в локальное время
                    start_local = start_dt.astimezone(tz)
                    end_local = end_dt.astimezone(tz)
                    
                    if start_local.date() == current_date:
                        # Определяем тип события
                        # Если событие из календаря "Учебные задачи" или "пары" — это учебное событие (отдых 30 мин)
                        is_study = (calendar_id == study_calendar_id) if study_calendar_id else False
                        if pairs_calendar_id and calendar_id == pairs_calendar_id:
                            is_study = True
                        day_events.append({
                            'start': start_local,
                            'end': end_local,
                            'is_study': is_study
                        })
                except Exception as e:
                    pass
        
        # Сортируем события по времени начала
        day_events.sort(key=lambda x: x['start'])
        
        for event in day_events:
            event_start = event['start']
            event_end = event['end']
            is_study = event.get('is_study', True)
            
            # Если событие начинается после текущего slot_start и есть время для слота
            if event_start > slot_start:
                duration = (event_start - slot_start).total_seconds() / 60  # в минутах
                
                if duration >= min_slot_duration:
                    slot_end = event_start
                    free_slots[date_key][f"{slot_start.strftime('%H:%M')}-{slot_end.strftime('%H:%M')}"] = int(duration)
            
            # Обновляем slot_start с учётом времени отдыха
            if event_end > slot_start:
                # Добавляем время отдыха после события
                rest_time = 30 if is_study else 60
                slot_start = event_end + datetime.timedelta(minutes=rest_time)
        
        # Проверяем оставшееся время после последнего события
        if slot_start < work_end:
            duration = (work_end - slot_start).total_seconds() / 60  # в минутах
            
            if duration >= min_slot_duration:
                free_slots[date_key][f"{slot_start.strftime('%H:%M')}-{work_end.strftime('%H:%M')}"] = int(duration)
        
        # Если слот пустой, удаляем его
        if not free_slots[date_key]:
            del free_slots[date_key]
        
        current_date += datetime.timedelta(days=1)
    
    return free_slots


def book_slot(service, calendar_id, title, start_datetime, end_datetime):
    #Бронь слота в календаре
    event = {
        'summary': title,
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'Europe/Istanbul'
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'Europe/Istanbul'
        },
    }
    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event
    ).execute()
    return created_event


def parse_task_name_for_deadline(title):

    #Извлекает дедлайн из названия задачи.
    Формат: ТИП [ДД.ММ.ГГГГ]: описаниe
    Пример: ДЗ [27.05.2026]: математика

    import re
    # Ищем паттерн [ДД.ММ.ГГГГ]
    match = re.search(r'\[(\d{2}\.\d{2}\.\d{4})\]', title)
    if match:
        return parse_date(match.group(1))
    return None


def get_all_tasks(service, calendar_id, start_date, end_date):

    #Получает все задачи из календаря с дедлайнами.
    Возвращает список задач: [{'id': ..., 'title': ..., 'start': ..., 'end': ..., 'deadline': ...}, ...]

    events_result = get_events_for_period(service, calendar_id, start_date, end_date)
    tasks = []
    
    for event in events_result:
        event_id = event.get('id')
        title = event.get('summary', '')
        event_start = event['start'].get('dateTime', None)
        event_end = event['end'].get('dateTime', None)
        
        if event_id and title:
            deadline = parse_task_name_for_deadline(title)
            tasks.append({
                'id': event_id,
                'title': title,
                'deadline': deadline,
                'deadline_days': (deadline - datetime.date.today()).days if deadline else None
            })
    
    return tasks


def get_busy_days_from_calendar(service, calendar_name, start_date, end_date, busy_threshold=3):

    #Получает календарь и подсчитывает количество событий в каждый день.
    Возвращает словарь: {'ДД.ММ.ГГГГ': count}

    # Получаем id календаря
    calendar_id = None
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list.get('items', []):
        if calendar_list_entry['summary'] == calendar_name:
            calendar_id = calendar_list_entry['id']
            break
    
    if not calendar_id:
        return {}
    
    events = get_events_for_period(service, calendar_id, start_date, end_date)
    
    busy_days = {}
    for event in events:
        start = event['start'].get('dateTime', None)
        if start:
            try:
                start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                tz = pytz.timezone('Europe/Istanbul')
                start_local = start_dt.astimezone(tz)
                date_key = start_local.strftime('%d.%m.%Y')
                busy_days[date_key] = busy_days.get(date_key, 0) + 1
            except:
                pass
    
    return busy_days


def delete_event(service, calendar_id, event_id):
    #Удаляет событие из календаря
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def get_task_priority_days(task):
    #Возвращает количество дней до дедлайна для задачи (для сортировки)
    if task.get('deadline_days') is not None:
        return task['deadline_days']
    return 999  # Большая цифра для задач без дедлайна


def reschedule_tasks_with_priority(service, calendar_id, tasks, free_slots, busy_days):

    #Переранжирует задачи по приоритету (ближайший дедлайн первым).
    Физически перемещает задачи в календаре.

    # Сортируем задачи по дедлайну (ближайший первым)
    sorted_tasks = sorted(tasks, key=get_task_priority_days)
    
    print("\n--- Приоритизация задач ---")
    print("Задачи упорядочены по дедлайну:")
    for i, task in enumerate(sorted_tasks, 1):
        days = task.get('deadline_days', 999)
        print(f"  {i}. {task['title']} (осталось {days} дней)")
    
    # Получаем текущую дату для планирования
    today = datetime.date.today()
    deadline = max((t['deadline'] for t in sorted_tasks if t['deadline']), default=today + datetime.timedelta(days=30))
    
    # Возвращаем отсортированный список задач
    return sorted_tasks


def get_distance_from_today(date_str):
    #Возвращает количество дней от сегодня до заданной даты
    today = datetime.date.today()
    deadline = parse_date(date_str)
    if not deadline:
        return None
    return (deadline - today).days


def main():
    # 1. Загрузка учётных данных
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('calendar', 'v3', credentials=creds)
    
    # 2. Получение границ рабочих часов
    work_start_hour, work_end_hour = get_working_hours()
    
    # 3. Получение id календаря "Учебные задачи"
    calendar_id = None
    calendar_list = service.calendarList().list().execute()
    for calendar_list_entry in calendar_list.get('items', []):
        if calendar_list_entry['summary'] == 'Учебные задачи':
            calendar_id = calendar_list_entry['id']
            break
    
    if not calendar_id:
        print("Календарь 'Учебные задачи' не найден. Создаём новый...")
        calendar_id = create_task_calendar(service)
        print(f"Календарь создан: {calendar_id}")
    
    # 4. Получение времени от пользователя
    print("\nВведите задачу в формате: <тип> <сложность> <гибкость> <дедлайн>")
    print("Типы: дз, доклад, проект, курсовая, др")
    print("Сложность: л (лёгкая), с (средняя), т (сложная), д (долгосрочная)")
    print("Гибкость: д (да), н (нет)")
    print("Дедлайн: ДД.ММ.ГГГГ")
    print("Пример: дз л н 26.05.2026")
    
    while True:
        task_input = input("\nВведите задачу: ").strip()
        task, error = parse_task_input(task_input)
        
        if error:
            print(f"Ошибка: {error}")
            continue
        break
    
    # 5. Получение id личного календаря
    personal_calendar_id = get_personal_calendar_id(service)
    
    # 6. Получение id календаря "пары"
    pairs_calendar_id = get_pairs_calendar_id(service)
    if pairs_calendar_id:
        print(f"Календарь 'пары' найден: {pairs_calendar_id}")
    else:
        print("Календарь 'пары' не найден - события пар не будут учтены при поиске слотов")
    
    # 7. Получение списка событий из всех календарей до дедлайна
    today = datetime.date.today()
    all_calendar_ids = [calendar_id, personal_calendar_id, pairs_calendar_id] if personal_calendar_id else [calendar_id, pairs_calendar_id]
    all_events = get_all_calendar_events(service, all_calendar_ids, today, task['deadline'])
    
    # 8. Поиск свободных слотов (с учётом текущего времени)
    print("\nПоиск свободных слотов...")
    free_slots = find_free_slots(
        all_events,
        work_start_hour=work_start_hour,
        work_end_hour=work_end_hour,
        min_slot_duration=60,  # Минимальный слот - 1 час
        deadline=task['deadline'],
        use_current_time=True,
        study_calendar_id=calendar_id,
        pairs_calendar_id=pairs_calendar_id
    )
    
    if not free_slots:
        print("Свободных слотов не найдено!")
        return
    
    # 7. Подбор подходящего слота
    print(f"\nНайдено свободных слотов:")
    for date_str, slots in sorted(free_slots.items()):
        print(f"\n{date_str}:")
        for slot_time, duration in slots.items():
            print(f"  {slot_time} ({duration} мин)")
    
    # Показать загруженность дней
    print("\nЗагруженность дней (по событиям):")
    day_events_count = {}
    for item in all_events:
        event = item.get('event', item)
        event_start = event.get('start', {}).get('dateTime', None)
        if event_start:
            try:
                start_dt = datetime.datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                tz = pytz.timezone('Europe/Istanbul')
                start_local = start_dt.astimezone(tz)
                date_key = start_local.strftime('%d.%m.%Y')
                day_events_count[date_key] = day_events_count.get(date_key, 0) + 1
            except:
                pass
    
    if day_events_count:
        for date_str, count in sorted(day_events_count.items()):
            print(f"  {date_str}: {count} событий")
    else:
        print("  Нет событий в указанный период")
    
    # Обработка долгосрочных задач
    if task['is_long_term']:
        print("\n--- Обработка долгосрочной задачи ---")
        print("Задача будет разбита на слоты по максимум 4 часа в день.")
        
        # Список слотов для долгосрочной задачи
        long_term_slots = []
        
        # Сортируем слоты по датам
        sorted_dates = sorted(free_slots.keys())
        
        # Используем флаг для заполнения слотов
        filled_any = False
        
        for date_str in sorted_dates:
            slots = free_slots[date_str]
            print(f"\nДень {date_str}:")
            
            for slot_time, duration in sorted(slots.items(), key=lambda x: x[0]):
                # Ограничиваем 4 часа (240 минут) в день
                usable_duration = min(duration, 240)
                print(f"  Планируется: {slot_time} ({usable_duration} мин)")
                
                long_term_slots.append((date_str, slot_time, usable_duration))
                filled_any = True
        
        # Проверяем, был ли хоть один слот
        if not filled_any:
            print(f"\nПредупреждение: Не удалось найти достаточные слоты для задачи!")
            print("Задача не будет добавлена в календарь.")
            return
        
        slot_list = long_term_slots
        print(f"\nВсего забронировано слотов: {len(slot_list)}")
    else:
        # Обработка обычных задач (одно бронирование)
        print(f"\nПланируем выполнение задачи ('{task['type_code']}'): {task['duration']} мин")
        print(f"Гибкость: {'Да' if task['flexible'] else 'Нет'}")
        
        # Ищем лучший свободный день (с наименьшим количеством событий)
        best_day = None
        min_events = float('inf')
        
        for date_str in sorted(free_slots.keys()):
            event_count = day_events_count.get(date_str, 0)
            # Выбираем день с наименьшим количеством событий (но не более 3)
            if event_count < min_events and event_count <= 3:
                min_events = event_count
                best_day = date_str
        
        # Если все дни перегружены, выбираем первый свободный
        if not best_day and free_slots:
            best_day = sorted(free_slots.keys())[0]
        
        if best_day:
            print(f"\nВыбран день: {best_day} (событий: {min_events if min_events != float('inf') else 0})")
            slots = free_slots[best_day]
            for slot_time, duration in sorted(slots.items(), key=lambda x: x[0]):
                if duration >= task['duration']:
                    slot_list = [(best_day, slot_time, task['duration'])]
                    break
            else:
                slot_list = []
                print("Нет подходящих слотов в выбранном дне")
        else:
            slot_list = []
            print("Нет свободных слотов")
    
    # Бронирование слотов
    if slot_list:
        print("\nЗабронированы следующие слоты:")
        tz = pytz.timezone('Europe/Istanbul')
        
        for date_str, slot_time, duration in slot_list:
            # Парсим время начала
            start_time_str = slot_time.split('-')[0]
            parts = date_str.split('.')
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            
            start_hour, start_min = map(int, start_time_str.split(':'))
            start_dt = tz.localize(datetime.datetime(year, month, day, start_hour, start_min))
            end_dt = start_dt + datetime.timedelta(minutes=duration)
            
            # Формируем название задачи с дедлайном
            deadline_str = task['deadline'].strftime('%d.%m.%Y')
            task_desc = f"{task['type']} по {task['type_code']}"
            title = f"{task['type_code'].upper()} [{deadline_str}]: {task_desc}"
            booked_event = book_slot(service, calendar_id, title, start_dt, end_dt)
            print(f"  {date_str}, {slot_time}: {title}")
            print(f"  Ссылка: {booked_event.get('htmlLink')}")
        
        print("\nЗадача успешно запланирована!")
    else:
        print("Не удалось найти подходящие слоты для задачи")
    
    # 7. Приоритизация задач
    need_priority = input("\nНужна ли приоритизация задач? (y/n): ").strip().lower() == 'y'
    
    if need_priority:
        # Получаем все задачи из календаря
        all_tasks = get_all_tasks(service, calendar_id, today, task['deadline'])
        
        # Получаем занятость дней из календаря "пары"
        busy_days = get_busy_days_from_calendar(service, 'пары', today, task['deadline'])
        
        # Переранжируем задачи по приоритету
        reschedule_tasks_with_priority(service, calendar_id, all_tasks, free_slots, busy_days)
    
    # 8. Вывод итогового списка свободных слотов
    print("\nИтоговый список свободных слотов:")
    for date_str, slots in sorted(free_slots.items()):
        print(f"\n{date_str}:")
        for slot_time, duration in sorted(slots.items()):
            print(f"  {slot_time} ({duration} мин)")


if __name__ == '__main__':
    main()
