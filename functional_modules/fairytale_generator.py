import logging
import os

import google.generativeai as genai
from dotenv import load_dotenv


def generate_fairytale(theme=None):
    try:
        dotenv_path = os.path.join(os.path.dirname(__file__))
        parent_dir = os.path.dirname(dotenv_path)
        end_dotenv_path = os.path.join(parent_dir, "api_keys.env")
        load_dotenv(end_dotenv_path)
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

        if not GOOGLE_API_KEY:
            raise ValueError("Ой-ой! Кажется, API ключ Google решил поиграть в прятки! Проверьте .env файл, может он там притаился?")

        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-pro')

        if theme:
            prompt = (
                f"Сочини короткую детскую сказку на тему '{theme}'. "
                "Сказка должна быть на русском языке, не длиннее 500 слов."
            )
        else:
            prompt = "Сочини короткую детскую сказку на русском языке. Сказка должна быть не длиннее 500 слов."

        response = model.generate_content(prompt)

        if response.text:
            logging.info("Ура! Сказочная фея успешно наколдовала новую историю!")
            return response.text
        else:
            raise ValueError("Упс! Похоже, сказочная фея взяла выходной - получен пустой ответ!")

    except Exception as e:
        logging.error(f"Ой-ёй! Сказка споткнулась о камешек и упала: {e}")
        return "Ой! Кажется, все сказочные персонажи ушли на обед. Попробуйте заглянуть попозже, когда они вернутся!"
