import pyjokes, requests
from googletrans import Translator  # Для перевода шуток (не всегда удачно)

URL = "https://v2.jokeapi.dev/joke/Any"  # Кладезь черного юмора


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
    except requests.RequestException:  # Если интернет решил пошутить
        try:
            # План Б: достаем шутку из локального запасника
            joke = pyjokes.get_joke()
            translator = Translator()
            translated_joke = translator.translate(joke, dest='ru')
            return translated_joke.text
        except Exception:  # Когда всё пошло совсем не по плану
            return joke
