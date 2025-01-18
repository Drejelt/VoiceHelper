import requests
from bs4 import BeautifulSoup


def get_money_info(money_name="гривна"):
    try:
        api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(api_url)
        response.raise_for_status()
        rates = response.json()["rates"]

        # Словарь соответствия названий валют их кодам
        currency_codes = {
            "доллар": "USD",
            "евро": "EUR",
            "рубль": "RUB",
            "гривна": "UAH",
            "фунт": "GBP",
            "йена": "JPY",
            "франк": "CHF",
            "песо": "MXN",
            "крона": "SEK",
            "юань": "CNY",
            "рэал": "BRL"
        }

        if money_name.lower() in currency_codes:
            code = currency_codes[money_name.lower()]
            if code in rates:
                rate = rates[code]
                if code == "UAH":
                    return f"Курс валюты {money_name}: 1 USD = {rate} UAH"
                return f"Курс валюты {money_name}: 1 USD = {rate} {code}"

        # Если API не сработал, используем парсинг Google как запасной вариант
        url = f"https://www.google.com/search?q=курс+{money_name.lower()}"

        class_dict = {
            "title": "vLqKYe",  # Класс названия валюты
            "count": "DFlfde SwHCTb",  # Класс для цены
            "day": "k0Rg6d hqAUc",  # День, время
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }

        r = requests.get(url, headers=headers)
        r.raise_for_status()

        html = BeautifulSoup(r.text, 'html.parser')

        title_money = html.find(class_=class_dict["title"]).get_text(strip=True)
        count_money = html.find(class_=class_dict["count"]).get_text(strip=True)
        refresh_day = html.find(class_=class_dict["day"]).get_text(strip=True)

        return f"Курс валюты {title_money}: 1 USD = {count_money}"

    except requests.exceptions.RequestException as e:
        return f"Ошибка при подключении: {e}"
    except AttributeError:
        return "Не удалось найти информацию о валюте. Возможно, неверное название валюты."


currency_list = ["доллар", "евро", "рубль", "гривна", "фунт", "йена", "франк", "песо", "крона", "юань", "рэал"]