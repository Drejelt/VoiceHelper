import asyncio
import json
import logging  # Для записи всех наших "упс" моментов
import os
import threading
from hashlib import sha256  # Для шифрования паролей, чтобы хакеры плакали (от смеха)
from typing import List

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse  # Когда нужно элегантно послать пользователя куда подальше
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # Чтобы плохие дяди не пробрались в систему
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from main import VoiceAssistant  # Наш болтливый огузок
from models import Base, SessionLocal, User, get_db
from pydantic import BaseModel  # Следит за порядком в данных как строгий родитель
from sqlalchemy.orm import Session


class Config(BaseModel):
    MODEL_PATH: str = "model/vosk-model-small-ru-0.22"  # Где живёт мозг нашего помощника (надеемся, он там не заблудится)
    AI_NAME: str = "шут"  # Имя нашего цифрового клоуна
    SAMPLE_RATE: int = 16000
    BUFFER_SIZE: int = 4000
    FRAME_DURATION_MS: int = 20
    VAD_MODE: int = 3
    DEFAULT_CITY: str = "днепропетровск"  # Город по умолчанию (где-то между Марсом и Венерой)
    DEFAULT_CURRENCY: str = "UAH"
    RESTART_TIMEOUT: int = 30  # Время в минутах до перезапуска
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
        self._create_default_user()

        # Добавляем поддержку статических файлов и шаблонов
        self.app.mount("/static", StaticFiles(directory="html/static"), name="static")
        self.app.mount("/assets", StaticFiles(directory="html/assets"), name="assets")
        self.templates = Jinja2Templates(directory="html/templates")

    def _setup_routes(self):  # Карта нашего цифрового мира
        self.app.get("/")(self.root)  # Главная страница, где всё начинается
        self.app.get("/config", response_model=Config)(self.get_config)  # Показываем наши настройки
        self.app.post("/config")(self.update_config)  # Обновляем настройки, если кто-то осмелится
        self.app.on_event("startup")(self.startup_event)  # Что делать при пробуждении
        self.app.on_event("shutdown")(self.shutdown_event)  # Что делать перед сном
        self.app.get("/api/files")(self.get_json_files)
        self.app.get("/api/files/{filename}")(self.get_file_content)
        self.app.post("/api/files/{filename}")(self.update_file_content)
        self.app.post("/api/restart")(self.restart_assistant)

        # Добавляем маршрут для панели управления
        @self.app.get("/admin")
        async def admin_panel(
            request: Request,
            credentials: HTTPBasicCredentials = Depends(HTTPBasic()),
            db: Session = Depends(get_db)
        ):
            self.verify_credentials(credentials, db)
            return self.templates.TemplateResponse("admin_panel.html", {"request": request})

        @self.app.post("/api/update_credentials")
        async def update_credentials(
            credentials: HTTPBasicCredentials = Depends(HTTPBasic()),
            db: Session = Depends(get_db),
            new_credentials: dict = Body(...)
        ):
            self.verify_credentials(credentials, db)

            # Обновляем учетные данные в базе данных
            user = db.query(User).filter(User.username == credentials.username).first()
            if user:
                user.username = new_credentials["username"]
                user.password_hash = sha256(new_credentials["password"].encode()).hexdigest()
                db.commit()
                return {"message": "Учетные данные успешно обновлены"}
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        @self.app.get("/api/logs/list")
        async def list_logs():
            try:
                files = api.voice_assistant.system_controller.list_log_files()
                return {"files": files}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/view/{filename}")
        async def view_log(filename: str):
            try:
                content = api.voice_assistant.system_controller.read_log_file(filename)
                return {"content": content}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/logs/delete/{filename}")
        async def delete_log(filename: str):
            try:
                success = api.voice_assistant.system_controller.delete_log_file(filename)
                if success:
                    return {"message": f"Файл {filename} успешно удален"}
                raise HTTPException(
                    status_code=404,
                    detail=f"Файл {filename} не найден"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )

        @self.app.get("/api/commands")
        async def get_commands():
            try:
                if not os.path.exists('json/custom_commands.json'):
                    # Создаем файл с пустым списком команд, если он не существует
                    with open('json/custom_commands.json', 'w', encoding='utf-8') as f:
                        json.dump({"commands": {}}, f, ensure_ascii=False, indent=4)
                    return {"commands": {}}

                with open('json/custom_commands.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            except Exception as e:
                logging.error(f"Ошибка при загрузке команд: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/commands")
        async def add_command(command_data: dict):
            try:
                file_path = 'json/custom_commands.json'
                if not os.path.exists(file_path):
                    data = {"commands": {}}
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                data['commands'][command_data['command']] = command_data['response']

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

                return {"message": "Команда успешно добавлена"}
            except Exception as e:
                logging.error(f"Ошибка при добавлении команды: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/commands/{command}")
        async def delete_command(command: str):
            try:
                with open('json/custom_commands.json', 'r+', encoding='utf-8') as f:
                    data = json.load(f)
                    if command in data['commands']:
                        del data['commands'][command]
                        f.seek(0)
                        json.dump(data, f, ensure_ascii=False, indent=4)
                        f.truncate()
                        return {"message": "Команда успешно удалена"}
                    raise HTTPException(status_code=404, detail="Команда не найдена")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

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

    def verify_credentials(self, credentials: HTTPBasicCredentials, db: Session):
        user = db.query(User).filter(User.username == credentials.username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        password_hash = sha256(credentials.password.encode()).hexdigest()
        if user.password_hash != password_hash:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        return True

    async def root(
        self,
        credentials: HTTPBasicCredentials = Depends(HTTPBasic()),
        db: Session = Depends(get_db)
    ):
        self.verify_credentials(credentials, db)
        return RedirectResponse(url="http://127.0.0.1:8000/admin")

    async def get_config(
        self,
        credentials: HTTPBasicCredentials = Depends(HTTPBasic()),
        db: Session = Depends(get_db)
    ):
        self.verify_credentials(credentials, db)
        config = self.load_config()
        return Config(**config)

    async def update_config(
        self,
        updated_config: Config,
        credentials: HTTPBasicCredentials = Depends(HTTPBasic()),
        db: Session = Depends(get_db)
    ):
        self.verify_credentials(credentials, db)
        config_dict = updated_config.dict()
        self.save_config(config_dict)

        if hasattr(self, 'voice_assistant'):
            self.voice_assistant.reload_config()

        logging.info("Ура! Конфигурация успешно обновлена и даже не сопротивлялась!")
        return {"INFO": "Конфигурация успешно обновлена и теперь пошла пить чай"}

    async def startup_event(self):
        """Что делать при запуске."""
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

    async def shutdown_event(self):
        """Прощаемся с пользователем."""
        logging.info("FastAPI приложение отправляется спать. Не будите его без печенек!")

    def _create_default_user(self):
        """Создание пользователя по умолчанию."""
        db = SessionLocal()
        try:
            if not db.query(User).filter(User.username == "admin").first():
                default_user = User(
                    username="admin",
                    password_hash=sha256("admin".encode()).hexdigest()
                )
                db.add(default_user)
                db.commit()
                logging.info("Создан пользователь по умолчанию")
        finally:
            db.close()

    async def get_logs(self, lines: int = 100):
        """Получение последних строк логов."""
        try:
            log_file = os.path.join(self.LOG_DIR, "assistant.log")
            with open(log_file, "r", encoding="utf-8") as f:
                logs = f.readlines()[-lines:]
            return {"logs": logs}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка чтения логов: {e}")

    async def get_json_files(self):
        """Получение списка JSON файлов."""
        json_files = [
            "model_config.json",
            "alarms.json",
            "custom_commands.json"
        ]
        return {"files": json_files}

    async def get_file_content(self, filename: str):
        """Получение содержимого файла."""
        try:
            file_path = os.path.join("json", filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            return content
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {e}")

    async def update_file_content(self, filename: str, content: dict):
        """Обновление содержимого файла."""
        try:
            file_path = os.path.join("json", filename)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
            return {"message": f"Файл {filename} успешно обновлен"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка обновления файла: {e}")

    async def restart_assistant(self):
        """Перезапуск голосового ассистента."""
        try:
            if hasattr(self.voice_assistant, 'reload_config'):
                self.voice_assistant.reload_config()
            logging.info("Ассистент успешно перезапущен")
            return {"success": True, "message": "Ассистент успешно перезапущен"}
        except Exception as e:
            error_msg = f"Ошибка при перезапуске ассистента: {e}"
            logging.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)


api = VoiceAssistantAPI()
app = api.app
