import enum 
import logging  # Логгер - наш верный летописец, записывающий все наши "упс" моменты
import os
import re 
import subprocess  # Для запуска других программ, когда своих сил не хватает
import sys
import time  # Время - штука относительная, особенно когда ждёшь загрузки YouTube
import webbrowser 

import pyautogui  # Автоматизация - когда лень двигать мышкой
import requests 
import wikipediaapi  # Wikipedia - кладезь знаний и случайных фактов в 3 часа ночи
from bs4 import BeautifulSoup


class Urls(enum.Enum):  # Коллекция наших любимых интернет-закладок
    LOFI_HIP_HOP = 'https://www.youtube.com/watch?v=jfKfPfyJRdk&list=PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L&autoplay=1'  # Для тех, кто хочет отдыхать как кот на подоконнике
    RANDOM_ANIME = 'https://www.anilibria.tv/public/random.php'  # Для любителей японских мультиков
    YOUTUBE = 'https://www.youtube.com/'  # Чёрная дыра для свободного времени
    BBC_NEWS = 'https://www.bbc.com/' 
    CHIPI_CHIPI = 'https://www.youtube.com/watch?v=0tOXxuLcaog&autoplay=1'  # Чипи-чипи-чапа-чапа!
    TRICKY_MUSIC = 'https://www.youtube.com/watch?v=vmaQFkWv8Gc&autoplay=1'
    CONTROL_PANEL = 'http://localhost:8000/'  # Центр управления полётами


def extract_video_query(text: str, ai_name: str) -> str:  # Функция-фильтр, убирающая словесный мусор
    cleaned_text = re.sub(
        rf"\b({ai_name}|найди|видео|поищи|покажи)\b",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    logging.info(f"Извлечен поисковый запрос для видео: {cleaned_text}")
    return cleaned_text


def search_youtube(query: str) -> str:  # YouTube-искатель, главный враг продуктивности
    if not query:
        logging.warning("Упс! Кажется, запрос потерялся по дороге в YouTube!")
        return "Ой-ой! Я не могу искать пустоту... Хотя, постойте, разве пустота - это не дзен?"

    try:
        search_query = query.replace(' ', '+')  # Заменяем пробелы на плюсики, как в математике!
        youtube_search_url = f"https://www.youtube.com/results?search_query={search_query}"
        open_url(youtube_search_url)
        response = f"Ищу видео по запросу: {query}"
        logging.info(response)
        return response
    except Exception as e:
        error_msg = f"Ой-ёй! YouTube сегодня капризничает как трёхлетний ребёнок! Вот что он говорит: {e}"
        logging.error(error_msg)
        return error_msg


def open_url(url):
    webbrowser.open_new_tab(url)
    if 'youtube.com/watch?v=' in url:
        time.sleep(8)  # Подождём, пока YouTube соберётся с мыслями
        pyautogui.press('space')


def open_enum_url(url_enum: Urls):  # Функция для ленивых - открыть URL одним щелчком
    open_url(url_enum.value)


def search_for_definition(query: str, language: str = "ru") -> str:  # Википедия - наш карманный профессор
    wiki = wikipediaapi.Wikipedia(language)
    wiki_page = wiki.page(query)
    try:
        if wiki_page.exists():
            first_paragraph = wiki_page.summary.split("\n")[0]
            return f"{first_paragraph}"
        else:
            google_search_url = f"https://google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(google_search_url)
    except Exception as e:
        return f"Ой-ёй! Википедия сегодня не в настроении делиться знаниями! Может, у неё понедельник? Вот что случилось: {str(e)}"


def search_google(query: str) -> tuple[str, str]:
    try:
        google_search_url = f"https://google.com/search?q={query.replace(' ', '+')}"
        headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"}  # Притворяемся обычным браузером

        search_response = requests.get(google_search_url, headers=headers)
        soup = BeautifulSoup(search_response.text, 'html.parser')
        first_link = soup.find('div', class_='yuRUbf')

        if first_link and first_link.find('a'):
            url = first_link.find('a')['href']
            return url, f"Открываю первый результат по запросу '{query}'"
        else:
            return google_search_url, f"Показываю результаты поиска для '{query}'"

    except Exception as e:
        logging.error(f"Ох! Google решил поиграть в прятки! Может, он занят перекусом печеньками? Ошибка: {e}")
        return google_search_url, f"Показываю результаты поиска для '{query}'"


def search_and_open(query: str) -> str:  # Ищем и сразу открываем, два в одном!
    url, message = search_google(query)
    open_url(url)
    return message
