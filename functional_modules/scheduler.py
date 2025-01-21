import logging
import datetime
import time
import threading
import re
import os
from datetime import datetime, timedelta
import pygame.mixer
import json


class Scheduler:
    def __init__(self, filename="Notes.txt", alarms_file="json/alarms.json"):
        self.filename = filename
        self.alarms_file = alarms_file
        pygame.mixer.init()
        self.load_alarms()  # Загружаем сохраненные будильники при инициализации

    def load_alarms(self):
        """Загружает сохраненные будильники из файла"""
        try:
            if not os.path.exists(self.alarms_file):
                self.active_alarms = {}
                return
                
            with open(self.alarms_file, 'r', encoding='utf-8') as file:
                self.active_alarms = json.load(file)
                
            # Перезапускаем все активные будильники в отдельных потоках
            for time_str, alarm_info in self.active_alarms.items():
                if alarm_info["active"]:
                    alarm_thread = threading.Thread(
                        target=self.start_alarm_thread,
                        args=(time_str,),
                        daemon=True
                    )
                    alarm_thread.start()
                    
            logging.info(f"Загружено {len(self.active_alarms)} будильников")
        except Exception as e:
            logging.error(f"Не удалось загрузить будильники: {e}")
            self.active_alarms = {}

    def save_alarms(self):
        """Сохраняет текущие будильники в файл"""
        try:
            with open(self.alarms_file, 'w', encoding='utf-8') as file:
                json.dump(self.active_alarms, file, ensure_ascii=False, indent=2)
            logging.info("Будильники успешно сохранены")
        except Exception as e:
            logging.error(f"Не удалось сохранить будильники: {e}")

    def parse_time_from_text(self, text, ai_name):
        text = text.lower().replace(ai_name.lower(), "").replace("будильник", "")
        time_pattern = r'(\d{1,2}):(\d{1,2})'
        match = re.search(time_pattern, text)
        
        if match:
            hours, minutes = map(int, match.groups())
            if 0 <= hours <= 23 and 0 <= minutes <= 59:
                logging.info(f"Успешно распарсено время: {hours:02d}:{minutes:02d}")
                return f"{hours:02d}:{minutes:02d}"
            else:
                logging.error(f"Ой-ой! Часы и минуты разбежались! Часы={hours}, минуты={minutes}")
        else:
            logging.error("Время не найдено в тексте")
        
        return None

    def get_current_time(self):
        current_time = datetime.now().strftime("%H:%M")
        return f"Текущее время {current_time}"

    def start_alarm_thread(self, time_str):
        try:
            hours, minutes = map(int, time_str.split(':'))
            now = datetime.now()
            alarm_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            
            if alarm_time <= now:
                alarm_time += timedelta(days=1)
                
            logging.info(f"Установка будильника на {time_str}")
            
            # Добавляем информацию о будильнике
            self.active_alarms[time_str] = {
                "time": time_str,
                "set_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active": True
            }
            self.save_alarms()
            
            while datetime.now() < alarm_time:
                time.sleep(1)
                
            logging.info(f"Будильник сработал в {time_str}")

            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            alarm_sound_path = os.path.join(parent_dir, "sounds", "alarm.mp3")
            
            pygame.mixer.music.load(alarm_sound_path)
            pygame.mixer.music.play(0)
            
            # Обновляем статус будильника
            self.active_alarms[time_str]["active"] = False
            self.save_alarms()
            
        except Exception as e:
            logging.error(f"Будильник решил поспать подольше! Ошибка: {e}")
            raise

    def get_active_alarms(self) -> str:
        """Возвращает список активных будильников"""
        active = {time: info for time, info in self.active_alarms.items() if info["active"]}
        if not active:
            return "Нет активных будильников"
        
        result = "Активные будильники:\n"
        for time, info in active.items():
            result += f"- {time} (установлен: {info['set_at']})\n"
        return result

    def clear_alarms(self) -> str:
        """Очищает все активные будильники"""
        self.active_alarms = {}
        self.save_alarms()
        return "Все будильники очищены"

    def set_alarm(self, time_str):
        try:
            if not time_str:
                return "Не удалось распознать время"
                
            alarm_thread = threading.Thread(
                target=self.start_alarm_thread,
                args=(time_str,),
                daemon=True
            )
            alarm_thread.start()
            logging.info(f"Будильник установлен на {time_str}")
            return f"Будильник установлен на {time_str}"
        except Exception as e:
            error_msg = f"Будильник отказывается работать! Говорит, что устал и хочет в отпуск! Ошибка: {e}"
            logging.error(error_msg)
            return error_msg

    def write_note(self, text: str, include_datetime: bool = False) -> str:
        try:
            with open(self.filename, 'a', encoding='utf-8') as file:
                if include_datetime:
                    current_time = datetime.now().strftime("%H:%M:%S")
                    file.write(f"{current_time} --> {text}\n")
                else:
                    file.write(f"{text}\n")
            return "Заметка успешно сохранена"
        except Exception as e:
            return f"Ой! Кажется, блокнот убежал на обед! Ошибка: {e}"

    def read_notes(self) -> str:
        try:
            if not os.path.exists(self.filename):
                return "Файл с заметками играет в прятки! Не могу его найти..."
            with open(self.filename, 'r', encoding='utf-8') as file:
                notes = file.read()
            return notes if notes else "Заметки разбежались! Пока тут пусто..."
        except Exception as e:
            return f"Заметки решили устроить забастовку! Ошибка: {e}"