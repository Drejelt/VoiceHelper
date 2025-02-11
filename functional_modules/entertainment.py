import random
import requests
import os
import logging
from googletrans import Translator
import pyjokes
import google.generativeai as genai
from dotenv import load_dotenv

class Entertainment:
    def __init__(self):
        self.setup_api_keys()
        self.games = Games()
        
    def setup_api_keys(self):
        dotenv_path = os.path.join(os.path.dirname(__file__))
        parent_dir = os.path.dirname(dotenv_path)
        end_dotenv_path = os.path.join(parent_dir, "api_keys.env")
        load_dotenv(end_dotenv_path)
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        if self.google_api_key:
            genai.configure(api_key=self.google_api_key)

    def toss_coin(self) -> str:
        flips_count = 3
        heads = sum(1 for _ in range(flips_count) if random.randint(0, 1) == 0)
        tails = flips_count - heads
        winner = "Решка" if tails > heads else "Орёл"
        return f"{winner} победил!"

    def programmer_joke(self):
        try:
            url = "https://v2.jokeapi.dev/joke/Any"
            response = requests.get(url)
            if response.status_code == 200:
                joke_data = response.json()
                if joke_data['type'] == 'single':
                    joke = joke_data['joke']
                else:
                    joke = f"{joke_data['setup']} {joke_data['delivery']}"

                translator = Translator()
                translated_joke = translator.translate(joke, dest='ru')
                return translated_joke.text
        except requests.RequestException:
            try:
                joke = pyjokes.get_joke()
                translator = Translator()
                translated_joke = translator.translate(joke, dest='ru')
                return translated_joke.text
            except Exception:
                return joke

    def generate_fairytale(self, theme=None):
        try:
            if not self.google_api_key:
                raise ValueError("Ой-ой! API ключ Google играет в прятки. Кто-нибудь видел его?")

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
                logging.info("Сказка успешно сгенерирована")
                return response.text
            else:
                raise ValueError("Ой! Моя фантазия временно ушла в отпуск на Марс!")

        except Exception as e:
            logging.error(f"Ошибка при генерации сказки: {e}")
            return "Извините, но мой внутренний сказочник сейчас медитирует в Гималаях. Попробуйте позже!"

class Games:
    def __init__(self):
        self.number_to_guess = None
        self.quest_object = None
        self.quest_properties = None
        self.attempts = 0
        
    def play_number_game(self, text: str = None) -> str:
        if not self.number_to_guess:
            self.number_to_guess = random.randint(1, 100)
            self.attempts = 0
            return "Я загадал число от 1 до 100. Попробуйте угадать!"
            
        try:
            number = int(''.join(filter(str.isdigit, text)))
            self.attempts += 1
            
            if number == self.number_to_guess:
                result = f"Поздравляю! Вы угадали число {self.number_to_guess} за {self.attempts} попыток!"
                self.number_to_guess = None
                return result
            elif number < self.number_to_guess:
                return "Больше!"
            else:
                return "Меньше!"
        except:
            return "Назовите число от 1 до 100"
            
    def play_rock_paper_scissors(self, choice: str) -> str:
        choices = {
            "камень": "камень",
            "ножницы": "ножницы",
            "бумага": "бумага"
        }
        
        if choice.lower() not in choices:
            return "Выберите: камень, ножницы или бумага!"
            
        computer_choice = random.choice(list(choices.keys()))
        user_symbol = choices[choice.lower()]
        comp_symbol = choices[computer_choice]
        
        if choice.lower() == computer_choice:
            return f"Ничья! {user_symbol} vs {comp_symbol}"
        elif (
            (choice.lower() == "камень" and computer_choice == "ножницы") or
            (choice.lower() == "ножницы" and computer_choice == "бумага") or
            (choice.lower() == "бумага" and computer_choice == "камень")
        ):
            return f"Вы победили! {user_symbol} vs {comp_symbol}"
        else:
            return f"Я победил! {user_symbol} vs {comp_symbol}"