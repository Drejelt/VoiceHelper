import asyncio
import io
import json
import logging
import time
from typing import Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

# Внешние библиотеки (спасибо их создателям!)
import pygame  # Для озвучки голоса от Google
import pyaudio  # Чтобы слышать голос пользователя
import pyttsx3  # Для роботического голоса (когда gTTS отдыхает)
import spacy  # Для понимания человеческой речи (или хотя бы попытки)
import vosk  # Для распознавания речи (когда не хочется платить Google)
import webrtcvad  # Отличает речь от чихания
from gtts import gTTS  # Google Text-to-Speech, когда хочется звучать как навигатор

# Наши самописные модули (сделано с любовью)
from functional_modules.scheduler import Scheduler  # Будильник (враг сна и моих нервов)
from functional_modules.info_services import InfoServices  # Для тех, кто хочет быть в курсе
from functional_modules.entertainment import Entertainment  # Развлекалово для скучающих
from functional_modules.media_controller import MediaController
from functional_modules.system_utils import SystemController, LoggerConfig  # Системный администратор в кармане
from functional_modules.social_interactions import SocialInteractions  # Модуль для социальных взаимодействий
from functional_modules.reminder import Reminder  # Модуль для работы с напоминаниями
from functional_modules.intent import Intent, Runtime, execute, intent_from_command, match_command
from functional_modules.llm import LlmRouter

# Инициализируем логгер (чтобы потом понимать, где всё сломалось)
logger_config = LoggerConfig()


class AudioProcessor:  # Мастер по обработке звука
    def __init__(self, sample_rate: int, buffer_size: int):
        self.pyaudio_instance = pyaudio.PyAudio()
        self.sample_rate = sample_rate  # Частота дискретизации
        self.buffer_size = buffer_size  # Размер буфера (чтобы не захлебнуться)

    def setup_stream(self) -> pyaudio.Stream:
        try:
            stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.buffer_size,
            )
            logging.info("Аудиопоток инициализирован.")
            return stream
        except Exception as e:
            logging.error(f"Ой-ой! Микрофон решил взять выходной: {e}")
            raise


class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def load(self) -> dict:
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
            self._validate_config(config)
            logging.info("Конфигурация успешно загружена.")
            return config
        except Exception as e:
            logging.error(f"Упс! Конфигурация сбежала в отпуск: {e}")
            raise

    def _validate_config(self, config: dict) -> None:
        required_keys = [
            "AI_NAME",
            "MODEL_PATH", 
            "SAMPLE_RATE",
            "BUFFER_SIZE",
            "FRAME_DURATION_MS",
            "VAD_MODE"
        ]
        for key in required_keys:
            if key not in config:
                raise KeyError(f"Караул! Потеряли важный ключ {key}! Кто-нибудь видел его?")


class CommandHandler:
    def __init__(self):
        self._handlers = {}
        
    def register(self, command: str, handler: Callable):
        self._handlers[command] = handler
        
    async def execute(self, command: str, *args) -> Optional[str]:
        handler = self._handlers.get(command)
        if handler:
            return await handler(*args)
        return None


class CommandProcessor:  # Переводчик с человеческого на компьютерный
    def __init__(self, config: dict, runtime: Runtime, llm: LlmRouter | None = None):
        self.config = config
        self.runtime = runtime
        self.llm = llm
        self.nlp = spacy.load("ru_core_news_sm")  # Загружаем русский язык (все 150МБ его)

    def extract_entities(self, text: str) -> Optional[Intent]:
        return self.resolve(text)

    def resolve(self, text: str) -> Optional[Intent]:
        if self.config["AI_NAME"].lower() not in text.lower():
            return None

        logging.info(f"Расспознано: {text}")
        standardized = self.runtime.info.standardize_text(text)
        command = match_command(
            standardized,
            number_game_active=bool(self.runtime.entertainment.games.number_to_guess),
        )
        cities, money = self._entities(standardized)
        time_alarm = None
        if command in {"будильник", "напомни"}:
            try:
                time_alarm = self.runtime.scheduler.parse_time_from_text(
                    standardized, self.config["AI_NAME"]
                )
                logging.info(f"Распознанное время будильника: {time_alarm}")
            except Exception as e:
                logging.error(f"Время куда-то убежало! Догоните его: {e}")

        if command:
            intent = intent_from_command(
                command,
                standardized,
                cities=cities,
                money=money,
                time_alarm=time_alarm,
                config=self.config,
            )
            if intent:
                logging.info("Определена команда: %s → %s", command, intent.tool)
                return intent

        if self.llm and self.llm.available():
            intent = self.llm.select(standardized)
            if intent:
                logging.info("LLM выбрал tool %s", intent.tool)
                return intent

        logging.info("Нет команды (keywords miss, LLM off or fallback)")
        return None

    def _entities(self, text: str) -> Tuple[list, Optional[str]]:
        doc = self.nlp(text)
        cities = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
        money = next((ent.text.lower() for ent in doc.ents if ent.label_ == "MONEY"), None)
        for currency in self.runtime.info.currency_list:
            if currency in text.lower():
                money = currency
                break
        return cities, money


