import logging
import os
import json
import pyautogui
from datetime import datetime

class SystemController:
    def shutdown(self) -> str:
        """Выключение компьютера"""
        os.system("shutdown -h now")
        return "Выключаю компьютер..."

    def restart(self) -> str:
        """Перезагрузка компьютера"""
        os.system("reboot")
        return "Перезагружаю компьютер..."

    def logout(self) -> str:
        """Выход из системы"""
        os.system("pkill -KILL -u $USER")
        return "Выхожу из системы..."

    def take_screenshot(self) -> str:
        """Создание скриншота"""
        try:
            sc = pyautogui.screenshot()
            sc.save('screenshot.png')
            return "Скриншот сохранен"
        except Exception as e:
            return f"Ой-ой! Кажется, камера застеснялась и отказывается фотографировать! Ошибка: {e}"


class LoggerConfig:
    def __init__(self, config_path="json/model_config.json"):
        self.config_path = config_path
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        self.setup_logging()

    def get_logging_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                return config.get('logging_enabled', True)
        except FileNotFoundError:
            return True

    def setup_logging(self):
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file_path = os.path.join(self.log_dir, f"{current_date}.log")

        if self.get_logging_config():
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s",
                handlers=[
                    logging.FileHandler(log_file_path),
                    logging.StreamHandler()
                ]
            )
        else:
            logging.basicConfig(
                handlers=[logging.NullHandler()]
            )


class NotesManager:
    def __init__(self, filename="Notes.txt"):
        self.filename = filename

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
            return f"Ошибка при сохранении заметки: {e}"

    def read_notes(self) -> str:
        try:
            if not os.path.exists(self.filename):
                return "Файл с заметками не найден"
            with open(self.filename, 'r', encoding='utf-8') as file:
                notes = file.read()
            return notes if notes else "Хм... В блокноте пусто, как в холодильнике после визита студента!"
        except Exception as e:
            return f"Ой! Кажется, все буквы разбежались! Не могу прочитать заметки: {e}"