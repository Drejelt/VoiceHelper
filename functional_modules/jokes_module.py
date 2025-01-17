import pyjokes, requests
from googletrans import Translator

URL = "https://v2.jokeapi.dev/joke/Any"


def programmer_joke():
    try:
        response = requests.get(URL)
        if response.status_code == 200:
            joke_data = response.json()
            if joke_data['type'] == 'single':
                joke = joke_data['joke']
            else:
                joke = f"{joke_data['setup']} {joke_data['delivery']}"

            translator = Translator()
            translated_joke = translator.translate(joke, dest='ru')
            return translated_joke.text
    except requests.RequestException:
        try:
            joke = pyjokes.get_joke()
            translator = Translator()
            translated_joke = translator.translate(joke, dest='ru')
            return translated_joke.text
        except Exception:
            return joke
