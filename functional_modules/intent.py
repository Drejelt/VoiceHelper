"""Closed tools and deterministic intent.

The voice loop never lets the model speak for the assistant. Keywords still
win. The LLM, when used, may only pick a name from TOOLS and a small argument
object. Execution stays in this module.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

SOURCE_DETERMINISTIC = "deterministic"
SOURCE_LLM = "llm"
SOURCE_FALLBACK = "fallback"


@dataclass(frozen=True)
class Intent:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    source: str = SOURCE_DETERMINISTIC
    utterance: str = ""


@dataclass
class Runtime:
    config: dict
    info: Any
    scheduler: Any
    reminder: Any
    entertainment: Any
    media: Any
    system: Any
    social: Any


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_time",
        "description": "Текущее локальное время.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_weather",
        "description": "Погода. Если город не назван — город по умолчанию.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    },
    {
        "name": "get_exchange_rate",
        "description": "Курс валюты к валюте по умолчанию.",
        "parameters": {
            "type": "object",
            "properties": {"currency": {"type": "string"}},
            "required": ["currency"],
        },
    },
    {
        "name": "search_wikipedia",
        "description": "Краткое определение из Википедии.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "set_alarm",
        "description": "Поставить будильник. time в формате HH:MM.",
        "parameters": {
            "type": "object",
            "properties": {"time": {"type": "string"}},
        },
    },
    {
        "name": "list_alarms",
        "description": "Список активных будильников.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "clear_alarms",
        "description": "Сбросить все будильники.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "add_reminder",
        "description": "Напоминание. time в HH:MM, text — о чём напомнить.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "time": {"type": "string"},
            },
        },
    },
    {
        "name": "list_reminders",
        "description": "Список активных напоминаний.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "media",
        "description": "Управление воспроизведением в активном окне (горячие клавиши YouTube).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "play_pause",
                        "volume_up",
                        "volume_down",
                        "shuffle",
                        "loop",
                        "fullscreen",
                        "subtitles",
                        "mini_player",
                        "speed_up",
                        "speed_down",
                        "seek_forward",
                        "seek_backward",
                        "jump_to_start",
                    ],
                }
            },
            "required": ["action"],
        },
    },
    {
        "name": "open_site",
        "description": "Открыть известный сайт или панель ассистента.",
        "parameters": {
            "type": "object",
            "properties": {
                "site": {
                    "type": "string",
                    "enum": [
                        "youtube",
                        "news",
                        "music",
                        "anime",
                        "chipi",
                        "tricky",
                        "control_panel",
                    ],
                }
            },
            "required": ["site"],
        },
    },
    {
        "name": "search_video",
        "description": "Поиск видео на YouTube.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "close",
        "description": "Закрыть вкладку или окно.",
        "parameters": {
            "type": "object",
            "properties": {"target": {"type": "string", "enum": ["tab", "window"]}},
            "required": ["target"],
        },
    },
    {
        "name": "screenshot",
        "description": "Снимок экрана.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "power",
        "description": "Питание. Реально выполняется только при ALLOW_POWER_COMMANDS=1.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["shutdown", "reboot", "logout"]}
            },
            "required": ["action"],
        },
    },
    {
        "name": "talk",
        "description": "Короткая реплика: шутка, сказка, монетка, приветствие.",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "joke",
                        "fairytale",
                        "coin",
                        "greet",
                        "goodbye",
                        "thanks",
                        "good_night",
                    ]
                },
                "theme": {"type": "string"},
            },
            "required": ["kind"],
        },
    },
    {
        "name": "play_game",
        "description": "Игра: угадай число или камень-ножницы-бумага.",
        "parameters": {
            "type": "object",
            "properties": {
                "game": {"type": "string", "enum": ["number", "rps"]},
                "value": {"type": "string"},
            },
            "required": ["game"],
        },
    },
    {
        "name": "write_note",
        "description": "Записать заметку.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "read_notes",
        "description": "Прочитать заметки.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "unknown",
        "description": "Фраза не является командой ассистента.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
        },
    },
]

TOOL_NAMES = frozenset(item["name"] for item in TOOL_SCHEMAS)
TOOL_ARG_KEYS = {
    item["name"]: set((item.get("parameters") or {}).get("properties") or {})
    for item in TOOL_SCHEMAS
}

_MEDIA = {
    "пауза": "play_pause",
    "продолжить": "play_pause",
    "громче": "volume_up",
    "тише": "volume_down",
    "перемешать": "shuffle",
    "повтор": "loop",
    "полный_экран": "fullscreen",
    "субтитры": "subtitles",
    "мини_плеер": "mini_player",
    "ускорить": "speed_up",
    "замедлить": "speed_down",
    "вперед": "seek_forward",
    "назад": "seek_backward",
    "в_начало": "jump_to_start",
}

_SITES = {
    "ютуб": "youtube",
    "новости": "news",
    "музыку": "music",
    "аниме": "anime",
    "чипи": "chipi",
    "хитрая_музыка": "tricky",
    "панель_управления": "control_panel",
}

_MUSIC_ENUM = {
    "play_pause": "PLAY_PAUSE",
    "volume_up": "VOLUME_UP",
    "volume_down": "VOLUME_DOWN",
    "shuffle": "SHUFFLE",
    "loop": "LOOP",
    "fullscreen": "FULLSCREEN",
    "subtitles": "SUBTITLES",
    "mini_player": "MINI_PLAYER",
    "speed_up": "SPEED_UP",
    "speed_down": "SPEED_DOWN",
    "seek_forward": "SEEK_FORWARD",
    "seek_backward": "SEEK_BACKWARD",
    "jump_to_start": "JUMP_TO_START",
}

_URL_ENUM = {
    "youtube": "YOUTUBE",
    "news": "BBC_NEWS",
    "music": "LOFI_HIP_HOP",
    "anime": "RANDOM_ANIME",
    "chipi": "CHIPI_CHIPI",
    "tricky": "TRICKY_MUSIC",
    "control_panel": "CONTROL_PANEL",
}


def sanitize_intent(
    tool: str,
    arguments: dict[str, Any] | None,
    *,
    source: str,
    utterance: str,
) -> Intent | None:
    if tool not in TOOL_NAMES:
        logging.warning("LLM named unknown tool %r — dropped", tool)
        return None
    raw = arguments or {}
    allowed = TOOL_ARG_KEYS[tool]
    clean = {
        key: value
        for key, value in raw.items()
        if key in allowed and value not in (None, "")
    }
    return Intent(tool=tool, arguments=clean, source=source, utterance=utterance)


def match_command(text: str, *, number_game_active: bool = False) -> str | None:
    """Keyword matcher. Order is the original CommandProcessor order."""
    t = text.lower()
    if number_game_active and any(ch.isdigit() for ch in t):
        return "игра_число"

    commands: dict[str, Callable[[str], bool]] = {
        "найди_видео": lambda s: "видео" in s and any(w in s for w in ("найди", "поищи", "покажи")),
        "открой_видео": lambda s: "открой видео" in s,
        "время": lambda s: "время" in s or "времени" in s,
        "погода": lambda s: "погода" in s,
        "новости": lambda s: "новости" in s,
        "курс": lambda s: any(kw in s for kw in ("курс", "доллар", "евро", "гривна")),
        "википедия": lambda s: "википедия" in s or "что такое" in s,
        "шутка": lambda s: "шутка" in s or "анекдот" in s,
        "сказка": lambda s: "сказку" in s or "историю" in s,
        "панель_управления": lambda s: "управления" in s and any(kw in s for kw in ("открой", "включи")),
        "закрой_вкладку": lambda s: "закрой" in s and "вкладку" in s,
        "закрой_окно": lambda s: "закрой" in s and "окно" in s,
        "пора_спать": lambda s: "отключись" in s or "выключись" in s,
        "будильник": lambda s: "будильник" in s and any(kw in s for kw in ("будильник", "разбуди", "поставь")),
        "ютуб": lambda s: "ютуб" in s and any(kw in s for kw in ("открой", "включи")),
        "музыку": lambda s: "включи" in s and "музыку" in s,
        "аниме": lambda s: "включи" in s and any(kw in s for kw in ("аниме", "анимешку")),
        "чипи": lambda s: "деградировать" in s,
        "хитрая_музыка": lambda s: ("подлая" in s or "хитрая" in s) and "музыка" in s,
        "пауза": lambda s: any(kw in s for kw in ("пауза", "паузу", "стоп")),
        "продолжить": lambda s: any(kw in s for kw in ("продолжить", "возобнови видео")),
        "громче": lambda s: any(kw in s for kw in ("сделай громче", "увеличь громкость")),
        "тише": lambda s: any(kw in s for kw in ("сделай тише", "уменьши громкость")),
        "перемешать": lambda s: any(kw in s for kw in ("перемешай", "случайный порядок")),
        "повтор": lambda s: any(kw in s for kw in ("повторять", "зациклить")),
        "полный_экран": lambda s: any(kw in s for kw in ("полный экран", "развернуть")),
        "субтитры": lambda s: any(kw in s for kw in ("субтитры", "титры")),
        "качество": lambda s: any(kw in s for kw in ("качество", "разрешение")),
        "мини_плеер": lambda s: any(kw in s for kw in ("мини-плеер", "маленькое окно")),
        "ускорить": lambda s: any(kw in s for kw in ("ускорь", "быстрее")),
        "замедлить": lambda s: any(kw in s for kw in ("замедли", "медленнее")),
        "вперед": lambda s: any(kw in s for kw in ("вперед", "перемотай вперед")),
        "назад": lambda s: any(kw in s for kw in ("назад", "перемотай назад")),
        "в_начало": lambda s: any(kw in s for kw in ("в начало", "сначала", "в начала")),
        "монетка": lambda s: any(kw in s for kw in ("монетка", "бросить монетку", "брось монетку")),
        "привет": lambda s: any(w in s for w in ("привет", "здравствуй", "доброе утро", "добрый день", "добрый вечер")),
        "пока": lambda s: any(w in s for w in ("пока", "до свидания", "прощай")),
        "спокойной_ночи": lambda s: any(w in s for w in ("спокойной ночи", "доброй ночи")),
        "спасибо": lambda s: any(w in s for w in ("спасибо", "благодарю")),
        "скриншот": lambda s: "скриншот" in s or "снимок экрана" in s,
        "заметка": lambda s: "заметку" in s or "запиши" in s,
        "прочитай_заметки": lambda s: "прочитай" in s and "заметки" in s,
        "выключи_компьютер": lambda s: "выключи компьютер" in s,
        "перезагрузи": lambda s: "перезагрузи" in s or "перезагрузка" in s,
        "выйти": lambda s: "выйти из системы" in s or "разлогиниться" in s,
        "угадай_число": lambda s: "угадай число" in s or "поиграем в числа" in s,
        "камень_ножницы_бумага": lambda s: "сыграем" in s and any(w in s for w in ("камень", "ножницы", "бумага")),
        "напомни": lambda s: "напомни" in s,
        "покажи_напоминания": lambda s: "покажи" in s and "напоминания" in s,
        "покажи_будильники": lambda s: "покажи" in s and "будильник" in s,
        "очисти_будильники": lambda s: "очисти" in s and "будильник" in s,
    }
    for name, pred in commands.items():
        if pred(t):
            return name
    return None


def intent_from_command(
    command: str,
    text: str,
    *,
    cities: list[str] | None = None,
    money: str | None = None,
    time_alarm: str | None = None,
    config: dict | None = None,
    source: str = SOURCE_DETERMINISTIC,
) -> Intent | None:
    cities = cities or []
    config = config or {}
    default_city = config.get("DEFAULT_CITY") or ""

    if command in _MEDIA:
        return sanitize_intent("media", {"action": _MEDIA[command]}, source=source, utterance=text)
    if command in _SITES:
        return sanitize_intent("open_site", {"site": _SITES[command]}, source=source, utterance=text)

    mapping: dict[str, tuple[str, dict[str, Any]]] = {
        "время": ("get_time", {}),
        "погода": ("get_weather", {"city": cities[0] if cities else default_city}),
        "курс": ("get_exchange_rate", {"currency": money or "доллар"}),
        "википедия": ("search_wikipedia", {"query": text}),
        "будильник": ("set_alarm", {"time": time_alarm or ""}),
        "покажи_будильники": ("list_alarms", {}),
        "очисти_будильники": ("clear_alarms", {}),
        "напомни": ("add_reminder", {"text": text, "time": time_alarm or ""}),
        "покажи_напоминания": ("list_reminders", {}),
        "найди_видео": ("search_video", {"query": text}),
        "открой_видео": ("search_video", {"query": text}),
        "закрой_вкладку": ("close", {"target": "tab"}),
        "закрой_окно": ("close", {"target": "window"}),
        "скриншот": ("screenshot", {}),
        "пора_спать": ("power", {"action": "shutdown"}),
        "выключи_компьютер": ("power", {"action": "shutdown"}),
        "перезагрузи": ("power", {"action": "reboot"}),
        "выйти": ("power", {"action": "logout"}),
        "шутка": ("talk", {"kind": "joke"}),
        "сказка": ("talk", {"kind": "fairytale"}),
        "монетка": ("talk", {"kind": "coin"}),
        "привет": ("talk", {"kind": "greet"}),
        "пока": ("talk", {"kind": "goodbye"}),
        "спасибо": ("talk", {"kind": "thanks"}),
        "спокойной_ночи": ("talk", {"kind": "good_night"}),
        "угадай_число": ("play_game", {"game": "number"}),
        "игра_число": ("play_game", {"game": "number", "value": text}),
        "камень_ножницы_бумага": (
            "play_game",
            {
                "game": "rps",
                "value": next((w for w in ("камень", "ножницы", "бумага") if w in text.lower()), ""),
            },
        ),
        "заметка": ("write_note", {"text": text}),
        "прочитай_заметки": ("read_notes", {}),
    }
    if command == "качество":
        return None
    pair = mapping.get(command)
    if not pair:
        return None
    tool, args = pair
    return sanitize_intent(tool, args, source=source, utterance=text)


def _strip_wake(text: str, ai_name: str) -> str:
    return re.sub(rf"\b{re.escape(ai_name)}\b", "", text, flags=re.IGNORECASE).strip()


def _parse_hhmm(raw: str, scheduler: Any, ai_name: str, utterance: str) -> str | None:
    if raw and re.fullmatch(r"\d{1,2}:\d{2}", raw.strip()):
        hours, minutes = map(int, raw.strip().split(":"))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    return scheduler.parse_time_from_text(utterance, ai_name)


def execute(intent: Intent, runtime: Runtime) -> str:
    tool = intent.tool
    args = intent.arguments
    ai_name = str(runtime.config.get("AI_NAME") or "")
    utterance = intent.utterance

    if tool == "unknown":
        return "Не понял команду. Попробуйте иначе."
    if tool == "get_time":
        return runtime.scheduler.get_current_time()
    if tool == "get_weather":
        city = str(args.get("city") or runtime.config.get("DEFAULT_CITY") or "").strip()
        if not city:
            return "Назовите город"
        return runtime.info.get_weather(city)
    if tool == "get_exchange_rate":
        return runtime.info.get_money_info(str(args.get("currency") or "доллар"))
    if tool == "search_wikipedia":
        query = str(args.get("query") or utterance)
        return runtime.info.search_for_definition(query, "ru", ai_name)
    if tool == "set_alarm":
        time_str = _parse_hhmm(str(args.get("time") or ""), runtime.scheduler, ai_name, utterance)
        if not time_str:
            return "Не удалось распознать время для будильника"
        return runtime.scheduler.set_alarm(time_str)
    if tool == "list_alarms":
        return runtime.scheduler.get_active_alarms()
    if tool == "clear_alarms":
        return runtime.scheduler.clear_alarms()
    if tool == "add_reminder":
        time_str = _parse_hhmm(str(args.get("time") or ""), runtime.scheduler, ai_name, utterance)
        if not time_str:
            return "Не удалось распознать время напоминания"
        body = str(args.get("text") or utterance)
        body = _strip_wake(body, ai_name)
        body = re.sub(r"\bнапомни\b", "", body, flags=re.IGNORECASE)
        body = body.replace(time_str, "").strip(" ,.-")
        today = datetime.now()
        hours, minutes = map(int, time_str.split(":"))
        when = datetime(today.year, today.month, today.day, hours, minutes)
        return runtime.reminder.add_reminder(body or "событие", when)
    if tool == "list_reminders":
        return runtime.reminder.get_active_reminders()
    if tool == "media":
        from functional_modules.media_controller import MusicAction

        enum_name = _MUSIC_ENUM.get(str(args.get("action") or ""))
        if not enum_name:
            return "Неизвестное действие плеера"
        action = MusicAction[enum_name]
        spoken = {
            "play_pause": "Переключаю воспроизведение",
            "volume_up": "Делаю громче",
            "volume_down": "Делаю тише",
            "shuffle": "Перемешиваю",
            "loop": "Включаю повтор",
            "fullscreen": "Разворачиваю на весь экран",
            "subtitles": "Переключаю субтитры",
            "mini_player": "Включаю мини-плеер",
            "speed_up": "Ускоряю воспроизведение",
            "speed_down": "Замедляю воспроизведение",
            "seek_forward": "Перематываю вперед",
            "seek_backward": "Перематываю назад",
            "jump_to_start": "Возвращаюсь в начало",
        }
        runtime.media.execute_action(action)
        return spoken.get(str(args.get("action")), "Готово")
    if tool == "open_site":
        from functional_modules.media_controller import Urls

        site = str(args.get("site") or "")
        enum_name = _URL_ENUM.get(site)
        if not enum_name:
            return "Неизвестный сайт"
        runtime.media.open_enum_url(Urls[enum_name])
        labels = {
            "youtube": "Открываю YouTube",
            "news": "Открываю новости",
            "music": "Музыка включена",
            "anime": "Открываю аниме",
            "chipi": "Включаю чипи чипи",
            "tricky": "Хитрая музыка включена",
            "control_panel": "Открываю панель управления",
        }
        return labels[site]
    if tool == "search_video":
        query = str(args.get("query") or "")
        query = runtime.media.extract_video_query(query or utterance, ai_name)
        if not query:
            return "Не удалось понять, какое видео вы ищете"
        return runtime.media.search_youtube(query)
    if tool == "close":
        target = str(args.get("target") or "tab")
        if target == "window":
            runtime.media.window_close()
            return "Закрываю окно"
        runtime.media.tab_close()
        return "Закрываю вкладку"
    if tool == "screenshot":
        return runtime.system.take_screenshot()
    if tool == "power":
        action = str(args.get("action") or "")
        if action == "shutdown":
            return runtime.system.shutdown()
        if action == "reboot":
            return runtime.system.restart()
        if action == "logout":
            return runtime.system.logout()
        return "Неизвестная команда питания"
    if tool == "talk":
        kind = str(args.get("kind") or "")
        if kind == "joke":
            return runtime.entertainment.programmer_joke()
        if kind == "fairytale":
            theme = args.get("theme")
            return runtime.entertainment.generate_fairytale(theme)
        if kind == "coin":
            return runtime.entertainment.toss_coin()
        if kind == "greet":
            return runtime.social.get_greeting()
        if kind == "goodbye":
            return runtime.social.get_goodbye()
        if kind == "thanks":
            return runtime.social.get_thanks()
        if kind == "good_night":
            return runtime.social.get_good_night()
        return "Не понял"
    if tool == "play_game":
        game = str(args.get("game") or "")
        value = str(args.get("value") or "")
        if game == "number":
            return runtime.entertainment.games.play_number_game(value or None)
        if game == "rps":
            choice = value or next((w for w in ("камень", "ножницы", "бумага") if w in utterance.lower()), "")
            if not choice:
                return "Выберите: камень, ножницы или бумага!"
            return runtime.entertainment.games.play_rock_paper_scissors(choice)
        return "Неизвестная игра"
    if tool == "write_note":
        note = _strip_wake(str(args.get("text") or utterance), ai_name)
        note = re.sub(r"\b(запиши|заметку|заметка)\b", "", note, flags=re.IGNORECASE).strip()
        return runtime.scheduler.write_note(note or utterance, include_datetime=True)
    if tool == "read_notes":
        return runtime.scheduler.read_notes()
    logging.error("execute: unhandled tool %s", tool)
    return "Эту команду я ещё не умею"
