import requests
from bs4 import BeautifulSoup

def get_money_info(money_name):
    try:
        # Формируем URL для поиска курса валюты
        url = f"https://www.google.com/search?q=курс+{money_name.lower()}"

        # Словарь с классами для поиска элементов на странице
        class_dict = {
            "title": "vLqKYe",  # Класс названия валюты
            "count": "DFlfde SwHCTb",  # Класс для цены
            "day": "k0Rg6d hqAUc",  # День, время
        }

        # Заголовки для подражания запросу от браузера
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }

        # Отправляем GET-запрос
        r = requests.get(url, headers=headers)
        r.raise_for_status()  # Генерирует исключение, если ответ не 200

        # Парсим HTML-страницу
        html = BeautifulSoup(r.text, 'html.parser')

        # Извлекаем информацию из элементов страницы
        title_money = html.find(class_=class_dict["title"]).get_text(strip=True)
        count_money = html.find(class_=class_dict["count"]).get_text(strip=True)
        refresh_day = html.find(class_=class_dict["day"]).get_text(strip=True)

        return f"Курс валюты {title_money}: 1 {title_money} = {count_money}."

    except requests.exceptions.RequestException as e:
        return f"Ошибка при подключении: {e}"
    except AttributeError:
        return "Не удалось найти информацию о валюте. Возможно, неверное название валюты."

currency_list = ["доллар", "евро", "рубль", "гривна", "фунт", "йена", "франк", "песо", "крона", "юань", "рэал"]