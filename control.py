import json
import threading
import logging
import os
from hashlib import sha256
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from main import VoiceAssistant

class Config(BaseModel):
    MODEL_PATH: str = "model/vosk-model-small-ru-0.22"
    AI_NAME: str = "шут"
    SAMPLE_RATE: int = 16000
    BUFFER_SIZE: int = 4000
    FRAME_DURATION_MS: int = 20
    VAD_MODE: int = 3

class VoiceAssistantAPI:
    def __init__(self):
        self.app = FastAPI()
        self.MODEL_CONFIG = "json/model_config.json"
        self.CREDENTIALS_FILE = "json/credentials.json"
        self.LOG_DIR = "logs"
        self.assistant_thread = None
        self.security = HTTPBasic()
        self._setup_routes()
        self._create_default_credentials()

    def _setup_routes(self):
        self.app.get("/")(self.root)
        self.app.get("/config", response_model=Config)(self.get_config)
        self.app.post("/config")(self.update_config)
        self.app.on_event("startup")(self.startup_event)
        self.app.on_event("shutdown")(self.shutdown_event)

    def load_config(self):
        try:
            with open(self.MODEL_CONFIG, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось загрузить конфигурацию: {e}")

    def save_config(self, config):
        try:
            with open(self.MODEL_CONFIG, "w", encoding="utf-8") as file:
                json.dump(config, file, ensure_ascii=False, indent=4)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось сохранить конфигурацию: {e}")

    def verify_credentials(self, credentials: HTTPBasicCredentials):
        try:
            with open(self.CREDENTIALS_FILE, "r", encoding="utf-8") as file:
                stored_credentials = json.load(file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось загрузить данные пользователя: {e}")

        username = credentials.username
        password_hash = sha256(credentials.password.encode()).hexdigest()

        if username in stored_credentials and stored_credentials[username] == password_hash:
            return True

        raise HTTPException(status_code=401, detail="Неверные логин или пароль")

    async def root(self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
        self.verify_credentials(credentials)
        return RedirectResponse(url="http://127.0.0.1:8000/docs")

    async def get_config(self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
        self.verify_credentials(credentials)
        return Config(**VoiceAssistant.config)

    async def update_config(self, updated_config: Config, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
        self.verify_credentials(credentials)
        VoiceAssistant.config = updated_config.dict()
        VoiceAssistant.reload_config()
        logging.info("Конфигурация успешно обновлена.")
        return {"INFO": "Конфигурация успешно обновлена."}

    async def startup_event(self):
        logging.info("FastAPI приложение успешно запущено.")
        try:
            voice_assistant = VoiceAssistant()
            self.assistant_thread = threading.Thread(target=voice_assistant.start_voice_assistant, daemon=True)
            self.assistant_thread.start()
        except Exception as e:
            logging.error(f"Ошибка при запуске голосового помощника: {e}")

    async def shutdown_event(self):
        logging.info("Завершение работы приложения FastAPI.")

    def _create_default_credentials(self):
        if not os.path.exists(self.CREDENTIALS_FILE):
            default_username = "admin"
            default_password = "admin"
            hashed_password = sha256(default_password.encode()).hexdigest()

            with open(self.CREDENTIALS_FILE, "w", encoding="utf-8") as file:
                json.dump({default_username: hashed_password}, file, ensure_ascii=False, indent=4)

            logging.info(f"Файл {self.CREDENTIALS_FILE} создан с учётными данными по умолчанию.")

# Создание экземпляра API
api = VoiceAssistantAPI()
app = api.app
