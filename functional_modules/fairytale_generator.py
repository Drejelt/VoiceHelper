import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging


def generate_fairytale(theme=None):
    try:
        # Загрузка API-ключа из файла .env
        dotenv_path = os.path.join(os.path.dirname(__file__), 'api_keys.env')
        load_dotenv(dotenv_path)
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

        if not GOOGLE_API_KEY:
            raise ValueError("API ключ Google не найден в .env файле")

        # Настройка Google Gemini API
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        # Формирование промпта
        if theme:
            prompt = (
                f"Сочини короткую детскую сказку на тему '{theme}'. "
                "Сказка должна быть на русском языке, не длиннее 500 слов."
            )
        else:
            prompt = "Сочини короткую детскую сказку на русском языке. Сказка должна быть не длиннее 500 слов."

        response = model.generate_content(prompt)

        if response.text:
            logging.info("Сказка успешно сгенерирована")
            return response.text
        else:
            raise ValueError("Получен пустой ответ от модели")

    except Exception as e:
        logging.error(f"Ошибка при генерации сказки: {e}")
        return "Извините, произошла ошибка при генерации сказки. Попробуйте позже."
