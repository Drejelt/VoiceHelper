"""
На данный момент (01.07.2025 (М.Д.Г)) проэкт не дописан, в планнах: добавить озвучку (Это уже в конце), добавить веб панель управления с дашбордами,
перенести конфигурацию в отдельные файлы, разделить main.py на отдельные модули, разобраться с .env файлом,
возможно дообучить модель vosk (Или использовать более большую), добавить возможность конфигурации запросов в удобном виде,
добавить больше доп.возможностей (может быть с использованием нейросетей), доработать webbrowser_module.py,
доработать jokes_module.py (Добавить возможность брать шутки с специальным API, а текущий код оставить как запасной.)
"""

# Импорты
import os, pyaudio, vosk, json, spacy, dateparser, re, threading, asyncio, webrtcvad, sys
from datetime import datetime, timezone

# Модули
from functional_modules.weather import call_weather_api
from functional_modules.dictionary_declensions import dictionary_declensions
from functional_modules.jokes_module import programmer_joke
from functional_modules.exchange_rates import get_money_info, currency_list
from functional_modules.alarm_clock import start_alarm_thread, get_current_time
from functional_modules.webbrowser_module import *

# Конфигурация
CONFIG = {
    "MODEL_PATH": "model/vosk-model-small-ru-0.22",
    "AI_NAME": "шут",
    "SAMPLE_RATE": 16000,
    "BUFFER_SIZE": 4000,
    "FRAME_DURATION_MS": 20,
}

AI_NAME = CONFIG["AI_NAME"].lower()
FRAME_SIZE = int(CONFIG["SAMPLE_RATE"] * (CONFIG["FRAME_DURATION_MS"] / 1000) * 2)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Инициализация VAD (детектор голосовой активности)
vad = webrtcvad.Vad()
vad.set_mode(3)

# Загрузка модели
if not os.path.exists(CONFIG["MODEL_PATH"]):
    logging.error(f"Модель не найдена по указанному пути: {CONFIG['MODEL_PATH']}")
    sys.exit(1)

# Инициализация Spacy и модели для распознавания речи
nlp = spacy.load("ru_core_news_sm")
model = vosk.Model(CONFIG["MODEL_PATH"])
rec = vosk.KaldiRecognizer(model, CONFIG["SAMPLE_RATE"])

# Настройка PyAudio
p = pyaudio.PyAudio()
try:
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=CONFIG["SAMPLE_RATE"],
        input=True,
        frames_per_buffer=CONFIG["BUFFER_SIZE"],
    )
    logging.info("Аудиопоток успешно инициализирован.")

except Exception as e:
    logging.error(f"Не удалось инициализировать аудиопоток: {e}")
    sys.exit(1)  # import sys


# Обработка аудио
def detect_speech_activity(frame, sample_rate=16000):
    """
    Определяет, содержит ли данный аудиофрейм речь.
    """
    try:
        if len(frame) not in [int(sample_rate * (d / 1000) * 2) for d in [10, 20, 30]]:
            raise ValueError("Длина фрейма должна быть 10мс, 20мс или 30мс.")
        return vad.is_speech(frame, sample_rate)
    except ValueError as e:
        logging.warning(f"Некорректная длина фрейма: {e}")
        raise


async def process_audio():
    """
    Непрерывная обработка аудио.
    """
    while True:
        data = stream.read(CONFIG["BUFFER_SIZE"], exception_on_overflow=False)
        if rec.AcceptWaveform(data):
            yield json.loads(rec.Result()).get("text", "")

async def process_audio_stream():
    """
    Непрерывная обработка аудиопотока и выполнение команд.
    """
    try:
        async for text in process_audio():
            command, cities, money, _, time_alarm = await recognize_speech(text)
            if command:
                await handle_command(command, cities, money, time_alarm)
    except Exception as e:
        logging.error(f"Ошибка при обработке аудио: {e}")

# Анализ текста
def parse_time_from_text(text):
    """
    Извлекает время из заданного текста с использованием dateparser.
    """
    logging.debug(f"Извлечение времени из текста: {text}")
    text = re.sub(r"\b(чай|поставь|будильник|на)\b", "", text, flags=re.IGNORECASE).strip()
    try:
        parsed_date = dateparser.parse(text, settings={
            'PREFER_DATES_FROM': 'future',
            'RELATIVE_BASE': datetime.now(timezone.utc),
        })
        return parsed_date.strftime("%H:%M") if parsed_date else None
    except Exception as e:
        logging.error(f"Ошибка при парсинге даты: {e}")
        return None

async def recognize_speech(text):
    if text:
        logging.info(f"Распознано: {text}")
        standardized_text = dictionary_declensions(text)
        return extract_entities(standardized_text)
    return None, None, None, None, None

def extract_entities(text):
    logging.debug(f"Извлечение сущностей из текста: {text}")
    doc = nlp(text)
    cities, money, command, time_alarm = [], None, None, None

    # Проверяем, упоминается ли имя ассистента в тексте
    if AI_NAME not in text.lower():
        return None, None, None, None, None

    # Извлечение сущностей (города, валюты и т.д.)
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            cities.append(ent.text)
        elif ent.label_ == "MONEY":
            money = ent.text.lower()

    for currency in currency_list:
        if currency in text.lower():
            money = currency
            break

    # Словарь команд и условий
    COMMANDS = {
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
    }

    # Поиск команды
    for cmd, condition in COMMANDS.items():
        if condition(text):
            command = cmd
            break

    # Обработка времени для будильника
    if command == "будильник":
        time_alarm = parse_time_from_text(text)

    # Если команда "википедия", извлекаем текст запроса
    if command == "википедия":
        query = re.sub(rf"\b({AI_NAME}|определи|википедия|что такое)\b", "", text, flags=re.IGNORECASE).strip()
        cities = [query] if query else []

    return command, cities, money, text, time_alarm

async def handle_command(command, cities, money, time_alarm):
    try:
        if command == "погода" and cities:
            for city in cities:
                weather_info = call_weather_api(city)
                logging.info(f"{weather_info}")
        elif command == "шутка":
            logging.info(f"Шутка: {programmer_joke()}")
        elif command == "курс" and money:
            logging.info(f"{get_money_info(money)}")
        elif command == "время":
            logging.info(f"{get_current_time()}")
        elif command == "будильник" and time_alarm:
            threading.Thread(target=start_alarm_thread, args=(time_alarm,), daemon=True).start()
        elif command == "ютуб":
            open_enum_url(Urls.YOUTUBE)
        elif command == "аниме":
            open_enum_url(Urls.RANDOM_ANIME)
        elif command == "новости":
            open_enum_url(Urls.BBC_NEWS)
        elif command == "музыку":
            open_enum_url(Urls.LOFI_HIP_HOP)
        elif command == "хитрая_музыка":
            open_enum_url(Urls.TRICKY_MUSIC)
        elif command == "чипи":
            open_enum_url(Urls.CHIPI_CHIPI)
        elif command == "википедия":
            for topic in cities:
                result = search_for_definition(topic, "ru")  # Используем русский язык
                logging.info(result)

    except ConnectionError as e:
        logging.error(f"Ошибка сети при обработке команды: {e}")
    except ValueError as e:
        logging.error(f"Ошибка ввода при обработке команды: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при обработке команды: {e}")

async def main():
    logging.info("Запуск голосового ассистента...")
    await process_audio_stream()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Завершение работы...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
