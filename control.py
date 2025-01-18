import json
import logging  # Для записи всех наших "упс" моментов
import os
import threading
from hashlib import sha256  # Для шифрования паролей, чтобы хакеры плакали (от смеха)

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse  # Когда нужно элегантно послать пользователя куда подальше
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # Чтобы плохие дяди не пробрались в систему
from main import VoiceAssistant  # Наш болтливый огузок
from pydantic import BaseModel  # Следит за порядком в данных как строгий родитель


class Config(BaseModel):
    MODEL_PATH: str = "model/vosk-model-small-ru-0.22" # Где живёт мозг нашего помощника (надеемся, он там не заблудится)
    AI_NAME: str = "шут"  # Имя нашего цифрового клоуна
    SAMPLE_RATE: int = 16000
    BUFFER_SIZE: int = 4000
    FRAME_DURATION_MS: int = 20
    VAD_MODE: int = 3 
    DEFAULT_CITY: str = "днепропетровск" # Город по умолчанию (где-то между Марсом и Венерой)
    logging_enabled: bool = True  # Включаем логирование, чтобы потом было над чем посмеяться


class VoiceAssistantAPI:
    def __init__(self):
        self.app = FastAPI()
        self.MODEL_CONFIG = "json/model_config.json"  # Где хранятся все наши секреты
        self.CREDENTIALS_FILE = "json/credentials.json"
        self.LOG_DIR = "logs" 
        self.assistant_thread = None  # Поток для ассистента (пока спит)
        self.security = HTTPBasic()  # Наша цифровая охрана
        self._setup_routes()  # Расставляем указатели на нашем цифровом перекрёстке
        self._create_default_credentials()  # Создаём учётку админа, если её ещё нет

    def _setup_routes(self):  # Карта нашего цифрового мира
        self.app.get("/")(self.root)  # Главная страница, где всё начинается
        self.app.get("/config", response_model=Config)(self.get_config)  # Показываем наши настройки
        self.app.post("/config")(self.update_config)  # Обновляем настройки, если кто-то осмелится
        self.app.on_event("startup")(self.startup_event)  # Что делать при пробуждении
        self.app.on_event("shutdown")(self.shutdown_event)  # Что делать перед сном

    def load_config(self):  # Загружаем конфигурацию из файла
        try:
            with open(self.MODEL_CONFIG, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ой-ой! Конфигурация сбежала в отпуск на Багамы: {e}"
            )

    def save_config(self, config):
        try:
            with open(self.MODEL_CONFIG, "w", encoding="utf-8") as file:
                json.dump(config, file, ensure_ascii=False, indent=4)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Упс! Файл конфигурации решил поиграть в прятки: {e}"
            )

    def verify_credentials(self, credentials: HTTPBasicCredentials):  # Проверяем, свой/чужой
        try:
            with open(self.CREDENTIALS_FILE, "r", encoding="utf-8") as file:
                stored_credentials = json.load(file)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Караул! Учетные данные пользователя испарились как утренний туман: {e}"
            )

        username = credentials.username
        password_hash = sha256(credentials.password.encode()).hexdigest()

        if username in stored_credentials and stored_credentials[username] == password_hash:
            return True

        raise HTTPException(status_code=401, detail="Ха-ха! Кажется, кто-то забыл свой пароль или решил притвориться админом!")

    async def root(self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
        self.verify_credentials(credentials)
        return RedirectResponse(url="http://127.0.0.1:8000/docs")

    async def get_config(self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):  # Показываем настройки
        self.verify_credentials(credentials)
        config = self.load_config()
        return Config(**config)

    async def update_config(  # Обновляем настройки
        self,
        updated_config: Config,
        credentials: HTTPBasicCredentials = Depends(HTTPBasic())
    ):
        self.verify_credentials(credentials)
        config_dict = updated_config.dict()
        self.save_config(config_dict)

        if hasattr(self, 'voice_assistant'):
            self.voice_assistant.reload_config()

        logging.info("Ура! Конфигурация успешно обновлена и даже не сопротивлялась!")
        return {"INFO": "Конфигурация успешно обновлена и теперь пошла пить чай"}

    async def startup_event(self):  # Что делать при запуске
        logging.info("FastAPI приложение проснулось и готово к подвигам!")
        try:
            self.voice_assistant = VoiceAssistant()
            self.assistant_thread = threading.Thread(
                target=self.voice_assistant.start_voice_assistant,
                daemon=True
            )
            self.assistant_thread.start()
        except Exception as e:
            logging.error(f"Ой-ёй! Голосовой помощник споткнулся на ровном месте: {e}")

    async def shutdown_event(self):  # Прощаемся с пользователем
        logging.info("FastAPI приложение отправляется спать. Не будите его без печенек!")

    def _create_default_credentials(self):  # Создаём учётку админа, если её нет
        if not os.path.exists(self.CREDENTIALS_FILE):
            default_username = "admin"  # Самый креативный логин в мире
            default_password = "admin"  # Самый безопасный пароль в мире (нет)
            hashed_password = sha256(default_password.encode()).hexdigest()

            with open(self.CREDENTIALS_FILE, "w", encoding="utf-8") as file:
                json.dump(
                    {default_username: hashed_password},
                    file,
                    ensure_ascii=False,
                    indent=4
                )

            logging.info(
                f"Ура! Родился новый файл {self.CREDENTIALS_FILE} с секретными данными!"
            )


api = VoiceAssistantAPI()
app = api.app
