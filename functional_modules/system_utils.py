import logging
import os
import json
import pyautogui
from datetime import datetime

class SystemController:
    def __init__(self):
        self.log_dir = "logs"  # Директория с логами

    def shutdown(self) -> str:
        os.system("shutdown -h now")
        return "Выключаю компьютер..."

    def restart(self) -> str:
        os.system("reboot")
        return "Перезагружаю компьютер..."

    def logout(self) -> str:
        os.system("pkill -KILL -u $USER")
        return "Выхожу из системы..."

    def take_screenshot(self) -> str:
        try:
            sc = pyautogui.screenshot()
            sc.save('screenshot.png')
            return "Скриншот сохранен"
        except Exception as e:
            return f"Ой-ой! Кажется, камера застеснялась и отказывается фотографировать! Ошибка: {e}"

    def list_log_files(self) -> list:
        try:
            if not os.path.exists(self.log_dir):
                return []
            return sorted([f for f in os.listdir(self.log_dir) if f.endswith('.log')])
        except Exception as e:
            logging.error(f"Ошибка при получении списка логов: {e}")
            return []

    def read_log_file(self, filename: str) -> str:
        try:
            file_path = os.path.join(self.log_dir, filename)
            if not os.path.exists(file_path):
                return "Файл не найден"
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Ошибка при чтении лога {filename}: {e}")
            return f"Ошибка при чтении файла: {str(e)}"

    def delete_log_file(self, filename: str) -> bool:
        try:
            file_path = os.path.join(self.log_dir, filename)
            if not os.path.exists(file_path):
                return False
            os.remove(file_path)
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении лога {filename}: {e}")
            return False


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