class AssistantState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"

@dataclass
class AssistantContext:
    state: AssistantState
    last_command: Optional[str] = None
    last_activity: float = time.time()


class CustomLogger:
    def __init__(self):
        self.handler = RotatingFileHandler(
            'logs/assistant.log',
            maxBytes=1024*1024,  # 1MB
            backupCount=5
        )
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


class VoiceAssistant:  # Электронный огузок (надеюсь, не станет Скайнетом)
    def __init__(self, config_path: str = "json/model_config.json"):
        self.config_path = config_path
        self.load_config()

        self.scheduler = Scheduler()  # Мастер времени
        self.info_services = InfoServices()  # Знаток всего на свете
        self.entertainment = Entertainment()  # Министр развлечений
        self.media_controller = MediaController()  # DJ на все руки
        self.system_controller = SystemController()  # Властелин компьютера
        self.social = SocialInteractions()
        self.reminder = Reminder()
        self.runtime = Runtime(
            config=self.config,
            info=self.info_services,
            scheduler=self.scheduler,
            reminder=self.reminder,
            entertainment=self.entertainment,
            media=self.media_controller,
            system=self.system_controller,
            social=self.social,
        )
        self.llm = LlmRouter.from_env(self.config)

        self.setup_audio_components()  # Настраиваем уши
        self.setup_voice_components()  # Настраиваем голос
        
        self.is_speaking = False  # Флаг "Я сейчас говорю, не перебивайте!"
        self.mood = "normal"  # Возможные состояния: happy, normal, tired, excited
        self.response_templates = {
            "happy": {
                "weather": "С удовольствием расскажу о погоде! {}",
                "joke": "О, обожаю шутить! Вот вам свеженькая: {}"
            },
            "tired": {
                "weather": "*Зевая* Так и быть, гляну в окно... {}",
                "joke": "Ну ладно, вот вам шутка... {}"
            }

        }
        self.last_activity = time.time()
        self.restart_timeout = self.config.get("RESTART_TIMEOUT", 30) * 60  # Конвертируем минуты в секунды

        self.is_running = True  # Флаг для контроля работы ассистента

    def load_config(self):
        """Загружает конфигурацию из файла"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logging.info("Конфигурация успешно загружена")
        except Exception as e:
            logging.error(f"Ошибка при загрузке конфигурации: {e}")
            self.config = {}

    def reload_config(self):
        """Перезагружает конфигурацию и обновляет необходимые компоненты"""
        try:
            self.load_config()
            
            # Обновляем компоненты, которые зависят от конфигурации
            self.runtime.config = self.config
            self.llm = LlmRouter.from_env(self.config)
            if hasattr(self, "command_processor"):
                self.command_processor.config = self.config
                self.command_processor.llm = self.llm
            
            logging.info("Конфигурация успешно перезагружена")
            return True
        except Exception as e:
            logging.error(f"Ошибка при перезагрузке конфигурации: {e}")
            return False

    def setup_audio_components(self):
        """Настройка аудио компонентов"""
        try:
            if hasattr(self, 'audio_processor'):
                if hasattr(self.audio_processor, 'pyaudio_instance'):
                    self.audio_processor.pyaudio_instance.terminate()
                del self.audio_processor
                
            self.vad = webrtcvad.Vad()
            self.vad.set_mode(self.config.get("VAD_MODE", 3))
            
            self.audio_processor = AudioProcessor(
                self.config["SAMPLE_RATE"],
                self.config["BUFFER_SIZE"]
            )
            self.stream = self.audio_processor.setup_stream()
            logging.info("Аудио компоненты успешно настроены")
        except Exception as e:
            logging.error(f"Ошибка при настройке аудио компонентов: {e}")
            raise

    def setup_voice_components(self):
        self.model = vosk.Model(self.config["MODEL_PATH"])
        self.rec = vosk.KaldiRecognizer(self.model, self.config["SAMPLE_RATE"])
        self.runtime.config = self.config
        self.command_processor = CommandProcessor(self.config, self.runtime, self.llm)
        
        pygame.mixer.init()
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 180)
        self.tts_engine.setProperty('voice', 'russian')

    def speak(self, text: str) -> None:
        try:
            # Пробуем использовать gTTS (звучит как навигатор)
            tts = gTTS(text=text, lang='ru')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            
            pygame.mixer.init()
            pygame.mixer.music.load(fp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            logging.error(f"gTTS решил поспать, использую запасной вариант: {e}")
            # Если gTTS не сработал, используем pyttsx3
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    def resume_stream(self) -> None: #Возобновляет аудиопоток (если он вдруг остановился)
        try:
            self.stream.start_stream()
            logging.info("Ура! Аудиопоток вернулся из отпуска!")
        except Exception as e:
            logging.error(f"Поток застрял в пробке! Пытаемся его вытащить: {e}")

    def start_voice_assistant(self) -> None:
        """Запуск ассистента"""
        self.is_running = True
        try:
            while self.is_running:
                self.run()
        except Exception as e:
            logging.error(f"Ошибка в работе ассистента: {e}")
        finally:
            if hasattr(self, 'stream'):
                self.stream.stop_stream()
                self.stream.close()
            if hasattr(self, 'pyaudio_instance'):
                self.pyaudio_instance.terminate()

    def run(self) -> None:
        asyncio.run(self.process_audio_stream())

    def _check_restart_needed(self) -> bool:
        """Проверяет, нужен ли перезапуск"""
        current_time = time.time()
        if current_time - self.last_activity > self.restart_timeout:
            logging.info("Перезапускаюсь после долгого молчания...")
            return True
        return False

    def restart(self):
        """Перезапуск аудио компонентов"""
        try:
            # Останавливаем текущие компоненты
            if hasattr(self, 'stream'):
                self.stream.stop_stream()
                self.stream.close()
            if hasattr(self, 'pyaudio_instance'):
                self.pyaudio_instance.terminate()
            
            # Даем время на освобождение ресурсов
            time.sleep(1)
            
            # Пересоздаем компоненты
            self.setup_audio_components()
            self.setup_voice_components()
            
            self.is_running = True
            logging.info("Аудио компоненты успешно перезапущены")
            return True
        except Exception as e:
            logging.error(f"Ошибка при перезапуске компонентов: {e}")
            return False

    async def process_audio_stream(self) -> None:
        while True:
            try:
                if self.is_speaking:
                    await asyncio.sleep(0.1)
                    continue

                # Проверяем необходимость перезапуска
                if self._check_restart_needed():
                    self.restart()

                data = self.stream.read(self.config["BUFFER_SIZE"])
                if self.rec.AcceptWaveform(data):
                    result = json.loads(self.rec.Result())
                    if result["text"]:
                        text = result["text"].lower()
                        logging.info(f"Распознано: {text}")
                        self.last_activity = time.time()  # Обновляем время последней активности
                        
                        if text.strip() == self.config["AI_NAME"].lower():
                            self.speak("Слушаю вас!")
                            continue
                            
                        intent = self.command_processor.resolve(text)
                        if intent:
                            await self.handle_command(intent)

                # Проверяем напоминания
                reminder_notification = self.reminder.check_reminders()
                if reminder_notification:
                    self.speak(reminder_notification)

            except Exception as e:
                logging.error(f"Аудиопоток запутался в своих битах: {e}")
                await asyncio.sleep(0.1)

    async def handle_command(self, intent: Intent) -> None:
        try:
            self.stream.stop_stream()
            self.is_speaking = True
            logging.info("Executing %s from %s args=%s", intent.tool, intent.source, intent.arguments)
            response = execute(intent, self.runtime)
            if response:
                self.speak(response)
        except Exception as e:
            error_msg = f"Упс! Кажется, я споткнулся о баг: {e}"
            logging.error(error_msg)
            self.speak(error_msg)
        finally:
            self.is_speaking = False
            self.resume_stream()

    def stop(self):
        self.is_running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'audio_processor') and hasattr(self.audio_processor, 'pyaudio_instance'):
            self.audio_processor.pyaudio_instance.terminate()
        pygame.mixer.quit()  # Освобождаем ресурсы pygame
        self.tts_engine.stop()  # Останавливаем движок TTS
        logging.info("Ассистент остановлен")

    async def _process_heavy_task(self, func, *args):
        """Выполнение тяжелых задач в отдельном потоке"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, func, *args)