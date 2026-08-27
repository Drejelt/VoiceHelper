import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from functional_modules import llm as llm_mod
from functional_modules.llm import LlmLimits, LlmRouter


def _router(**kwargs) -> LlmRouter:
    clock = {"t": 0.0}

    def now() -> float:
        return clock["t"]

    router = LlmRouter(
        provider=kwargs.get("provider", "openai"),
        model="test-model",
        api_key="secret",
        api_base="https://example.invalid/v1",
        limits=kwargs.get("limits", LlmLimits(timeout_sec=0.2, failure_threshold=3, cooldown_sec=30, max_calls_per_minute=12)),
        http_post=kwargs["http_post"],
        now=now,
    )
    router._clock = clock
    return router


class LlmRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: None)
        patcher = mock.patch.object(llm_mod, "LOG_PATH", self.tmp / "llm.jsonl")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _events(self) -> list[dict]:
        path = self.tmp / "llm.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def test_openai_tool_call_becomes_intent(self) -> None:
        def http_post(url, body, headers, timeout):
            self.assertIn("chat/completions", url)
            self.assertEqual(headers["Authorization"], "Bearer secret")
            self.assertEqual(body["tool_choice"], "required")
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"city": "одесса"}',
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 111, "completion_tokens": 9},
            }

        router = _router(http_post=http_post)
        intent = router.select("шут какая погода в одессе")
        assert intent is not None
        self.assertEqual(intent.tool, "get_weather")
        self.assertEqual(intent.arguments["city"], "одесса")
        self.assertEqual(intent.source, "llm")
        event = self._events()[0]
        self.assertEqual(event["prompt_tokens"], 111)
        self.assertEqual(event["completion_tokens"], 9)
        self.assertIsNone(event["error"])
        self.assertNotIn("secret", json.dumps(event))

    def test_gemini_function_call(self) -> None:
        def http_post(url, body, headers, timeout):
            self.assertIn("generativelanguage.googleapis.com", url)
            self.assertIn("key=secret", url)
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"functionCall": {"name": "get_time", "args": {}}}]
                        }
                    }
                ],
                "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 3},
            }

        router = _router(provider="gemini", http_post=http_post)
        intent = router.select("сколько времени")
        assert intent is not None
        self.assertEqual(intent.tool, "get_time")
        self.assertEqual(self._events()[0]["prompt_tokens"], 40)

    def test_invented_tool_is_fallback(self) -> None:
        def http_post(*_a, **_k):
            return {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"name": "run_shell", "arguments": '{"cmd": "id"}'}}
                            ]
                        }
                    }
                ],
                "usage": {},
            }

        router = _router(http_post=http_post)
        self.assertIsNone(router.select("сделай что-нибудь"))
        event = self._events()[0]
        self.assertEqual(event["source"], "fallback")
        self.assertIn("closed set", event["error"])

    def test_timeout_falls_back_and_opens_circuit(self) -> None:
        def http_post(*_a, **_k):
            raise TimeoutError("slow")

        router = _router(http_post=http_post, limits=LlmLimits(failure_threshold=2, cooldown_sec=50))
        self.assertIsNone(router.select("погода"))
        self.assertIsNone(router.select("погода"))
        self.assertGreater(router._open_until, 0)
        self.assertIsNone(router.select("погода"))
        errors = [e["error"] for e in self._events()]
        self.assertTrue(any("TimeoutError" in (err or "") for err in errors))
        self.assertTrue(any("circuit open" in (err or "") for err in errors))

    def test_from_env_off_without_keys(self) -> None:
        with mock.patch.dict("os.environ", {"GOOGLE_API_KEY": "", "LLM_API_KEY": "", "LLM_API_BASE": ""}, clear=False):
            with mock.patch.object(llm_mod, "_load_env"):
                self.assertIsNone(LlmRouter.from_env({}))

    def test_from_env_can_be_disabled(self) -> None:
        with mock.patch.dict("os.environ", {"LLM_ENABLED": "0", "GOOGLE_API_KEY": "x"}):
            with mock.patch.object(llm_mod, "_load_env"):
                self.assertIsNone(LlmRouter.from_env({}))
