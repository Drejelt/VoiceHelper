import pyjokes, httpcore
from googletrans import Translator

def programmer_joke():
    try:
        translator = Translator()
        joke = pyjokes.get_joke()
        translated_joke = translator.translate(joke, dest='ru')
        return (translated_joke.text)
    except httpcore._exceptions.ConnectError:
        return (joke)
