import json, threading, logging, os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from main import VoiceAssistant

app = FastAPI()

MODEL_CONFIG = "json/model_config.json"
LOG_DIR = "logs"
assistant_thread = None

# Базовая конфигурация модели
class Config(BaseModel):
    MODEL_PATH: str = "model/vosk-model-small-ru-0.22"
    AI_NAME: str = "шут"
    SAMPLE_RATE: int = 16000
    BUFFER_SIZE: int = 4000
    FRAME_DURATION_MS: int = 20
    VAD_MODE: int = 3

# Загрузка конфигурации
def load_config():
    try:
        with open(MODEL_CONFIG, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось загрузить конфигурацию: {e}")

# Сохранение конфигурации
def save_config(config):
    try:
        with open(MODEL_CONFIG, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить конфигурацию: {e}")

# Конечная точка для получения конфигурации
@app.get("/config", response_model=Config)
def get_config():
    return Config(**VoiceAssistant.config)

# Конечная точка для обновления конфигурации
@app.post("/config")
def update_config(updated_config: Config):
    # Сохраняем новую конфигурацию
    VoiceAssistant.config = updated_config.dict()
    VoiceAssistant.reload_config()
    logging.info("Конфигурация успешно обновлена.")
    return {"INFO": "Конфигурация успешно обновлена."}

@app.on_event("startup")
def startup_event():
    logging.info("FastAPI приложение успешно запущено.")

    try:
        voice_assistant = VoiceAssistant()
        assistant_thread = threading.Thread(target=voice_assistant.start_voice_assistant, daemon=True)
        assistant_thread.start()

    except Exception as e:
        logging.error(f"Ошибка при запуске голосового помощника: {e}")

@app.on_event("shutdown")
def shutdown_event():
    logging.info("Завершение работы приложения FastAPI.")
    # Дополнительная логика очистки может быть здесь
