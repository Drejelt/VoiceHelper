import asyncio
import io
import json

import pygame  # Для музыкального сопровождения наших приключений
import pyaudio  # Чтобы слышать голос пользователя
import pyttsx3
import spacy  # Для понимания человеческой речи (или хотя бы попытки)
import vosk  # Для распознавания речи (когда не хочется платить Google)
import webrtcvad  # Отличает речь от чихания
from gtts import gTTS  # Google Text-to-Speech, когда хочется звучать как навигатор

# Импортируем наши самописные модули (сделано с любовью)
import functional_modules.logger_config
from functional_modules.alarm_clock import (  # Будильник (враг сна и моих нервов)
    get_current_time,
    parse_time_from_text,
    set_alarm,
)
from functional_modules.dictionary_declensions import dictionary_declensions  # Для борьбы с падежами
from functional_modules.exchange_rates import currency_list, get_money_info
from functional_modules.fairytale_generator import generate_fairytale  # Сказки на ночь
from functional_modules.jokes_module import programmer_joke  # Юмор (осторожно, очень сухой)
from functional_modules.keyboard_shortcuts import *  # Магические сочетания клавиш
from functional_modules.weather import call_weather_api  # Узнаём погоду (спойлер: опять дождь)
from functional_modules.webbrowser_module import *  # Для путешествий по интернетам


class AudioProcessor:  # Мастер по обработке звука
    def __init__(self, sample_rate, buffer_size):
        self.pyaudio_instance = pyaudio.PyAudio()
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

    def setup_stream(self):  # Настраиваем микрофон (если он не сломан)
        try:
            stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,  # Моно, потому что мы экономные
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.buffer_size,
            )
            logging.info("Аудиопоток инициализирован.")
            return stream
        except Exception as e:
            logging.error(f"Ой-ой! Микрофон решил взять выходной: {e}")
            raise


class ConfigManager:  # Хранитель настроек и тайн
    def __init__(self, config_path):
        self.config_path = config_path

    def load(self):  # Загружаем конфиг (если он не спрятался)
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
            self._validate_config(config)
            logging.info("Конфигурация успешно загружена.")
            return config
        except Exception as e:
            logging.error(f"Упс! Конфигурация сбежала в отпуск: {e}")
            raise

    def _validate_config(self, config):  # Проверяем, все ли ключи на месте
        required_keys = [
            "AI_NAME",  # Как зовут нашего джина
            "MODEL_PATH",  # Где живёт его мозг
            "SAMPLE_RATE",  # Частота дискретизации
            "BUFFER_SIZE",  # Размер буфера, что-бы не захлебнуться
            "FRAME_DURATION_MS",  # Длительность кадра в миллисекундах
            "VAD_MODE"  # Режим определения голоса (от 0 до 3, где 3 - самый придирчивый)
        ]
        for key in required_keys:
            if key not in config:
                raise KeyError(f"Караул! Потеряли важный ключ {key}! Кто-нибудь видел его?")


class CommandProcessor:  # Переводчик с человеческого на компьютерный
    def __init__(self, config):
        self.config = config
        self.nlp = spacy.load("ru_core_news_sm")  # Загружаем русский язык (все 150МБ его)

    def extract_entities(self, text):  # Извлекаем смысл из сказанного (если он там есть)
        if self.config["AI_NAME"].lower() not in text.lower():
            return None, None, None, None, None

        standardized_text = dictionary_declensions(text)

        doc = self.nlp(standardized_text)
        cities = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]  # Ищем города
        money = next((ent.text.lower() for ent in doc.ents if ent.label_ == "MONEY"), None)  # Ищем валюты

        for currency in currency_list:  # Проверяем упоминания валют
            if currency in doc.text.lower():
                money = currency
                break

        command = self._determine_command(standardized_text)
        time_alarm = None

        if command == "будильник":
            try:
                time_alarm = parse_time_from_text(standardized_text, self.config['AI_NAME'])
                logging.info(f"Распознанное время будильника: {time_alarm}")
            except Exception as e:
                logging.error(f"Время куда-то убежало! Догоните его: {e}")

        return command, cities, money, standardized_text, time_alarm

    def _determine_command(self, text):  # Определяем, чего же хочет пользователь
        commands = {
            "найди_видео": lambda t: "найди" in t and "видео" in t,
            "погода": lambda t: "погода" in t,  # Для метеозависимых
            "новости": lambda t: "новости" in t,  # Для любителей быть в курсе
            "ютуб": lambda t: "ютуб" in t and any(kw in t for kw in ["открой", "включи"]),
            "шутка": lambda t: "шутка" in t or "анекдот" in t,  # Для поднятия настроения
            "курс": lambda t: any(kw in t for kw in ["курс", "доллар", "евро", "гривна"]),
            "музыку": lambda t: "включи" in t and "музыку" in t,  # Для меломанов
            "аниме": lambda t: "включи" in t and any(kw in t for kw in ["аниме", "анимешку"]),  # Для отаку
            "чипи": lambda t: "пора" in t or "деградировать" in t,  # Когда совсем всё плохо
            "хитрая_музыка": lambda t: "подлая" in t or "хитрая" in t and "музыка" in t,
            "будильник": lambda t: any(kw in t for kw in ["будильник", "разбуди", "поставь"]) and "будильник" in t,
            "время": lambda t: "время" in t or "времени" in t,  # Для опаздывающих
            "википедия": lambda t: "википедия" in t or "что такое" in t,  # Для любознательных
            "панель_управления": lambda t: "управления" in t and any(kw in t for kw in ["открой", "включи"]),
            "пора_спать": lambda t: "отключись" in t or "выключись" in t,  # Для уставших
            "открой": lambda t: "открой" in t or "найди" in t,
            "сказка": lambda t: "сказку" in t or "историю" in t,  # Для любителей погрузиться в детство
            "закрой_вкладку": lambda t: "закрой" in t and "вкладку" in t,
            "закрой_окно": lambda t: "закрой" in t and "вкладку" in t,
        }

        for cmd, condition in commands.items():
            if condition(text):
                logging.info(f"Определена команда: {cmd}")
                return cmd
        return None


