import logging  # Импортируем логирование, чтобы знать, когда всё пошло не так
import os
import json
from datetime import datetime  # Чтобы знать, когда наступил очередной день страданий

def get_logging_config():
    try:
        with open('json/model_config.json', 'r') as f:
            config = json.load(f)
            # Проверяем, не решил ли пользователь отключить наш дневник неудач
            return config.get('logging_enabled', True)
    except FileNotFoundError:
        return True

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

current_date = datetime.now().strftime("%Y-%m-%d")
log_file_path = os.path.join(LOG_DIR, f"{current_date}.log")
# Настраиваем систему слежки... то есть, логирования
if get_logging_config():
    logging.basicConfig(
        level=logging.INFO,  # Уровень паранойи: средний
        format="%(asctime)s - %(levelname)s - %(message)s",  # Красиво оформляем наши страдания
        handlers=[
            logging.FileHandler(log_file_path),  # Записываем в файл (на случай, если потомки захотят посмеяться)
            logging.StreamHandler()  # И в консоль (чтобы сразу видеть, где мы накосячили)
        ]
    )
else:
    # Если логирование выключено, притворяемся, что ничего не видим
    logging.basicConfig(
        handlers=[logging.NullHandler()]  # Чёрная дыра для логов
    )
