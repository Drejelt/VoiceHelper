import asyncio
import io
import json
import logging
import time
from typing import Optional, Tuple, List, Callable
from datetime import datetime
from functools import lru_cache
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
from functional_modules.media_controller import MediaController, MusicAction, Urls  # DJ на минималках
from functional_modules.system_utils import SystemController, LoggerConfig  # Системный администратор в кармане
from functional_modules.social_interactions import SocialInteractions  # Модуль для социальных взаимодействий
from functional_modules.reminder import Reminder  # Модуль для работы с напоминаниями

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
    def __init__(self, config: dict, info_services: InfoServices, scheduler: Scheduler):
        self.config = config  # Настройки нашего цифрового друга
        self.info_services = info_services  # Для получения информации из внешнего мира
        self.scheduler = scheduler  # Личный тайм-менеджер
        self.nlp = spacy.load("ru_core_news_sm")  # Загружаем русский язык (все 150МБ его)
        # Добавляем новые модули
        self.entertainment = Entertainment()
        self.media_controller = MediaController()
        self.system_controller = SystemController()

    @lru_cache(maxsize=128)
    def _get_command_patterns(self) -> dict:
        """Кэширование паттернов команд для улучшения производительности"""
        return self.commands

    def extract_entities(self, text: str) -> Tuple[Optional[str], Optional[List[str]], Optional[str], Optional[str], Optional[str]]:
        if self.config["AI_NAME"].lower() not in text.lower():
            return None, None, None, None, None

        logging.info(f"Расспознано: {text}")
        standardized_text = self.info_services.standardize_text(text)

        doc = self.nlp(standardized_text)
        cities = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
        money = next((ent.text.lower() for ent in doc.ents if ent.label_ == "MONEY"), None)

        for currency in self.info_services.currency_list:
            if currency in doc.text.lower():
                money = currency
                break

        command = self._determine_command(standardized_text)
        time_alarm = None

        if command == "будильник":
            try:
                time_alarm = self.scheduler.parse_time_from_text(standardized_text, self.config['AI_NAME'])
                logging.info(f"Распознанное время будильника: {time_alarm}")
            except Exception as e:
                logging.error(f"Время куда-то убежало! Догоните его: {e}")

        return command, cities, money, standardized_text, time_alarm

    def _determine_command(self, text: str) -> Optional[str]:
        commands = {
            "найди_видео": lambda t: "видео" and any(word in t for word in ["найди", "поищи", "покажи"]),
            "открой_видео": lambda t: "открой видео" in t,
            "время": lambda t: "время" in t or "времени" in t,
            "погода": lambda t: "погода" in t,
            "новости": lambda t: "новости" in t,
            "курс": lambda t: any(kw in t for kw in ["курс", "доллар", "евро", "гривна"]),
            "википедия": lambda t: "википедия" in t or "что такое" in t,
            "шутка": lambda t: "шутка" in t or "анекдот" in t,
            "сказка": lambda t: "сказку" in t or "историю" in t,
            "панель_управления": lambda t: "управления" in t and any(kw in t for kw in ["открой", "включи"]),
            #"открой": lambda t: "открой" in t or "найди" in t,
            "закрой_вкладку": lambda t: "закрой" in t and "вкладку" in t,
            "закрой_окно": lambda t: "закрой" in t and "вкладку" in t,
            "пора_спать": lambda t: "отключись" in t or "выключись" in t,
            "будильник": lambda t: any(kw in t for kw in ["будильник", "разбуди", "поставь"]) and "будильник" in t,
            "ютуб": lambda t: "ютуб" in t and any(kw in t for kw in ["открой", "включи"]),
            "музыку": lambda t: "включи" in t and "музыку" in t,
            "аниме": lambda t: "включи" in t and any(kw in t for kw in ["аниме", "анимешку"]),
            "чипи": lambda t: "деградировать" in t,
            "хитрая_музыка": lambda t: "подлая" in t or "хитрая" in t and "музыка" in t,
            "пауза": lambda t: any(kw in t for kw in ["пауза", "паузу", "стоп"]),
            "продолжить": lambda t: any(kw in t for kw in ["продолжить", "возобнови видео"]),
            "громче": lambda t: any(kw in t for kw in ["сделай громче", "увеличь громкость"]),
            "тише": lambda t: any(kw in t for kw in ["сделай тише", "уменьши громкость"]),
            "перемешать": lambda t: any(kw in t for kw in ["перемешай", "случайный порядок"]),
            "повтор": lambda t: any(kw in t for kw in ["повторять", "зациклить"]),
            "полный_экран": lambda t: any(kw in t for kw in ["полный экран", "развернуть"]),
            "субтитры": lambda t: any(kw in t for kw in ["субтитры", "титры"]),
            "качество": lambda t: any(kw in t for kw in ["качество", "разрешение"]),
            "мини_плеер": lambda t: any(kw in t for kw in ["мини-плеер", "маленькое окно"]),
            "ускорить": lambda t: any(kw in t for kw in ["ускорь", "быстрее"]),
            "замедлить": lambda t: any(kw in t for kw in ["замедли", "медленнее"]),
            "вперед": lambda t: any(kw in t for kw in ["вперед", "перемотай вперед"]),
            "назад": lambda t: any(kw in t for kw in ["назад", "перемотай назад"]),
            "в_начало": lambda t: any(kw in t for kw in ["в начало", "сначала" "в начала"]),
            "монетка": lambda t: any(kw in t for kw in ["монетка", "бросить монетку", "брось монетку"]),
            "привет": lambda t: any(word in t for word in ["привет", "здравствуй", "доброе утро", "добрый день", "добрый вечер"]),
            "пока": lambda t: any(word in t for word in ["пока", "до свидания", "прощай"]),
            "спокойной_ночи": lambda t: any(word in t for word in ["спокойной ночи", "доброй ночи"]),
            "спасибо": lambda t: any(word in t for word in ["спасибо", "благодарю"]),
            "скриншот": lambda t: "скриншот" in t or "снимок экрана" in t,
            "заметка": lambda t: "заметку" in t or "запиши" in t,
            "прочитай_заметки": lambda t: "прочитай" in t and "заметки" in t,
            "выключи_компьютер": lambda t: "выключи компьютер" in t,
            "перезагрузи": lambda t: "перезагрузи" in t or "перезагрузка" in t,
            "выйти": lambda t: "выйти из системы" in t or "разлогиниться" in t,
            "угадай_число": lambda t: "угадай число" in t or "поиграем в числа" in t,
            "игра_число": lambda t: any(str(i) for i in range(1, 101) if str(i) in t and self.entertainment.games.number_to_guess),
            "камень_ножницы_бумага": lambda t: "сыграем" in t and any(word in t for word in ["камень", "ножницы", "бумага"]),
            "напомни": lambda t: "напомни" in t.lower(),
            "покажи_напоминания": lambda t: "покажи" in t and "напоминания" in t,
        }

        for cmd, condition in commands.items():
            if condition(text):
                logging.info(f"Определена команда: {cmd}")
                return cmd
        return None


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
        self.social = SocialInteractions()
        self.last_activity = time.time()
        self.restart_timeout = self.config.get("RESTART_TIMEOUT", 30) * 60  # Конвертируем минуты в секунды

        self.is_running = True  # Флаг для контроля работы ассистента
        self.reminder = Reminder()  # Создаем экземпляр класса Reminder

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
            old_config = self.config.copy()
            self.load_config()
            
            # Обновляем компоненты, которые зависят от конфигурации
            if old_config.get('AI_NAME') != self.config.get('AI_NAME'):
                self.command_processor = CommandProcessor(self.config, self.info_services, self.scheduler)
            
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
        self.command_processor = CommandProcessor(
            self.config,
            self.info_services,
            self.scheduler
        )
        
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
                            
                        command, cities, money, standardized_text, time_alarm = (
                            self.command_processor.extract_entities(text)
                        )
                        if command:
                            await self.handle_command(command, cities, money, time_alarm, standardized_text)

                # Проверяем напоминания
                reminder_notification = self.reminder.check_reminders()
                if reminder_notification:
                    self.speak(reminder_notification)

            except Exception as e:
                logging.error(f"Аудиопоток запутался в своих битах: {e}")
                await asyncio.sleep(0.1)

    async def handle_command(self, command: str, cities: List[str], money: str, 
                           time_alarm: str, text: str) -> None:
        try:
            self.stream.stop_stream()
            self.is_speaking = True
            response = None

            match command:
                case "будильник":
                    time_str = self.scheduler.parse_time_from_text(text, self.config["AI_NAME"])
                    if time_str:
                        logging.info(f"Распознанное время будильника: {time_str}")
                        response = self.scheduler.set_alarm(time_str)
                        logging.info(f"Ответ будильника: {response}")
                    else:
                        response = "Не удалось распознать время для будильника"
                
                case "погода" if cities:
                    response = self.info_services.get_weather(cities[0])
                    logging.info(f"Погода: {response}")
                
                case "шутка":
                    response = self.entertainment.programmer_joke()
                    logging.info(f"Шутка: {response}")
                
                case "курс" if money:
                    response = self.info_services.get_money_info(money)
                    logging.info(f"Курс валюты: {response}")
                
                case "ютуб":
                    response = "Открываю YouTube"
                    self.media_controller.open_enum_url(Urls.YOUTUBE)
                    logging.info(response)
                
                case "аниме":
                    response = "Открываю аниме"
                    self.media_controller.open_enum_url(Urls.RANDOM_ANIME)
                    logging.info(response)
                
                case "новости":
                    response = "Открываю новости"
                    self.media_controller.open_enum_url(Urls.BBC_NEWS)
                    logging.info(response)
                
                case "музыку":
                    response = "Музыка включена"
                    self.media_controller.open_enum_url(Urls.LOFI_HIP_HOP)
                    logging.info(response)
                
                case "хитрая_музыка":
                    response = "Хитрая музыка включена"
                    self.media_controller.open_enum_url(Urls.TRICKY_MUSIC)
                    logging.info(response)
                
                case "чипи":
                    response = "Включаю чипи чипи"
                    self.media_controller.open_enum_url(Urls.CHIPI_CHIPI)
                    logging.info(response)
                
                case "википедия":
                    response = self.info_services.search_for_definition(text, "ru", self.config["AI_NAME"])
                    logging.info(f"{response}")
                
                case "время":
                    response = self.scheduler.get_current_time()
                    logging.info(f"{response}")
                
                case "сказка":
                    response = self.entertainment.generate_fairytale()
                    logging.info(f"{response}")
                
                case "закрой_вкладку":
                    response = "Закрываю вкладку"
                    self.media_controller.tab_close()
                    logging.info(response)
                
                case "закрой_окно":
                    response = "Закрываю окно"
                    self.media_controller.window_close()
                    logging.info(response)
                
                case "пора_спать":
                    response = "Выключаю компьютер"
                    self.system_controller.shutdown()
                    logging.info(response)
                
                case "монетка":
                    response = self.entertainment.toss_coin()
                    logging.info(f"Результат броска: {response}")
                
                case "пауза":
                    response = "Ставлю на паузу"
                    self.media_controller.execute_action(MusicAction.PLAY_PAUSE)
                    logging.info(response)
                
                case "продолжить":
                    response = "Продолжаю воспроизведение"
                    self.media_controller.execute_action(MusicAction.PLAY_PAUSE)
                    logging.info(response)
                
                case "громче":
                    response = "Делаю громче"
                    self.media_controller.execute_action(MusicAction.VOLUME_UP)
                    logging.info(response)
                
                case "тише":
                    response = "Делаю тише"
                    self.media_controller.execute_action(MusicAction.VOLUME_DOWN)
                    logging.info(response)
                
                case "перемешать":
                    response = "Перемешиваю"
                    self.media_controller.execute_action(MusicAction.SHUFFLE)
                    logging.info(response)
                
                case "повтор":
                    response = "Включаю повтор"
                    self.media_controller.execute_action(MusicAction.LOOP)
                    logging.info(response)
                
                case "полный_экран":
                    response = "Разворачиваю на весь экран"
                    self.media_controller.execute_action(MusicAction.FULLSCREEN)
                    logging.info(response)
                
                case "субтитры":
                    response = "Переключаю субтитры"
                    self.media_controller.execute_action(MusicAction.SUBTITLES)
                    logging.info(response)
                
                case "мини_плеер":
                    response = "Включаю мини-плеер"
                    self.media_controller.execute_action(MusicAction.MINI_PLAYER)
                    logging.info(response)
                
                case "ускорить":
                    response = "Ускоряю воспроизведение"
                    self.media_controller.execute_action(MusicAction.SPEED_UP)
                    logging.info(response)
                
                case "замедлить":
                    response = "Замедляю воспроизведение"
                    self.media_controller.execute_action(MusicAction.SPEED_DOWN)
                    logging.info(response)
                
                case "вперед":
                    response = "Перематываю вперед"
                    self.media_controller.execute_action(MusicAction.SEEK_FORWARD)
                    logging.info(response)
                
                case "назад":
                    response = "Перематываю назад"
                    self.media_controller.execute_action(MusicAction.SEEK_BACKWARD)
                    logging.info(response)
                
                case "в_начало":
                    response = "Возвращаюсь в начало"
                    self.media_controller.execute_action(MusicAction.JUMP_TO_START)
                    logging.info(response)
                
                case "привет":
                    response = self.social.get_greeting()
                    logging.info(f"Приветствие: {response}")
                
                case "пока":
                    response = self.social.get_goodbye()
                    logging.info(f"Прощание: {response}")
                
                case "спокойной_ночи":
                    response = self.social.get_good_night()
                    logging.info(f"Пожелание спокойной ночи: {response}")
                
                case "спасибо":
                    response = self.social.get_thanks()
                    logging.info(f"Ответ на благодарность: {response}")
                
                case "покажи_будильники":
                    response = self.scheduler.get_active_alarms()
                    logging.info(f"Список будильников: {response}")
                
                case "очисти_будильники":
                    response = self.scheduler.clear_alarms()
                    logging.info(response)
                
                case "скриншот":
                    response = self.system_controller.take_screenshot()
                    logging.info(f"Сделан скриншот: {response}")
                
                case "выключи_компьютер":
                    response = self.system_controller.shutdown()
                    logging.info("Выключение компьютера")
                
                case "перезагрузи":
                    response = self.system_controller.restart()
                    logging.info("Перезагрузка компьютера")
                
                case "выйти":
                    response = self.system_controller.logout()
                    logging.info("Выход из системы")

                case "найди_видео" | "открой_видео":
                    query = self.media_controller.extract_video_query(text, self.config["AI_NAME"])
                    if query:
                        response = self.media_controller.search_youtube(query)
                        logging.info(f"Поиск видео: {query}")
                    else:
                        response = "Не удалось понять, какое видео вы ищете"
                        logging.warning("Пустой запрос для поиска видео")

                case "угадай_число":
                    response = self.entertainment.games.play_number_game()
                    logging.info(f"Начата игра в угадай число: {response}")

                case "игра_число":
                    response = self.entertainment.games.play_number_game(text)
                    logging.info(f"Ход в игре угадай число: {response}")

                case "камень_ножницы_бумага":
                    choice = next((word for word in ["камень", "ножницы", "бумага"] if word in text.lower()), None)
                    if choice:
                        response = self.entertainment.games.play_rock_paper_scissors(choice)
                        logging.info(f"Игра КНБ: {response}")
                    else:
                        response = "Выберите: камень, ножницы или бумага!"

                case "напомни":
                    text_without_command = text.lower().replace("напомни", "").strip()
                    time_str = self.scheduler.parse_time_from_text(text_without_command, self.config["AI_NAME"])
                    if time_str:
                        reminder_text = text_without_command.replace(time_str, "").strip()
                        reminder_time = datetime.strptime(time_str, "%H:%M")
                        today = datetime.now()
                        reminder_datetime = datetime(
                            today.year, today.month, today.day,
                            reminder_time.hour, reminder_time.minute
                        )
                        response = self.reminder.add_reminder(reminder_text, reminder_datetime)
                    else:
                        response = "Не удалось распознать время напоминания"
                    logging.info(f"Создано напоминание: {response}")

                case "покажи_напоминания":
                    response = self.reminder.get_active_reminders()
                    logging.info("Запрошен список напоминаний")

        
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