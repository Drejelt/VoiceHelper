#!/usr/bin/env python3

import logging
import datetime
import time
import threading
import re
from datetime import datetime, timedelta

def parse_time_from_text(text, ai_name):
    text = text.lower().replace(ai_name.lower(), "").replace("будильник", "")

    time_pattern = r'(\d{1,2}):(\d{1,2})'
    match = re.search(time_pattern, text)
    
    if match:
        hours, minutes = map(int, match.groups())
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            logging.info(f"Успешно распарсено время: {hours:02d}:{minutes:02d} (часы: {hours}, минуты: {minutes})")
            return f"{hours:02d}:{minutes:02d}"
        else:
            logging.error(f"Некорректное время: часы={hours}, минуты={minutes}")
    else:
        logging.error("Не удалось найти время в тексте")
    
    return None

def get_current_time():
    current_time = datetime.now().strftime("%H:%M")
    return f"Текущее время {current_time}"

def start_alarm_thread(time_str):
    try:
        hours, minutes = map(int, time_str.split(':'))
        now = datetime.now()
        alarm_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        
        # Если время уже прошло, добавляем день
        if alarm_time <= now:
            alarm_time += timedelta(days=1)
            
        logging.info(f"Попытка установки будильника на {time_str}")
        
        # Ждем до указанного времени
        while datetime.now() < alarm_time:
            time.sleep(1)
            
        logging.info(f"Будильник сработал в {time_str}")
        # Здесь можно добавить звуковой сигнал или другое действие
        
    except Exception as e:
        logging.error(f"Ошибка в работе будильника: {e}")
        raise

def set_alarm(time_str):
    try:
        if not time_str:
            return "Извините, не удалось распознать время для будильника"
            
        alarm_thread = threading.Thread(
            target=start_alarm_thread,
            args=(time_str,),
            daemon=True
        )
        alarm_thread.start()
        logging.info(f"Будильник установлен на {time_str}")
        return f"Будильник установлен на {time_str}"
    except Exception as e:
        error_msg = f"Ошибка при установке будильника: {e}"
        logging.error(error_msg)
        return error_msg