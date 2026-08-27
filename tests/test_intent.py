import unittest
from datetime import datetime
from types import SimpleNamespace

from functional_modules.intent import (
    SOURCE_DETERMINISTIC,
    SOURCE_LLM,
    TOOL_NAMES,
    execute,
    intent_from_command,
    match_command,
    sanitize_intent,
)


class MatchCommandTests(unittest.TestCase):
    def test_keywords_still_win_for_common_phrases(self) -> None:
        self.assertEqual(match_command("шут который час время"), "время")
        self.assertEqual(match_command("шут какая погода"), "погода")
        self.assertEqual(match_command("шут открой ютуб"), "ютуб")
        self.assertEqual(match_command("шут закрой окно"), "закрой_окно")
        self.assertIsNone(match_command("ну и ладно"))

    def test_number_game_digits_only_when_active(self) -> None:
        self.assertIsNone(match_command("это 42"))
        self.assertEqual(match_command("это 42", number_game_active=True), "игра_число")


class IntentMappingTests(unittest.TestCase):
    def test_weather_uses_named_city_or_default(self) -> None:
        named = intent_from_command("погода", "погода", cities=["киев"], config={"DEFAULT_CITY": "одесса"})
        assert named is not None
        self.assertEqual(named.tool, "get_weather")
        self.assertEqual(named.arguments["city"], "киев")
        default = intent_from_command("погода", "погода", config={"DEFAULT_CITY": "одесса"})
        assert default is not None
        self.assertEqual(default.arguments["city"], "одесса")

    def test_unknown_llm_tool_is_dropped(self) -> None:
        self.assertIsNone(sanitize_intent("rm", {"path": "/"}, source=SOURCE_LLM, utterance="x"))

    def test_extra_args_are_stripped(self) -> None:
        intent = sanitize_intent(
            "get_weather",
            {"city": "киев", "shell": "id"},
            source=SOURCE_LLM,
            utterance="погода",
        )
        assert intent is not None
        self.assertEqual(intent.arguments, {"city": "киев"})

    def test_closed_tool_set(self) -> None:
        self.assertIn("unknown", TOOL_NAMES)
        self.assertNotIn("run_shell", TOOL_NAMES)


class ExecuteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[tuple] = []

        def track(name):
            def inner(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return f"ok:{name}"

            return inner

        games = SimpleNamespace(number_to_guess=None, play_number_game=track("number"), play_rock_paper_scissors=track("rps"))
        self.runtime = SimpleNamespace(
            config={"AI_NAME": "шут", "DEFAULT_CITY": "киев"},
            info=SimpleNamespace(
                get_weather=track("weather"),
                get_money_info=track("money"),
                search_for_definition=track("wiki"),
            ),
            scheduler=SimpleNamespace(
                get_current_time=track("time"),
                parse_time_from_text=lambda *a, **k: "07:30",
                set_alarm=track("alarm"),
                write_note=track("note"),
                read_notes=track("read_notes"),
            ),
            reminder=SimpleNamespace(add_reminder=track("reminder"), get_active_reminders=track("list_rem")),
            entertainment=SimpleNamespace(
                games=games,
                programmer_joke=track("joke"),
                generate_fairytale=track("tale"),
                toss_coin=track("coin"),
            ),
            media=SimpleNamespace(
                execute_action=track("media"),
                open_enum_url=track("open"),
                extract_video_query=lambda text, _n: "lofi",
                search_youtube=track("yt"),
                tab_close=track("tab"),
                window_close=track("window"),
            ),
            system=SimpleNamespace(
                take_screenshot=track("shot"),
                shutdown=track("off"),
                restart=track("reboot"),
                logout=track("logout"),
            ),
            social=SimpleNamespace(get_greeting=track("hi"), get_goodbye=track("bye"), get_thanks=track("ty"), get_good_night=track("night")),
        )

    def test_weather_and_unknown(self) -> None:
        weather = execute(
            sanitize_intent("get_weather", {"city": "львов"}, source=SOURCE_DETERMINISTIC, utterance="погода"),
            self.runtime,
        )
        self.assertEqual(weather, "ok:weather")
        self.assertEqual(self.calls[0][1][0], "львов")
        self.assertEqual(
            execute(sanitize_intent("unknown", {}, source=SOURCE_LLM, utterance="asdf"), self.runtime),
            "Не понял команду. Попробуйте иначе.",
        )

    def test_reminder_uses_parsed_time(self) -> None:
        intent = sanitize_intent(
            "add_reminder",
            {"text": "шут напомни чай 07:30", "time": "07:30"},
            source=SOURCE_DETERMINISTIC,
            utterance="шут напомни чай 07:30",
        )
        execute(intent, self.runtime)
        name, args, _ = self.calls[0]
        self.assertEqual(name, "reminder")
        self.assertEqual(args[0], "чай")
        self.assertIsInstance(args[1], datetime)
        self.assertEqual(args[1].hour, 7)
