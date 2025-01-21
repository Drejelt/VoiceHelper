import random
import logging
from datetime import datetime

class SocialInteractions:
    def __init__(self):
        self.greetings = {
            "morning": [
                "Доброе утро! Как спалось?",
                "С добрым утром! Надеюсь, вы хорошо выспались!",
                "Утречка! Кофе уже готов?",
                "Доброе утро! Готовы покорять этот день?"
            ],
            "afternoon": [
                "Добрый день! Как ваше настроение?",
                "Здравствуйте! Надеюсь, день проходит отлично!",
                "Приветствую! Чем могу помочь?",
                "Добрый день! Рад вас слышать!"
            ],
            "evening": [
                "Добрый вечер! Как прошёл день?",
                "Вечер добрый! Надеюсь, день был продуктивным!",
                "Здравствуйте! Готовы отдохнуть?",
                "Добрый вечер! Что нового?"
            ]
        }
        
        self.goodbyes = [
            "До встречи! Буду ждать нашего следующего разговора!",
            "Пока-пока! Хорошего дня!",
            "До свидания! Обращайтесь, если что-нибудь понадобится!",
            "Пока! Рад был помочь!"
        ]
        
        self.good_night = [
            "Спокойной ночи! Пусть приснится что-нибудь хорошее!",
            "Сладких снов! До завтра!",
            "Доброй ночи! Набирайтесь сил для нового дня!",
            "Спокойной ночи! Пусть кроватка будет мягкой, а сны - сладкими!"
        ]
        
        self.thanks = [
            "Всегда пожалуйста! Рад помочь!",
            "Не за что! Обращайтесь ещё!",
            "Пожалуйста! Для меня это только в радость!",
            "На здоровье! Люблю быть полезным!"
        ]

    def get_greeting(self) -> str:
        """Возвращает приветствие в зависимости от времени суток"""
        hour = datetime.now().hour
        
        if 5 <= hour < 12:
            return random.choice(self.greetings["morning"])
        elif 12 <= hour < 18:
            return random.choice(self.greetings["afternoon"])
        else:
            return random.choice(self.greetings["evening"])

    def get_goodbye(self) -> str:
        """Возвращает случайное прощание"""
        return random.choice(self.goodbyes)

    def get_good_night(self) -> str:
        """Возвращает пожелание спокойной ночи"""
        return random.choice(self.good_night)

    def get_thanks(self) -> str:
        """Возвращает ответ на благодарность"""
        return random.choice(self.thanks) 