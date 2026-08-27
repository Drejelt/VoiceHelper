"""LLM as intent extractor only.

The model never executes commands and never talks to the user. It may pick one
tool from the closed set. If the key is missing, the request times out, the
circuit is open, or the reply is garbage — callers get None and keep the
deterministic matcher as the only path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from functional_modules.intent import (
    SOURCE_FALLBACK,
    SOURCE_LLM,
    TOOL_SCHEMAS,
    sanitize_intent,
)

MAX_UTTERANCE = 400
MAX_OUTPUT_TOKENS = 128
DEFAULT_TIMEOUT = 3.0
FAILURE_THRESHOLD = 3
COOLDOWN_SEC = 60.0
MAX_CALLS_PER_MINUTE = 12
LOG_PATH = Path("logs/llm.jsonl")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = (
    "Ты классификатор намерений локального голосового ассистента. "
    "Не отвечай пользователю текстом. Вызови ровно один tool. "
    "Если фраза не команда ассистента — вызови unknown."
)

HttpPost = Callable[[str, dict[str, Any], dict[str, str] | None, float], dict[str, Any]]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / "api_keys.env")


def _http_post(url: str, body: dict[str, Any], headers: dict[str, str] | None, timeout: float) -> dict[str, Any]:
    import requests

    response = requests.post(url, json=body, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def _truthy(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _append_log(event: dict[str, Any]) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        logging.error("Could not write LLM usage log: %s", exc)


class CircuitOpen(RuntimeError):
    pass


class RateLimited(RuntimeError):
    pass


@dataclass
class LlmLimits:
    timeout_sec: float = DEFAULT_TIMEOUT
    max_utterance: int = MAX_UTTERANCE
    failure_threshold: int = FAILURE_THRESHOLD
    cooldown_sec: float = COOLDOWN_SEC
    max_calls_per_minute: int = MAX_CALLS_PER_MINUTE


class LlmRouter:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        api_base: str = "",
        limits: LlmLimits | None = None,
        http_post: HttpPost | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.limits = limits or LlmLimits()
        self._http_post = http_post or _http_post
        self._now = now or time.monotonic
        self._failures = 0
        self._open_until = 0.0
        self._window: deque[float] = deque()

    @classmethod
    def from_env(cls, config: dict[str, Any] | None = None) -> LlmRouter | None:
        _load_env()
        config = config or {}
        enabled = _truthy(os.getenv("LLM_ENABLED"))
        if enabled is False:
            return None
        if enabled is None and config.get("LLM_ENABLED") is False:
            return None

        api_base = (os.getenv("LLM_API_BASE") or "").strip()
        openai_key = (os.getenv("LLM_API_KEY") or "").strip()
        gemini_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
        model = (
            os.getenv("LLM_MODEL")
            or str(config.get("LLM_MODEL") or "")
            or ("gpt-4.1-mini" if api_base else "gemini-2.0-flash")
        )
        timeout = float(os.getenv("LLM_TIMEOUT_SEC") or config.get("LLM_TIMEOUT_SEC") or DEFAULT_TIMEOUT)

        if api_base and openai_key:
            return cls(
                provider="openai",
                model=model,
                api_key=openai_key,
                api_base=api_base,
                limits=LlmLimits(timeout_sec=timeout),
            )
        if gemini_key:
            return cls(
                provider="gemini",
                model=model if not api_base else model,
                api_key=gemini_key,
                limits=LlmLimits(timeout_sec=timeout),
            )
        logging.info("LLM router off: no GOOGLE_API_KEY / LLM_API_KEY")
        return None

    def available(self) -> bool:
        return bool(self.api_key) and self._now() >= self._open_until

    def select(self, utterance: str) -> Intent | None:
        text = (utterance or "").strip()
        started = self._now()
        event: dict[str, Any] = {
            "ts": time.time(),
            "source": SOURCE_LLM,
            "provider": self.provider,
            "model": self.model,
            "utterance": text[:200],
            "tool": None,
            "latency_ms": 0,
            "prompt_tokens": None,
            "completion_tokens": None,
            "error": None,
        }
        try:
            if not text:
                raise ValueError("empty utterance")
            if len(text) > self.limits.max_utterance:
                raise ValueError(f"utterance longer than {self.limits.max_utterance} chars")
            self._before_call()
            if self.provider == "openai":
                tool, args, usage = self._select_openai(text)
            else:
                tool, args, usage = self._select_gemini(text)
            event["prompt_tokens"] = usage.get("prompt_tokens")
            event["completion_tokens"] = usage.get("completion_tokens")
            intent = sanitize_intent(tool, args, source=SOURCE_LLM, utterance=text)
            if intent is None:
                raise ValueError(f"tool not in closed set: {tool}")
            self._failures = 0
            event["tool"] = intent.tool
            return intent
        except (CircuitOpen, RateLimited) as exc:
            event["source"] = SOURCE_FALLBACK
            event["error"] = str(exc)
            return None
        except Exception as exc:  # noqa: BLE001 — voice loop must not die on a bad model
            self._on_failure()
            event["source"] = SOURCE_FALLBACK
            event["error"] = f"{type(exc).__name__}: {exc}"
            logging.warning("LLM intent extract failed, using keywords only: %s", exc)
            return None
        finally:
            event["latency_ms"] = int((self._now() - started) * 1000)
            _append_log(event)
            logging.info(
                "llm intent source=%s tool=%s latency_ms=%s tokens=%s/%s error=%s",
                event["source"],
                event["tool"],
                event["latency_ms"],
                event["prompt_tokens"],
                event["completion_tokens"],
                event["error"],
            )

    def _before_call(self) -> None:
        now = self._now()
        if now < self._open_until:
            raise CircuitOpen("llm circuit open")
        while self._window and now - self._window[0] > 60.0:
            self._window.popleft()
        if len(self._window) >= self.limits.max_calls_per_minute:
            raise RateLimited("llm rate limited")
        self._window.append(now)

    def _on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.limits.failure_threshold:
            self._open_until = self._now() + self.limits.cooldown_sec
            self._failures = 0
            logging.error("LLM circuit opened for %.0fs", self.limits.cooldown_sec)

    def _select_openai(self, text: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        url = f"{self.api_base}/chat/completions"
        body = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "tool_choice": "required",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": spec["name"],
                        "description": spec["description"],
                        "parameters": spec["parameters"],
                    },
                }
                for spec in TOOL_SCHEMAS
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = self._http_post(url, body, headers, self.limits.timeout_sec)
        message = ((data.get("choices") or [{}])[0].get("message")) or {}
        calls = message.get("tool_calls") or []
        if not calls:
            raise ValueError("openai reply had no tool_calls")
        fn = (calls[0].get("function") or {})
        name = str(fn.get("name") or "")
        raw_args = fn.get("arguments") or "{}"
        args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        usage = data.get("usage") or {}
        return name, args, {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }

    def _select_gemini(self, text: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        url = GEMINI_URL.format(model=self.model) + f"?key={self.api_key}"
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "tools": [{"functionDeclarations": TOOL_SCHEMAS}],
            "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
            "generationConfig": {"temperature": 0, "maxOutputTokens": MAX_OUTPUT_TOKENS},
        }
        data = self._http_post(url, body, {"Content-Type": "application/json"}, self.limits.timeout_sec)
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
        call = None
        for part in parts:
            if "functionCall" in part:
                call = part["functionCall"]
                break
        if not call:
            raise ValueError("gemini reply had no functionCall")
        name = str(call.get("name") or "")
        args = dict(call.get("args") or {})
        usage = data.get("usageMetadata") or {}
        return name, args, {
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
        }
