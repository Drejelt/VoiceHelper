import requests
from bs4 import BeautifulSoup


def get_money_info(money_name="гривна"):
    try:
        api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(api_url)
        response.raise_for_status()
        rates = response.json()["rates"]

        # Словарь для перевода с человеческого на валютный
        currency_codes = {
            "гривна": "UAH",
            "доллар": "USD",
            "евро": "EUR",
            "йена": "JPY",
            "крона": "SEK",
            "песо": "MXN",
            "рубль": "RUB",
            "рэал": "BRL",
            "фунт": "GBP",
            "франк": "CHF",
            "юань": "CNY"
        }

        # Проверяем, знаем ли мы такие валюты
        if money_name.lower() in currency_codes:
            code = currency_codes[money_name.lower()]
            if code in rates:
                rate = rates[code]
                if code == "UAH":
                    return f"Курс валюты {money_name}: 1 USD = {rate} UAH"
                return f"Курс валюты {money_name}: 1 USD = {rate} {code}"

        # Если API отдыхает, идём гуглить (как все нормальные люди)
        url = f"https://www.google.com/search?q=курс+{money_name.lower()}"

        class_dict = {
            "title": "vLqKYe",  # Тут прячется имя валюты
            "count": "DFlfde SwHCTb",  # А тут её стоимость
            "day": "k0Rg6d hqAUc",  # Когда последний раз проверяли
        }

        # Притворяемся нормальным браузером, а то нас раскусят
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (HTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        }

        r = requests.get(url, headers=headers)
        r.raise_for_status()

        html = BeautifulSoup(r.text, 'html.parser')

        title_money = html.find(class_=class_dict["title"]).get_text(strip=True)
        count_money = html.find(class_=class_dict["count"]).get_text(strip=True)
        refresh_day = html.find(class_=class_dict["day"]).get_text(strip=True)

        return f"Курс валюты {title_money}: 1 USD = {count_money}"

    except requests.exceptions.RequestException as e:
        return f"Ой-ой! Кажется, интернет решил поиграть в прятки! Не могу достучаться до сервера: {e}"
    except AttributeError:
        return "Упс! Похоже, эта валюта настолько экзотическая, что даже Google о ней не слышал! Может, попробуете что-то более земное?"


# Список валют, которые мы знаем (остальные для нас - тёмный лес)
currency_list = [
    "гривна",
    "доллар",
    "евро", 
    "йена",
    "крона",
    "песо",
    "рубль",
    "рэал",
    "фунт",
    "франк",
    "юань"
]