import logging
import webbrowser
import wikipediaapi
import enum
import time
import pyautogui
import requests
import re
from bs4 import BeautifulSoup

class Urls(enum.Enum):
    LOFI_HIP_HOP = 'https://www.youtube.com/watch?v=jfKfPfyJRdk&list=PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L&autoplay=1'
    RANDOM_ANIME = 'https://www.anilibria.tv/public/random.php'
    YOUTUBE = 'https://www.youtube.com/'
    BBC_NEWS = 'https://www.bbc.com/'
    CHIPI_CHIPI = 'https://www.youtube.com/watch?v=0tOXxuLcaog&autoplay=1'
    TRICKY_MUSIC = 'https://www.youtube.com/watch?v=vmaQFkWv8Gc&autoplay=1'
    CONTROL_PANEL = 'http://127.0.0.1:8000/'

def extract_video_query(text: str, ai_name: str) -> str:
    cleaned_text = re.sub(
        rf"\b({ai_name}|найди|видео|поищи|покажи)\b",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()
    
    logging.info(f"Извлечен поисковый запрос для видео: {cleaned_text}")
    return cleaned_text

def search_youtube(query: str) -> str:
    if not query:
        logging.warning("Пустой поисковый запрос для YouTube")
        return "Не указан поисковый запрос"
        
    try:
        search_query = query.replace(' ', '+')
        youtube_search_url = f"https://www.youtube.com/results?search_query={search_query}"
        open_url(youtube_search_url)
        response = f"Ищу видео по запросу: {query}"
        logging.info(response)
        return response
    except Exception as e:
        error_msg = f"Ошибка при поиске видео: {e}"
        logging.error(error_msg)
        return error_msg

def open_url(url):
    webbrowser.open_new_tab(url)
    if 'youtube.com/watch?v=' in url:
        time.sleep(8)
        pyautogui.press('space')

def open_enum_url(url_enum: Urls):
    open_url(url_enum.value)

def search_for_definition(query: str, language: str = "ru") -> str:
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
        return f"Произошла ошибка при выполнении поиска: {str(e)}"

def search_google(query: str) -> tuple[str, str]:
    try:
        google_search_url = f"https://google.com/search?q={query.replace(' ', '+')}"
        headers = {'User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'}

        search_response = requests.get(google_search_url, headers=headers)
        soup = BeautifulSoup(search_response.text, 'html.parser')
        first_link = soup.find('div', class_='yuRUbf')
        
        if first_link and first_link.find('a'):
            url = first_link.find('a')['href']
            return url, f"Открываю первый результат по запросу '{query}'"
        else:
            return google_search_url, f"Показываю результаты поиска для '{query}'"
            
    except Exception as e:
        logging.error(f"Ошибка при поиске в Google: {e}")
        return google_search_url, f"Показываю результаты поиска для '{query}'"

def search_and_open(query: str) -> str:
    url, message = search_google(query)
    open_url(url)
    return message