class VoiceAssistant:  # Главный класс нашего искусственного идиота
    def __init__(self, config_path="json/model_config.json"):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load()

        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.config.get("VAD_MODE", 3))

        self.audio_processor = AudioProcessor(
            self.config["SAMPLE_RATE"],
            self.config["BUFFER_SIZE"]
        )
        self.stream = self.audio_processor.setup_stream()

        self.model = vosk.Model(self.config["MODEL_PATH"])
        self.rec = vosk.KaldiRecognizer(self.model, self.config["SAMPLE_RATE"])

        self.command_processor = CommandProcessor(self.config)

        # Инициализация pygame для воспроизведения аудио
        pygame.mixer.init()

        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 180)  # Скорость речи (чтобы не тараторил)
        self.tts_engine.setProperty('voice', 'russian')  # Говорим по-русски

    def reload_config(self):  # Перезагружаем конфиг (если что-то изменилось)
        self.config = self.config_manager.load()
        logging.info("Конфигурация перезагружена")

    def start_voice_assistant(self):  # Запускаем нашего электронного огузка
        asyncio.run(self.process_audio_stream())

    async def process_audio(self):  # Обрабатываем аудиопоток
        while True:
            if not self.stream.is_active():  # Проверяем, не спит ли микрофон
                logging.warning("Ой! Аудиопоток прилёг вздремнуть. Подождём, пока проснётся...")
                await asyncio.sleep(0.1)  # Даём микрофону поспать
                continue

            try:
                data = self.stream.read(self.config["BUFFER_SIZE"], exception_on_overflow=False)
                if self.rec.AcceptWaveform(data):
                    yield json.loads(self.rec.Result()).get("text", "")
            except OSError as e:
                logging.error(f"Аудиопоток споткнулся и упал: {e}")
                await asyncio.sleep(0.1)  # Даём время на восстановление

    async def process_audio_stream(self):  # Основной цикл обработки
        async for text in self.process_audio():
            command, cities, money, original_text, time_alarm = await self.recognize_speech(text)
            if command:
                await self.handle_command(command, cities, money, time_alarm, original_text)

    async def recognize_speech(self, text):  # Распознаём речь
        if text:
            logging.info(f"Расспознано: {text}")
            standardized_text = dictionary_declensions(text)
            return self.command_processor.extract_entities(standardized_text)
        return None, None, None, None, None

    def resume_stream(self):  # Возобновляем поток после паузы
        if not self.stream.is_active():
            self.stream.start_stream()
            logging.info("Ура! Аудиопоток вернулся из отпуска!")

    def speak(self, text):  # Говорим пользователю
        try:
            tts = gTTS(text=text, lang='ru')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)

            # Воспроизводим с помощью pygame (потому что он крутой)
            pygame.mixer.music.load(fp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

        except Exception as e:
            logging.error(f"Голос сел! Переключаюсь на запасной: {e}")
            # План Б: используем pyttsx3
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()

    def _handle_alarm(self, time_alarm):  # Обработчик будильника
        return set_alarm(time_alarm)

    def _handle_weather(self, cities):  # Обработчик погоды
        if not cities:
            return "Эй! А город-то кто будет угадывать?"

        responses = []
        for city in cities:
            try:
                response = call_weather_api(city)
                responses.append(response)
                logging.info(f"Получен прогноз погоды для города {city}")
            except Exception as e:
                error_msg = f"Метеостанция в {city} ушла на обед: {e}"
                logging.error(error_msg)
                responses.append(error_msg)

        return " ".join(responses)

    async def handle_command(self, command, cities, money, time_alarm, text):  # Главный обработчик команд
        try:
            self.stream.stop_stream()  # Останавливаем поток, чтобы не слышать себя
            self.is_speaking = True
            response = None

            # Большой список if-elif для обработки всех возможных команд
            if command == "будильник":
                response = self._handle_alarm(time_alarm)
            elif command == "погода" and cities:
                response = self._handle_weather(cities)
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
                search_text = extract_video_query(text, self.config['AI_NAME'])
                response = search_youtube(search_text)
                logging.info(response)
            elif command == "открой":
                if cities:
                    query = " ".join(cities)
                    response = search_and_open(query)
                    logging.info(response)

            if response:
                self.speak(response)

        except Exception as e:
            error_msg = f"Ой-ой! Что-то пошло не так, и я в панике: {e}"
            logging.error(error_msg)
            self.speak(error_msg)
        finally:
            self.resume_stream()
            self.is_speaking = False
            logging.info("Миссия выполнена! Жду следующих приказаний.")

    def run(self):  # Запускаем всю эту махину
        asyncio.run(self.process_audio_stream())
