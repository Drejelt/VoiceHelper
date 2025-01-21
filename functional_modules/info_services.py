import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from dotenv import load_dotenv
import wikipediaapi
import json

class InfoServices:
    def __init__(self):
        self.setup_api_keys()
        with open("json/model_config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.currency_list = [
            "гривна", "доллар", "евро", "йена", "крона",
            "песо", "рубль", "рэал", "фунт", "франк", "юань"
        ]
        
    def setup_api_keys(self):
        dotenv_path = os.path.join(os.path.dirname(__file__))
        parent_dir = os.path.dirname(dotenv_path)
        end_dotenv_path = os.path.join(parent_dir, "api_keys.env")
        load_dotenv(end_dotenv_path)
        self.weather_api_key = os.getenv('WEATHER_API')

    def get_weather(self, city_name, units="metric", lang="ru"):
        if not self.weather_api_key:
            return "API ключ от погоды потерялся в облаках"
            
        try:
            base_url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city_name,
                "appid": self.weather_api_key,
                "units": units,
                "lang": lang
            }
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return (
                f"температура {data['main']['temp']:.1f}°C, "
                f"{data['weather'][0]['description']}, "
                f"скорость ветра {data['wind']['speed']} м/с"
            )
        except Exception as e:
            logging.error(f"Метеостанция ушла на перерыв: {e}")
            return f"Погода в городе {city_name} играет в прятки"

    def get_money_info(self, money_name="доллар"):
        try:
            api_url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = requests.get(api_url)
            response.raise_for_status()
            rates = response.json()["rates"]

            # Нормализуем входное название валюты
            money_name = money_name.lower().replace("доллара", "доллар")

            currency_codes = {
                "гривна": "UAH", "доллар": "USD", "евро": "EUR",
                "йена": "JPY", "крона": "SEK", "песо": "MXN",
                "рубль": "RUB", "рэал": "BRL", "фунт": "GBP",
                "франк": "CHF", "юань": "CNY"
            }

            if money_name in currency_codes:
                target_code = currency_codes[money_name]
                default_currency = self.config.get("DEFAULT_CURRENCY", "UAH")
                
                if target_code in rates:
                    target_rate = rates[target_code]
                    default_rate = rates[default_currency]
                    conversion_rate = default_rate / target_rate
                    
                    return f"Курс {money_name}: 1 {target_code} = {conversion_rate:.2f} {default_currency}"

            return self._get_money_info_from_google(money_name)
        except Exception as e:
            logging.error(f"Курсы валют ушли в отпуск: {e}")
            return "Биржа временно закрыта на переучёт"

    def _get_money_info_from_google(self, money_name):
        try:
            url = f"https://www.google.com/search?q=курс+{money_name.lower()}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (HTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            }
            
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            class_dict = {
                "title": "vLqKYe",
                "count": "DFlfde SwHCTb",
                "day": "k0Rg6d hqAUc",
            }
            
            title_money = soup.find(class_=class_dict["title"]).get_text(strip=True)
            count_money = soup.find(class_=class_dict["count"]).get_text(strip=True)
            
            return f"Курс валюты {title_money}: 1 USD = {count_money}"
        except Exception as e:
            logging.error(f"Ошибка при получении курса из Google: {e}")
            return "Не удалось получить информацию о курсе валют"

    def standardize_text(self, text):
        city_replacements = {
            "афинах": "афины",
            "амстердаме": "амстердам",
            "астане": "астана",
            "баку": "баку",
            "бангкоке": "бангкок",
            "берлине": "берлин",  # Столица колбасок и пива
            "брюсселе": "брюссель",  # Штаб-квартира евробюрократии
            "будапеште": "будапешт",
            "варшаве": "варшава",  # Феникс Европы
            "вашингтоне": "вашингтон",  # Где живёт дядя Сэм
            "вене": "вена",
            "гривны": "гривна",  # Деньги, деньги, дребеденьги...
            "днепре": "днепр",  # Город, который сменил фамилию
            "днепропетровске": "днепропетровск",  # Старая фамилия Днепра
            "доллара": "доллар",  # Зелёный властелин мира
            "дублине": "дублин",
            "ереване": "ереван",
            "киеве": "киев",
            "копенгагене": "копенгаген",  # Где русалочка грустит
            "лиссабоне": "лиссабон",
            "лондоне": "лондон",  # Где дождь - национальный спорт
            "мадриде": "мадрид",
            "минске": "минск",  # Город драников
            "москве": "москва",
            "осло": "осло",
            "оттаве": "оттава",  # Канадская скромница
            "париже": "париж",
            "пекине": "пекин",
            "пражке": "прага",
            "риме": "рим",  # Все дороги ведут сюда
            "сеуле": "сеул",
            "сиднее": "сидней",  # Где кенгуру переходят дорогу
            "стокгольме": "стокгольм",
            "тбилиси": "тбилиси",
            "токио": "токио",
            "хельсинки": "хельсинки",
            "черт": "чёрт",
            "шутку": "шутка",
            "вперёд": "вперед"
        }

        number_replacements = {
            "восемнадцать": "18",
            "восемь": "8",
            "два": "2",
            "двадцать": "20",
            "двенадцать": "12",
            "девятнадцать": "19",
            "девять": "9",
            "десять": "10",
            "ноль": "0",
            "один": "1",
            "одиннадцать": "11",
            "пятнадцать": "15",
            "пятьдесят": "50",
            "пять": "5",
            "семнадцать": "17",
            "семь": "7",
            "сорок": "40",
            "три": "3",
            "тридцать": "30",
            "тринадцать": "13",
            "четыре": "4",
            "четырнадцать": "14",
            "шестнадцать": "16",
            "шесть": "6",
        }

        # Замена чисел
        for word, number in number_replacements.items():
            text = re.sub(rf"\b{word}\b", number, text, flags=re.IGNORECASE)

        # Обработка времени
        time_patterns = [
            (r'(\d+)\s*час[ао]?в?\s*(дня|вечера)(?:\s+(\d+)\s*минут)?',
             lambda m: f"{int(m.group(1))+12}:{m.group(3) if m.group(3) else '00'}"),
            (r'(\d+)\s*час[ао]?в?\s*утра(?:\s+(\d+)\s*минут)?',
             lambda m: f"{int(m.group(1)):02d}:{m.group(2) if m.group(2) else '00'}"),
            (r'(\d+)\s*час[ао]?в?(?:\s+(\d+)\s*минут)?',
             lambda m: f"{int(m.group(1)):02d}:{m.group(2) if m.group(2) else '00'}")
        ]

        for pattern, replacement in time_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Замена городов
        pattern = re.compile("|".join(map(re.escape, city_replacements.keys())))
        text = pattern.sub(lambda match: city_replacements[match.group(0)], text)

        return text 

    def clean_wiki_query(self, text: str, ai_name: str) -> str:
        query = text.replace("что такое", "")
        query = query.replace(ai_name.lower(), "")
        query = query.replace("википедия", "")
        return query.strip()

    def search_for_definition(self, query: str, language: str = "ru", ai_name: str = "") -> str:
        try:
            clean_query = self.clean_wiki_query(query, ai_name)
            wiki = wikipediaapi.Wikipedia(language)
            page = wiki.page(clean_query)
            
            if page.exists():
                # Берём первый абзац и очищаем от лишних пробелов
                summary = page.summary.split('\n')[0].strip()
                logging.info(f"Найдено определение для: {clean_query}")
                return summary
            else:
                logging.warning(f"Страница не найдена для запроса: {clean_query}")
                return f"Ой-ой! Я перерыл всю Википедию вдоль и поперёк, но '{clean_query}' как сквозь землю провалилось! Может, оно играет в прятки?"
        except Exception as e:
            logging.error(f"Ошибка при поиске в Википедии: {e}")
            return "Упс! Кажется, Википедия ушла на обед. Или на чай с печеньками. В любом случае, сейчас она не отвечает на мои отчаянные попытки достучаться!"