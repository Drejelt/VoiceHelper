"""
На данный момент (01.15.2025, М.Д.Г.) проект не завершён. В планах:

    Разобраться с .env файлом.
    Возможно, дообучить модель Vosk (или использовать более мощную).
    Добавить дополнительные возможности (возможно, с использованием нейросетей).
    Доработать webbrowser_module.py.

Из того, что сделано хотя бы частично с предыдущего коммита:

    Добавлена озвучка (нужно поиграться со скоростью, но в принципе работает).
    Перенос конфигурации в отдельные файлы (конфигурация модели теперь хранится в JSON, и её можно редактировать через сайт).
    Добавлена веб-панель управления с дашбордами (частично; веб-панель есть, но пока её функционал ограничен только редактированием JSON конфигурации).
    Проведен рефакторинг кода, попытался привести его в читаемый вид.
    Доработан jokes_module.py (теперь он получает шутки с API, а если доступа нет, — с PyJokes).
    Доработан exchange_rates.py (Теперь он берёт данные с API, а если доступа нет - с Google )

Что не сделано:

    Не придумал функционала, который можно реализовать с нейросетями.
    webbrowser_module был слегка изменён, но он продолжит изменяться.
    Я не разобрался с .env файлом, и он пока лежит в functional_modules, потому что не хочу жёстко прописывать путь.

Что в планах:

    Вывод логов напрямую в панель управления (без возможности их изменять).
    Отправка логов через Telegram API.
    Вывод панели управления в сеть с помощью ngrok и команды в Telegram с последующей отправкой ссылки.
    Привести в порядок панель управления, сделать переадресацию с 127.0.0.1:8080 на 127.0.0.1:8000/docs, добавить авторизацию или WhiteList.
    Добавить возможность поиска видео на YouTube, расширить вариативность новостных сайтов, возможно, добавить поиск музыки и её воспроизведение без открытия YouTube в браузере (только звук).
    Начать определение валюты/времени в зависимости от местоположения пользователя (есть два варианта: 1. указывать в JSON файле, 2. определять по IP-адресу).

"""

import json, pyaudio, vosk, spacy, asyncio, threading, re, dateparser, webrtcvad, pyttsx3, sys

from functional_modules.weather import call_weather_api
from functional_modules.dictionary_declensions import dictionary_declensions
from functional_modules.jokes_module import programmer_joke
from functional_modules.exchange_rates import get_money_info, currency_list
from functional_modules.alarm_clock import start_alarm_thread, get_current_time
from functional_modules.webbrowser_module import *
import functional_modules.logger_config

