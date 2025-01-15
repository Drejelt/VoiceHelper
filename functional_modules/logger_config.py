import logging
import os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

current_date = datetime.now().strftime("%Y-%m-%d")
log_file_path = os.path.join(LOG_DIR, f"{current_date}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)

# Пример использования
logging.info("Логирование настроено!")
