import logging, webbrowser, wikipediaapi

# Настройка логирования
logging.getLogger("wikipediaapi").setLevel(logging.WARNING)

def open_url(url):
    webbrowser.open_new_tab(url)

def open_lofi_hip_hop_music():
    open_url('https://www.youtube.com/watch?v=jfKfPfyJRdk&list=PL6NdkXsPL07Il2hEQGcLI4dg_LTg7xA2L')

def open_random_anime():
    open_url('https://www.anilibria.tv/public/random.php')

def open_youtube():
    open_url('https://www.youtube.com/')

def bbc_news_open():
    open_url('https://www.bbc.com/')

def chipi_chipi():
    open_url('https://www.youtube.com/watch?v=0tOXxuLcaog')

def tricky_music():
    open_url('https://www.youtube.com/watch?v=vmaQFkWv8Gc?autoplay=1')

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
