#!/usr/bin/env python3

# Импортируем все, что нужно для создания самого надоедливого будильника в мире
import logging
import datetime
import time
import threading
import re
import os
from datetime import datetime, timedelta

# Без этого наш будильник будет тихим как мышь... а нам такое не надо!
import pygame.mixer


def parse_time_from_text(text, ai_name):
    # Убираем лишние слова, чтобы не путаться (как будто раздеваем время догола)
    text = text.lower().replace(ai_name.lower(), "").replace("будильник", "")

    # Ищем время по шаблону, как детектив в поисках преступника
    time_pattern = r'(\d{1,2}):(\d{1,2})'
    match = re.search(time_pattern, text)
    
    if match:
        # Если поймали время за хвост, разбираем его на части
        hours, minutes = map(int, match.groups())
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            logging.info(f"Успешно распарсено время: {hours:02d}:{minutes:02d} (часы: {hours}, минуты: {minutes})")
            return f"{hours:02d}:{minutes:02d}"
        else:
            logging.error(f"Ой-ой! Кажется, часы сошли с ума! Часы={hours}, минуты={minutes}")
    else:
        logging.error("Время играет в прятки и я не могу его найти!")
    
    return None

def get_current_time():
    current_time = datetime.now().strftime("%H:%M")
    return f"Текущее время {current_time}"

def start_alarm_thread(time_str):
    try:
        # Разбираем время на запчасти, как механик будильник
        hours, minutes = map(int, time_str.split(':'))
        now = datetime.now()
        alarm_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        
        # Если проспали нужное время, переносим на завтра (классика жанра!)
        if alarm_time <= now:
            alarm_time += timedelta(days=1)
            
        logging.info(f"Пытаюсь уговорить будильник зазвонить в {time_str}")
        
        # Тут будильник притворяется спящим
        while datetime.now() < alarm_time:
            time.sleep(1)
            
        logging.info(f"Динь-дон! Будильник проснулся в {time_str}")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        alarm_sound_path = os.path.join(parent_dir, "sounds", "alarm.mp3")
        
        # Врубаем музыку на полную! Соседи будут в восторге!
        pygame.mixer.music.load(alarm_sound_path)
        pygame.mixer.music.play(0)
        
    except Exception as e:
        logging.error(f"Будильник взял больничный и отказывается работать: {e}")
        raise

def set_alarm(time_str):
    try:
        # Если время потерялось по дороге
        if not time_str:
            return "Ой! Время куда-то убежало, не могу его поймать!"
            
        # Запускаем будильник в отдельном потоке, чтобы он никому не мешал (пока не зазвонит)
        alarm_thread = threading.Thread(
            target=start_alarm_thread,
            args=(time_str,),
            daemon=True
        )
        alarm_thread.start()
        logging.info(f"Будильник согласился зазвонить в {time_str}")
        return f"Будильник установлен на {time_str}"
    except Exception as e:
        error_msg = f"Будильник впал в депрессию и отказывается сотрудничать: {e}"
        logging.error(error_msg)
        return error_msg