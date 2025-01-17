import asyncio
import io
import json
import re
import threading
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
import dateparser
from gtts import gTTS
import pygame
import pyaudio
import pyttsx3
import requests
import spacy
import vosk
import webrtcvad

from functional_modules.alarm_clock import get_current_time, start_alarm_thread
from functional_modules.dictionary_declensions import dictionary_declensions
from functional_modules.exchange_rates import currency_list, get_money_info
from functional_modules.jokes_module import programmer_joke
import functional_modules.logger_config
from functional_modules.weather import call_weather_api
from functional_modules.webbrowser_module import *
from functional_modules.keyboard_shortcuts import *
from functional_modules.fairytale_generator import generate_fairytale

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

        if command == "открой":
            text = re.sub(rf"\b({self.config['AI_NAME']}|найди|открой)\b", "", text, flags=re.IGNORECASE).strip()
            cities = [text] if text else []

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
            "пора_спать": lambda t: "отключись" in t or "выключись" in t,
            "открой": lambda t: "открой" in t or "найди" in t,
            "сказка": lambda t: "сказку" in t or "историю" in t,
            "закрой_вкладку": lambda t: "закрой" in t and "вкладку" in t,
            "закрой_окно": lambda t: "закрой" in t and "вкладку" in t,
            "найди_видео": lambda t: "найди" in t and "видео" in t,
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
        # Удаляем лишние слова
        text = re.sub(
            rf"\b({self.config['AI_NAME']}|поставь|будильник|на|установи)\b",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

        
        try:
            # Словарь для преобразования словесного времени в числа
            time_words = {
                'один': '1', 'одну': '1', 'первого': '1',
                'два': '2', 'две': '2', 'второго': '2',
                'три': '3', 'третьего': '3',
                'четыре': '4', 'четвертого': '4',
                'пять': '5', 'пятого': '5',
                'шесть': '6', 'шестого': '6',
                'семь': '7', 'седьмого': '7',
                'восемь': '8', 'восьмого': '8',
                'девять': '9', 'девятого': '9',
                'десять': '10', 'десятого': '10',
                'одиннадцать': '11', 'одиннадцатого': '11',
                'двенадцать': '12', 'двенадцатого': '12'
            }
            
            # Заменяем словесные числа на цифры
            for word, number in time_words.items():
                text = re.sub(rf'\b{word}\b', number, text, flags=re.IGNORECASE)
            
            # Пытаемся найти время в разных форматах
            patterns = [
                r'(\d{1,2})(?:\s*)?(?::|часов|час|часа)?(?:\s*)?(\d{2})?(?:\s*)?(?:утра|вечера|дня)?',
                r'(\d{1,2})(?:\s*)?(?:утра|вечера|дня)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2)) if match.group(2) else 0
                    
                    # Обработка времени с учетом периода дня
                    if 'вечера' in text.lower() and hours < 12:
                        hours += 12
                    elif 'утра' in text.lower() and hours == 12:
                        hours = 0
                    
                    now = datetime.now()
                    alarm_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                    
                    # Если время уже прошло, добавляем день
                    if alarm_time <= now:
                        alarm_time += timedelta(days=1)
                    
                    result_time = alarm_time.strftime("%H:%M")
                    return result_time
            
            # Если не удалось распарсить через регулярки, пробуем dateparser
            parsed_date = dateparser.parse(
                text,
                languages=['ru'],
                settings={'PREFER_DATES_FROM': 'future'}
            )
            
            if parsed_date:
                now = datetime.now()
                if parsed_date < now:
                    parsed_date += timedelta(days=1)
                
                result_time = parsed_date.strftime("%H:%M")
                logging.info(f"Успешно распарсено время через dateparser: {result_time}")
                return result_time
                
            logging.error(f"Не удалось распарсить время из текста: {text}")
            return None
                
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

        # Инициализация pygame для воспроизведения аудио
        pygame.mixer.init()
        
        # Fallback TTS движок
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 180)
        self.tts_engine.setProperty('voice', 'russian')

    def reload_config(self):
        self.config = self.config_manager.load()
        logging.info("Конфигурация перезагружена")

    def start_voice_assistant(self):
        asyncio.run(self.process_audio_stream())

    async def process_audio(self):
        while True:
            if not self.stream.is_active():  # Проверяем, активен ли поток
                logging.warning("Попытка чтения остановленного потока. Пропуск итерации.")
                await asyncio.sleep(0.1)  # Небольшая задержка перед повторной проверкой
                continue

            try:
                data = self.stream.read(self.config["BUFFER_SIZE"], exception_on_overflow=False)
                if self.rec.AcceptWaveform(data):
                    yield json.loads(self.rec.Result()).get("text", "")
            except OSError as e:
                logging.error(f"Ошибка аудиопотока: {e}")
                await asyncio.sleep(0.1)  # Небольшая задержка для восстановления потока

    async def process_audio_stream(self):
        async for text in self.process_audio():
            command, cities, money, original_text, time_alarm = await self.recognize_speech(text)
            if command:
                await self.handle_command(command, cities, money, time_alarm, original_text)

    async def recognize_speech(self, text):
        if text:
            logging.info(f"Расспознано: {text}")
            standardized_text = dictionary_declensions(text)
            return self.command_processor.extract_entities(standardized_text)
        return None, None, None, None, None

    def resume_stream(self):
        if not self.stream.is_active():
            self.stream.start_stream()
            logging.info("Аудиопоток возобновлён.")

    def speak(self, text):
        try:
            # Пробуем использовать gTTS
            tts = gTTS(text=text, lang='ru')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            
            # Воспроизводим с помощью pygame
            pygame.mixer.music.load(fp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
        except Exception as e:
            logging.error(f"Ошибка gTTS: {e}. Использую резервный движок.")
            # Используем резервный движок если gTTS недоступен
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    async def handle_command(self, command, cities, money, time_alarm, text):
        try:
            self.stream.stop_stream()
            self.is_speaking = True
            response = None

            if command == "будильник":
                parsed_time = self.command_processor.parse_time_from_text(text)
                
                if parsed_time:
                    alarm_thread = threading.Thread(
                        target=start_alarm_thread,
                        args=(parsed_time,),
                        daemon=True
                    )
                    alarm_thread.start()
                    response = f"Будильник установлен на {parsed_time}"
                else:
                    response = "Извините, не удалось распознать время для будильника"
                logging.info(f"Установка будильника: {response}")

            elif command == "погода" and cities:
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
                response = "музыка включена"
                open_enum_url(Urls.LOFI_HIP_HOP)
                logging.info(response)
            elif command == "хитрая_музыка":
                response = "хитрая музыка включена"
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
            elif command == "панель_управления":
                response = "Включаю панель управления"
                open_enum_url(Urls.CONTROL_PANEL)
                logging.info(response)
            elif command == "сказка":
                response = generate_fairytale()
                logging.info(response)
            elif command == "закрой_вкладку":
                response = "Выполняю"
                tab_close()
                logging.info(response)
            elif command == "закрой_окно":
                response = "Выполняю"
                window_close()
                logging.info(response)
            elif command == "найди_видео":
                search_text = re.sub(
                    rf"\b({self.config['AI_NAME']}|найди|видео)\b", 
                    "", 
                    text, 
                    flags=re.IGNORECASE
                ).strip()
                if search_text:
                    response = f"Ищу видео по запросу: {search_text}"
                    search_youtube(search_text)
                    logging.info(response)
                else:
                    response = "Не удалось распознать поисковый запрос"
                    logging.warning(response)
            elif command == "открой":
                if cities:
                    query = " ".join(cities)
                    try:
                        # Поиск в Google и получение первой ссылки
                        google_search_url = f"https://google.com/search?q={query.replace(' ', '+')}"
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        search_response = requests.get(google_search_url, headers=headers)
                        soup = BeautifulSoup(search_response.text, 'html.parser')
                        first_link = soup.find('div', class_='yuRUbf')
                        if first_link and first_link.find('a'):
                            url = first_link.find('a')['href']
                            webbrowser.open(url)
                            response = f"Открываю первый результат по запросу '{query}'"
                        else:
                            webbrowser.open(google_search_url)
                            response = f"Показываю результаты поиска для '{query}'"
                    except Exception as e:
                        webbrowser.open(google_search_url)
                        response = f"Показываю результаты поиска для '{query}'"
                    logging.info(response)

            if response:
                self.speak(response)

        except Exception as e:
            error_msg = f"Неожиданная ошибка при обработке команды: {e}"
            logging.error(error_msg)
            self.speak(error_msg)
        finally:
            self.resume_stream()
            self.is_speaking = False
            logging.info("Завершение обработки команды.")

    def run(self):
        asyncio.run(self.process_audio_stream())



