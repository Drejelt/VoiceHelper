import requests
import os
import json
import logging
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), 'api_keys.env')
load_dotenv(dotenv_path)

CONFIG_PATH = "json/model_config.json"

class WeatherModule:
    def __init__(self, api_key, base_url="https://api.openweathermap.org/data/2.5/weather"):
        self.api_key = api_key
        self.base_url = base_url

    def get_weather(self, city_name, units="metric", lang="ru"):
        try:
            params = {
                "q": city_name,
                "appid": self.api_key,
                "units": units,
                "lang": lang
            }
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                "temperature": data["main"]["temp"],
                "weather": data["weather"][0]["description"],
                "wind_speed": data["wind"]["speed"],
                "city": data["name"]
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при получении погоды для города {city_name}: {e}")
            return None

def get_default_city():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("DEFAULT_CITY", "Днепр")
    except Exception as e:
        logging.error(f"Ошибка при чтении конфигурации: {e}")
        return "Днепр"

def call_weather_api(city_name=None):
    api_key = os.getenv('WEATHER_API')
    if not api_key:
        return "Отсутствует ключ API для получения погоды"

    if not city_name:
        city_name = get_default_city()
        logging.info(f"Используется город по умолчанию: {city_name}")

    weather_module = WeatherModule(api_key)
    weather = weather_module.get_weather(city_name)
    
    if weather:
        return (
            f"температура {weather['temperature']:.1f}°C, "
            f"{weather['weather']}, "
            f"скорость ветра {weather['wind_speed']} м/с"
        )
    else:
        return f"Не удалось получить данные о погоде для города {city_name}"