class AudioProcessor:
    def __init__(self, sample_rate, buffer_size):
        self.pyaudio_instance = pyaudio.PyAudio()
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        
    def setup_stream(self):
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
            logging.error(f"Ошибка инициализации аудиопотока: {e}")
            raise

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        
    def load(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
            self._validate_config(config)
            logging.info("Конфигурация успешно загружена.")
            return config
        except Exception as e:
            logging.error(f"Ошибка загрузки конфигурации: {e}")
            raise
            
    def _validate_config(self, config):
        required_keys = ["AI_NAME", "MODEL_PATH", "SAMPLE_RATE", "BUFFER_SIZE", "FRAME_DURATION_MS", "VAD_MODE"]
        for key in required_keys:
            if key not in config:
                raise KeyError(f"Отсутствует требуемый ключ-значение конфигурации: {key}")

class CommandProcessor:
    def __init__(self, config):
        self.config = config
        self.nlp = spacy.load("ru_core_news_sm")
        
    def extract_entities(self, text):
        doc = self.nlp(text)
        cities, money, command, time_alarm = [], None, None, None

        if self.config["AI_NAME"].lower() not in text.lower():
            return None, None, None, None, None

        cities, money = self._extract_entities_from_doc(doc)
        command = self._determine_command(text)
        time_alarm = self._extract_time_alarm(command, text)
        
        if command == "википедия":
            query = self._extract_wiki_query(text)
            cities = [query] if query else []

        return command, cities, money, text, time_alarm
        
    def _extract_entities_from_doc(self, doc):
        cities = []
        money = None
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:
                cities.append(ent.text)
            elif ent.label_ == "MONEY":
                money = ent.text.lower()
                
        for currency in currency_list:
            if currency in doc.text.lower():
                money = currency
                break
                
        return cities, money
        
    def _determine_command(self, text):
        commands = {
            "погода": lambda t: "погода" in t,
            "новости": lambda t: "новости" in t,
            "ютуб": lambda t: "ютуб" in t and any(kw in t for kw in ["открой", "включи"]),
            "шутка": lambda t: "шутка" in t or "анекдот" in t,
            "курс": lambda t: any(kw in t for kw in ["курс", "доллар", "евро", "гривна"]),
            "музыку": lambda t: "включи" in t and "музыку" in t,
            "аниме": lambda t: "включи" in t and any(kw in t for kw in ["аниме", "анимешку"]),
            "чипи": lambda t: "пора" in t or "деградировать" in t,
            "хитрая_музыка": lambda t: "подлая" in t or "хитрая" in t and "музыка" in t,
            "будильник": lambda t: "установи" in t or "поставь" in t and "будильник" in t,
            "время": lambda t: "время" in t or "времени" in t,
            "википедия": lambda t: "википедия" in t or "что такое" in t,
            "панель_управления": lambda t: "управления" in t and any(kw in t for kw in ["открой", "включи"]),
            "пора_спать": lambda t: "отключись" in t and any(kw in t for kw in ["отключись", "выключись"]),
        }
        
        for cmd, condition in commands.items():
            if condition(text):
                return cmd
        return None
        
    def _extract_time_alarm(self, command, text):
        if command == "будильник":
            return self.parse_time_from_text(text)
        return None
        
    def _extract_wiki_query(self, text):
        return re.sub(rf"\b({self.config['AI_NAME']}|определи|википедия|что такое)\b", "", text, flags=re.IGNORECASE).strip()
        
    def parse_time_from_text(self, text):
        text = re.sub(r"\b({self.config['AI_NAME']}|поставь|будильник|на|определи|википедия|что такое)\b", "", text, flags=re.IGNORECASE).strip()
        try:
            parsed_date = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
            return parsed_date.strftime("%H:%M") if parsed_date else None
        except Exception as e:
            logging.error(f"Ошибка парсинга времени: {e}")
            return None

class VoiceAssistant:
    def __init__(self, config_path="json/model_config.json"):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load()
        
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.config.get("VAD_MODE", 3))
        
        self.audio_processor = AudioProcessor(self.config["SAMPLE_RATE"], self.config["BUFFER_SIZE"])
        self.stream = self.audio_processor.setup_stream()
        
        self.model = vosk.Model(self.config["MODEL_PATH"])
        self.rec = vosk.KaldiRecognizer(self.model, self.config["SAMPLE_RATE"])
        
        self.command_processor = CommandProcessor(self.config)
        
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)
        self.tts_engine.setProperty('voice', 'russian')

    def reload_config(self):
        self.config = self.config_manager.load()
        logging.info("Конфигурация перезагружена")

    def start_voice_assistant(self):
        asyncio.run(self.process_audio_stream())

    async def process_audio(self):
        while True:
            data = self.stream.read(self.config["BUFFER_SIZE"], exception_on_overflow=False)
            if self.rec.AcceptWaveform(data):
                yield json.loads(self.rec.Result()).get("text", "")

    async def process_audio_stream(self):
        async for text in self.process_audio():
            command, cities, money, _, time_alarm = await self.recognize_speech(text)
            if command:
                await self.handle_command(command, cities, money, time_alarm)

    async def recognize_speech(self, text):
        if text:
            logging.info(f"Расспознано: {text}")
            standardized_text = dictionary_declensions(text)
            return self.command_processor.extract_entities(standardized_text)
        return None, None, None, None, None

    async def handle_command(self, command, cities, money, time_alarm):
        try:
            response = None
            if command == "погода" and cities:
                for city in cities:
                    response = call_weather_api(city)
                    logging.info(f"{response}")
            elif command == "шутка":
                response = programmer_joke()
                logging.info(f"{response}")
            elif command == "курс" and money:
                response = get_money_info(money)
                logging.info(f"{response}")
            elif command == "ютуб":
                response = "Открываю YouTube"
                open_enum_url(Urls.YOUTUBE)
                logging.info(response)
            elif command == "аниме":
                response = "Открываю аниме"
                open_enum_url(Urls.RANDOM_ANIME)
                logging.info(response)
            elif command == "новости":
                response = "Открываю новости"
                open_enum_url(Urls.BBC_NEWS)
                logging.info(response)
            elif command == "музыку":
                response = "Включаю музыку"
                open_enum_url(Urls.LOFI_HIP_HOP)
                logging.info(response)
            elif command == "хитрая_музыка":
                response = "Включаю хитрую музыку"
                open_enum_url(Urls.TRICKY_MUSIC)
                logging.info(response)
            elif command == "чипи":
                open_enum_url(Urls.CHIPI_CHIPI)
                logging.info(response)
            elif command == "википедия":
                for topic in cities:
                    response = search_for_definition(topic, "ru")
                    logging.info(response)
            elif command == 'время':
                response = get_current_time()
                logging.info(f"{response}")
            elif command == "будильник" and time_alarm:
                response = f"Будильник установлен на {time_alarm}"
                threading.Thread(target=start_alarm_thread, args=(time_alarm,), daemon=True).start()
                logging.info(response)
            elif command == "панель_управления":
                response = "Включаю панель управления"
                open_enum_url(Urls.CONTROL_PANEL)
                logging.info(response)

            if response:
                self.tts_engine.say(response)
                self.tts_engine.runAndWait()

        except ConnectionError as e:
            error_msg = f"Ошибка сети при обработке команды: {e}"
            logging.error(error_msg)
            self.tts_engine.say(error_msg)
            self.tts_engine.runAndWait()
        except ValueError as e:
            error_msg = f"Ошибка ввода при обработке команды: {e}"
            logging.error(error_msg)
            self.tts_engine.say(error_msg)
            self.tts_engine.runAndWait()
        except Exception as e:
            error_msg = f"Неожиданная ошибка при обработке команды: {e}"
            logging.error(error_msg)
            self.tts_engine.say(error_msg)
            self.tts_engine.runAndWait()

    def run(self):
        asyncio.run(self.process_audio_stream())
