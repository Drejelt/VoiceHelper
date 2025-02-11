import enum
import logging
import os
import re
import subprocess
import sys
import time
import webbrowser
import pyautogui
import requests
import wikipediaapi
from bs4 import BeautifulSoup


class Urls(enum.Enum):
    LOFI_HIP_HOP = 'https://www.youtube.com/watch?v=jfKfPfyJRdk&list=PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L&autoplay=1'
    RANDOM_ANIME = 'https://www.anilibria.tv/public/random.php'
    YOUTUBE = 'https://www.youtube.com/'
    BBC_NEWS = 'https://www.bbc.com/'
    CHIPI_CHIPI = 'https://www.youtube.com/watch?v=0tOXxuLcaog&autoplay=1'
    TRICKY_MUSIC = 'https://www.youtube.com/watch?v=vmaQFkWv8Gc&autoplay=1'
    CONTROL_PANEL = 'http://localhost:8000/'


class MusicAction(enum.Enum):
    PLAY_PAUSE = 'k'
    VOLUME_UP = 'up'
    VOLUME_DOWN = 'down'
    SHUFFLE = 's'
    LOOP = 'l'
    FULLSCREEN = 'f'
    SUBTITLES = 'c'
    MINI_PLAYER = 'i'
    SPEED_UP = ['shift', '>']
    SPEED_DOWN = ['shift', '<']
    RESET_SPEED = ['shift', 'n']
    SEEK_FORWARD = 'l'
    SEEK_BACKWARD = 'j'
    JUMP_TO_START = '0'


class MediaController:
    def __init__(self):
        self.social_searcher = SocialSearcher()

    def execute_action(self, action: MusicAction):
        try:
            keys = action.value
            if isinstance(keys, str):
                pyautogui.press(keys)
            else:
                for key in keys:
                    pyautogui.press(key)
            return f"Команда {action.name} выполнена"
        except Exception as e:
            logging.error(f"Ошибка при выполнении команды {action.name}: {e}")
            return f"Ой-ой! Мои кнопочки взбунтовались и отказываются выполнять команду {action.name}! Может, им нужен отпуск?"

    def tab_close(self):
        pyautogui.hotkey('ctrl', 'w')

    def window_close(self):
        pyautogui.hotkey('alt', 'f4')

    def open_url(self, url):
        webbrowser.open_new_tab(url)
        if 'youtube.com/watch?v=' in url:
            time.sleep(8)
            pyautogui.press('space')

    def open_enum_url(self, url_enum: Urls):
        self.open_url(url_enum.value)

    def extract_video_query(self, text: str, ai_name: str) -> str:
        cleaned_text = re.sub(
            rf"\b({ai_name}|найди|видео|поищи|покажи)\b",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()
        logging.info(f"Извлечен поисковый запрос для видео: {cleaned_text}")
        return cleaned_text

    def search_youtube(self, query: str) -> str:
        if not query:
            logging.warning("Пустой поисковый запрос")
            return "Хм... Искать пустоту? Я конечно умный, но не настолько философский!"

        try:
            search_query = query.replace(' ', '+')
            youtube_search_url = f"https://www.youtube.com/results?search_query={search_query}"
            self.open_url(youtube_search_url)
            response = f"Ищу видео по запросу: {query}"
            logging.info(response)
            return response
        except Exception as e:
            error_msg = f"Упс! YouTube решил поиграть в прятки! Говорит что-то про: {e}"
            logging.error(error_msg)
            return error_msg

    def search_for_definition(self, query: str, language: str = "ru") -> str:
        wiki = wikipediaapi.Wikipedia(language)
        wiki_page = wiki.page(query)
        try:
            if wiki_page.exists():
                return wiki_page.summary.split("\n")[0]
            else:
                google_search_url = f"https://google.com/search?q={query.replace(' ', '+')}"
                webbrowser.open(google_search_url)
                return "Википедия пожала плечами, открываю Google!"
        except Exception as e:
            return f"Ой-ой! Кажется, все энциклопедии мира одновременно ушли на обед! Ошибка: {str(e)}"

    def search_google(self, query: str) -> tuple[str, str]:
        try:
            google_search_url = f"https://google.com/search?q={query.replace(' ', '+')}"
            headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            search_response = requests.get(google_search_url, headers=headers)
            soup = BeautifulSoup(search_response.text, 'html.parser')
            first_link = soup.find('div', class_='yuRUbf')

            if first_link and first_link.find('a'):
                url = first_link.find('a')['href']
                return url, (f"Открываю первый результа"
                             f"т по запросу '{query}'")
            return google_search_url, f"Показываю результаты поиска для '{query}'"
        except Exception as e:
            logging.error(f"Ошибка при поиске в Google: {e}")
            return google_search_url, f"Google сейчас немного занят - считает до бесконечности! Показываю что смог найти для '{query}'"


class SocialSearcher:
    def search_person(self, name: str) -> str:
        try:
            google_term = " ".join(name.split())
            fb_term = "-".join(name.split())
            
            webbrowser.get().open(f"https://google.com/search?q={google_term} site:facebook.com")
            webbrowser.get().open(f"https://www.facebook.com/public/{fb_term}")
            
            return f"Ищу информацию о {name} в социальных сетях"
        except Exception as e:
            logging.error(f"Ошибка при поиске в соц. сетях: {e}")
            return "Ой! Кажется, социальные сети устроили забастовку. Говорят, им нужно больше лайков!" 