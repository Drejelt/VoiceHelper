import logging, webbrowser, wikipediaapi, enum

# Настройка логирования
logging.getLogger("wikipediaapi").setLevel(logging.WARNING)

class Urls(enum.Enum):
    LOFI_HIP_HOP = 'https://www.youtube.com/watch?v=jfKfPfyJRdk&list=PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L?autoplay=1'
    RANDOM_ANIME = 'https://www.anilibria.tv/public/random.php'
    YOUTUBE = 'https://www.youtube.com/'
    BBC_NEWS = 'https://www.bbc.com/'
    CHIPI_CHIPI = 'https://www.youtube.com/watch?v=0tOXxuLcaog?autoplay=1'
    TRICKY_MUSIC = 'https://www.youtube.com/watch?v=vmaQFkWv8Gc?autoplay=1'
    CONTROL_PANEL = 'http://127.0.0.1:8000/docs'

def open_url(url):
    webbrowser.open_new_tab(url)

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
