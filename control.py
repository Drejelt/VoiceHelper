import json
import logging
import os
import secrets
import threading
from hashlib import sha256
from pathlib import Path

import bcrypt
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from main import VoiceAssistant
from models import SessionLocal, User, get_db

JSON_DIR = Path("json").resolve()
LOG_DIR = Path("logs").resolve()
ALLOWED_JSON_FILES = {
    "model_config.json",
    "alarms.json",
    "custom_commands.json",
    "reminders.json",
}
INSECURE_ADMIN_SHA256 = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
LOCALHOST_HOSTS = {"127.0.0.1", "::1"}
security = HTTPBasic()


class Config(BaseModel):
    MODEL_PATH: str = "model/vosk-model-small-ru-0.22"
    AI_NAME: str = "шут"
    SAMPLE_RATE: int = 16000
    BUFFER_SIZE: int = 4000
    FRAME_DURATION_MS: int = 20
    VAD_MODE: int = 3
    DEFAULT_CITY: str = "днепропетровск"
    DEFAULT_CURRENCY: str = "UAH"
    RESTART_TIMEOUT: int = 30
    logging_enabled: bool = True


class CredentialUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _is_bcrypt_hash(stored_hash: str) -> bool:
    return stored_hash.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain_password: str, stored_hash: str) -> bool:
    if _is_bcrypt_hash(stored_hash):
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                stored_hash.encode("utf-8"),
            )
        except ValueError:
            return False
    expected = sha256(plain_password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(expected, stored_hash)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Basic"},
    )


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise _unauthorized()

    if not _is_bcrypt_hash(user.password_hash):
        user.password_hash = hash_password(credentials.password)
        db.commit()
        db.refresh(user)

    return user


