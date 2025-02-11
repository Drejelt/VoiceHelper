from datetime import datetime
import json
import logging
from typing import Dict, List, Optional

class Reminder:
    def __init__(self):
        self.reminders_file = "json/reminders.json"
        self.reminders: Dict[str, List[Dict]] = self._load_reminders()

    def _load_reminders(self) -> Dict[str, List[Dict]]:
        try:
            with open(self.reminders_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"active": [], "completed": []}
        except Exception as e:
            logging.error(f"Ошибка загрузки напоминаний: {e}")
            return {"active": [], "completed": []}

    def _save_reminders(self) -> None:
        try:
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка сохранения напоминаний: {e}")

    def add_reminder(self, text: str, time: datetime) -> str:
        try:
            reminder = {
                "id": len(self.reminders["active"]),
                "text": text,
                "time": time.strftime("%Y-%m-%d %H:%M"),
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            self.reminders["active"].append(reminder)
            self._save_reminders()
            return f"Хорошо, я напомню вам {text} в {time.strftime('%H:%M')}"
        except Exception as e:
            logging.error(f"Ошибка добавления напоминания: {e}")
            return "Извините, не удалось создать напоминание"

    def get_active_reminders(self) -> str:
        if not self.reminders["active"]:
            return "У вас нет активных напоминаний"
        
        result = "Ваши напоминания:\n"
        for rem in self.reminders["active"]:
            result += f"- {rem['text']} в {rem['time'].split()[1]}\n"
        return result

    def check_reminders(self) -> Optional[str]:
        current_time = datetime.now()
        reminders_to_remove = []
        notification = None

        for reminder in self.reminders["active"]:
            reminder_time = datetime.strptime(reminder["time"], "%Y-%m-%d %H:%M")
            if current_time >= reminder_time:
                notification = f"Напоминаю: {reminder['text']}"
                reminders_to_remove.append(reminder)

        for rem in reminders_to_remove:
            self.reminders["active"].remove(rem)
            self.reminders["completed"].append(rem)

        if reminders_to_remove:
            self._save_reminders()

        return notification 