import requests, os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), 'api_keys.env')
load_dotenv(dotenv_path)

class WeatherModule:
    def __init__(self, api_key, base_url="https://api.openweathermap.org/data/2.5/weather"):
        self.api_key = api_key
        self.base_url = base_url

    def get_weather(self, city_name, units="metric", lang="ru"):
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
                "wind_speed": data["wind"]["speed"]
            }

def call_weather_api(city_name):
    api_key = os.getenv('WEATHER_API')
    weather_module = WeatherModule(api_key)
    weather = weather_module.get_weather(city_name)
    if weather:
        return (f"Температура на улице: {weather['temperature']}°C, {weather['weather']}, скорость ветра составляет: {weather['wind_speed']} м/с")
    else:
        return ("Не удалось получить данные о погоде.")