def _safe_json_path(filename: str) -> Path:
    if filename not in ALLOWED_JSON_FILES:
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    path = (JSON_DIR / filename).resolve()
    try:
        path.relative_to(JSON_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Недопустимый путь") from exc
    return path


def _safe_log_path(filename: str) -> Path:
    if Path(filename).name != filename or not filename.endswith(".log"):
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    path = (LOG_DIR / filename).resolve()
    try:
        path.relative_to(LOG_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Недопустимый путь") from exc
    return path


class VoiceAssistantAPI:
    def __init__(self):
        self.app = FastAPI()
        self.MODEL_CONFIG = "json/model_config.json"
        self.LOG_DIR = "logs"
        self.assistant_thread = None
        self._setup_middleware()
        self._setup_routes()
        self._create_default_user()

        self.app.mount("/static", StaticFiles(directory="html/static"), name="static")
        self.app.mount("/assets", StaticFiles(directory="html/assets"), name="assets")
        self.templates = Jinja2Templates(directory="html/templates")

    def _setup_middleware(self):
        @self.app.middleware("http")
        async def localhost_only(request: Request, call_next):
            client_host = request.client.host if request.client else ""
            if client_host not in LOCALHOST_HOSTS:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Панель доступна только с localhost"},
                )
            return await call_next(request)

    def _setup_routes(self):
        self.app.get("/")(self.root)
        self.app.get("/config", response_model=Config)(self.get_config)
        self.app.post("/config")(self.update_config)
        self.app.get("/api/config", response_model=Config)(self.get_config)
        self.app.post("/api/config")(self.update_config)
        self.app.on_event("startup")(self.startup_event)
        self.app.on_event("shutdown")(self.shutdown_event)
        self.app.get("/api/files")(self.get_json_files)
        self.app.get("/api/files/{filename}")(self.get_file_content)
        self.app.post("/api/files/{filename}")(self.update_file_content)
        self.app.post("/api/restart")(self.restart_assistant)

        @self.app.get("/admin")
        async def admin_panel(
            request: Request,
            _: User = Depends(get_current_user),
        ):
            return self.templates.TemplateResponse("admin_panel.html", {"request": request})

        @self.app.post("/api/update_credentials")
        async def update_credentials(
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db),
            new_credentials: CredentialUpdate = Body(...),
        ):
            taken = (
                db.query(User)
                .filter(
                    User.username == new_credentials.username,
                    User.id != current_user.id,
                )
                .first()
            )
            if taken:
                raise HTTPException(status_code=409, detail="Имя пользователя уже занято")

            current_user.username = new_credentials.username
            current_user.password_hash = hash_password(new_credentials.password)
            db.commit()
            return {"message": "Учетные данные успешно обновлены"}

        @self.app.get("/api/logs/list")
        async def list_logs(_: User = Depends(get_current_user)):
            try:
                files = api.voice_assistant.system_controller.list_log_files()
                return {"files": files}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/api/logs/view/{filename}")
        async def view_log(filename: str, _: User = Depends(get_current_user)):
            try:
                _safe_log_path(filename)
                content = api.voice_assistant.system_controller.read_log_file(filename)
                return {"content": content}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.delete("/api/logs/delete/{filename}")
        async def delete_log(filename: str, _: User = Depends(get_current_user)):
            try:
                _safe_log_path(filename)
                success = api.voice_assistant.system_controller.delete_log_file(filename)
                if success:
                    return {"message": f"Файл {filename} успешно удален"}
                raise HTTPException(status_code=404, detail=f"Файл {filename} не найден")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/api/commands")
        async def get_commands(_: User = Depends(get_current_user)):
            try:
                commands_path = _safe_json_path("custom_commands.json")
                if not commands_path.exists():
                    with open(commands_path, "w", encoding="utf-8") as f:
                        json.dump({"commands": {}}, f, ensure_ascii=False, indent=4)
                    return {"commands": {}}

                with open(commands_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except HTTPException:
                raise
            except Exception as e:
                logging.error(f"Ошибка при загрузке команд: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.post("/api/commands")
        async def add_command(command_data: dict, _: User = Depends(get_current_user)):
            try:
                command = command_data.get("command")
                response = command_data.get("response")
                if not isinstance(command, str) or not isinstance(response, str):
                    raise HTTPException(status_code=400, detail="Нужны поля command и response")
                if not command.strip() or not response.strip():
                    raise HTTPException(status_code=400, detail="Команда и ответ не могут быть пустыми")

                file_path = _safe_json_path("custom_commands.json")
                if not file_path.exists():
                    data = {"commands": {}}
                else:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                data.setdefault("commands", {})
                data["commands"][command.strip()] = response.strip()

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

                return {"message": "Команда успешно добавлена"}
            except HTTPException:
                raise
            except Exception as e:
                logging.error(f"Ошибка при добавлении команды: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.delete("/api/commands/{command}")
        async def delete_command(command: str, _: User = Depends(get_current_user)):
            try:
                file_path = _safe_json_path("custom_commands.json")
                with open(file_path, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    if command in data.get("commands", {}):
                        del data["commands"][command]
                        f.seek(0)
                        json.dump(data, f, ensure_ascii=False, indent=4)
                        f.truncate()
                        return {"message": "Команда успешно удалена"}
                    raise HTTPException(status_code=404, detail="Команда не найдена")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

    def load_config(self):
        try:
            with open(self.MODEL_CONFIG, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ой-ой! Конфигурация сбежала в отпуск на Багамы: {e}",
            ) from e

    def save_config(self, config):
        try:
            with open(self.MODEL_CONFIG, "w", encoding="utf-8") as file:
                json.dump(config, file, ensure_ascii=False, indent=4)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Упс! Файл конфигурации решил поиграть в прятки: {e}",
            ) from e

    async def root(self, _: User = Depends(get_current_user)):
        return RedirectResponse(url="/admin")

    async def get_config(self, _: User = Depends(get_current_user)):
        config = self.load_config()
        return Config(**config)

    async def update_config(
        self,
        updated_config: Config,
        _: User = Depends(get_current_user),
    ):
        config_dict = updated_config.model_dump()
        self.save_config(config_dict)

        if hasattr(self, "voice_assistant"):
            self.voice_assistant.reload_config()

        logging.info("Ура! Конфигурация успешно обновлена и даже не сопротивлялась!")
        return {"INFO": "Конфигурация успешно обновлена и теперь пошла пить чай"}

    async def startup_event(self):
        logging.info("FastAPI приложение проснулось и готово к подвигам!")
        try:
            self.voice_assistant = VoiceAssistant()
            self.assistant_thread = threading.Thread(
                target=self.voice_assistant.start_voice_assistant,
                daemon=True,
            )
            self.assistant_thread.start()
        except Exception as e:
            logging.error(f"Ой-ёй! Голосовой помощник споткнулся на ровном месте: {e}")

    async def shutdown_event(self):
        logging.info("FastAPI приложение отправляется спать. Не будите его без печенек!")

    def _create_default_user(self):
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.username == "admin").first()
            password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(16)

            if admin and admin.password_hash == INSECURE_ADMIN_SHA256:
                admin.password_hash = hash_password(password)
                db.commit()
                logging.warning(
                    "Старый пароль admin/admin сброшен. "
                    "Новый логин: admin, пароль: %s",
                    password,
                )
            elif not db.query(User).first():
                db.add(User(username="admin", password_hash=hash_password(password)))
                db.commit()
                logging.warning(
                    "Создан пользователь admin. Пароль: %s "
                    "(задайте ADMIN_PASSWORD, чтобы выбрать свой)",
                    password,
                )
        finally:
            db.close()

    async def get_json_files(self, _: User = Depends(get_current_user)):
        return {"files": sorted(ALLOWED_JSON_FILES)}

    async def get_file_content(self, filename: str, _: User = Depends(get_current_user)):
        try:
            file_path = _safe_json_path(filename)
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {e}") from e

    async def update_file_content(
        self,
        filename: str,
        content: dict,
        _: User = Depends(get_current_user),
    ):
        try:
            file_path = _safe_json_path(filename)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
            return {"message": f"Файл {filename} успешно обновлен"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка обновления файла: {e}") from e

    async def restart_assistant(self, _: User = Depends(get_current_user)):
        try:
            if hasattr(self.voice_assistant, "reload_config"):
                self.voice_assistant.reload_config()
            logging.info("Ассистент успешно перезапущен")
            return {"success": True, "message": "Ассистент успешно перезапущен"}
        except Exception as e:
            error_msg = f"Ошибка при перезапуске ассистента: {e}"
            logging.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg) from e


api = VoiceAssistantAPI()
app = api.app
