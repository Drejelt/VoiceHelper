import logging
import os
import json
import subprocess
from pathlib import Path

import pyautogui
from datetime import datetime

class SystemController:
    def __init__(self):
        self.log_dir = "logs"

    def _power_commands_allowed(self) -> bool:
        return os.getenv("ALLOW_POWER_COMMANDS", "0").lower() in {"1", "true", "yes"}

    def shutdown(self) -> str:
        if not self._power_commands_allowed():
            return "Команды питания отключены. Чтобы разрешить, задайте ALLOW_POWER_COMMANDS=1"
        subprocess.run(["shutdown", "-h", "now"], check=False)
        return "Выключаю компьютер..."

    def restart(self) -> str:
        if not self._power_commands_allowed():
            return "Команды питания отключены. Чтобы разрешить, задайте ALLOW_POWER_COMMANDS=1"
        subprocess.run(["reboot"], check=False)
        return "Перезагружаю компьютер..."

    def logout(self) -> str:
        if not self._power_commands_allowed():
            return "Команды питания отключены. Чтобы разрешить, задайте ALLOW_POWER_COMMANDS=1"
        user = os.environ.get("USER")
        if not user:
            return "Не удалось определить пользователя для выхода из системы"
        subprocess.run(["pkill", "-KILL", "-u", user], check=False)
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

    def _safe_log_path(self, filename: str) -> Path | None:
        if Path(filename).name != filename or not filename.endswith(".log"):
            return None
        log_dir = Path(self.log_dir).resolve()
        path = (log_dir / filename).resolve()
        try:
            path.relative_to(log_dir)
        except ValueError:
            return None
        return path

    def read_log_file(self, filename: str) -> str:
        try:
            file_path = self._safe_log_path(filename)
            if file_path is None or not file_path.exists():
                return "Файл не найден"
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Ошибка при чтении лога {filename}: {e}")
            return f"Ошибка при чтении файла: {str(e)}"

    def delete_log_file(self, filename: str) -> bool:
        try:
            file_path = self._safe_log_path(filename)
            if file_path is None or not file_path.exists():
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