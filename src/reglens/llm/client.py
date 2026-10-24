"""LLM access: LiteLLM router (aliases + fallbacks) behind a disk cache and a usage log.

Why a cache in front of every call?
- The free tier allows ~1,000 requests/day per model: re-running an evaluation must not
  spend quota twice.
- Tests and CI replay cached answers, so they are deterministic and need no API key.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from reglens.log import get_logger

log = get_logger(__name__)

Message = dict[str, str]
RATE_LIMIT_WAIT = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.I)
MAX_RATE_LIMIT_WAIT_S = 90.0


class LLMUnavailableError(RuntimeError):
    """No API key, no cached answer, or the provider kept failing."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class Backend(Protocol):
    def __call__(
        self, alias: str, messages: list[Message], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse: ...


def _parse_wait(message: str) -> float | None:
    match = RATE_LIMIT_WAIT.search(message)
    if not match:
        return None
    minutes = float(match.group(1) or 0)
    return minutes * 60 + float(match.group(2))


class LiteLLMBackend:
    """Free open-weight models through a LiteLLM Router built from configs/litellm.yaml."""

    def __init__(
        self,
        config_path: Path,
        groq_api_key: str,
        sleep: Callable[[float], None] = time.sleep,
        max_rate_limit_retries: int = 3,
    ) -> None:
        from litellm.router import Router  # noqa: PLC0415 - heavy import, only when used

        cfg: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        model_list = []
        for entry in cfg["model_list"]:
            params = dict(entry["litellm_params"])
            if params["model"].startswith("groq/"):
                params["api_key"] = groq_api_key
            model_list.append({"model_name": entry["model_name"], "litellm_params": params})
        settings = cfg.get("router_settings", {})
        self._router = Router(
            model_list=model_list,
            fallbacks=cfg.get("fallbacks", []),
            num_retries=settings.get("num_retries", 1),
            timeout=settings.get("timeout", 60),
        )
        self._sleep = sleep
        self._max_rate_limit_retries = max_rate_limit_retries

    def __call__(
        self, alias: str, messages: list[Message], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": alias,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "reasoning_effort": "low",  # gpt-oss: keep hidden reasoning short (tokens = quota)
            "drop_params": True,  # models without reasoning_effort just ignore it
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        for attempt in range(self._max_rate_limit_retries + 1):
            started = time.perf_counter()
            try:
                response: Any = self._router.completion(**kwargs)
            except Exception as exc:  # litellm raises many provider-specific types
                wait = _parse_wait(str(exc))
                if wait is None or attempt == self._max_rate_limit_retries:
                    raise LLMUnavailableError(f"{type(exc).__name__}: {exc}") from exc
                wait = min(wait + 1.0, MAX_RATE_LIMIT_WAIT_S)
                log.warning("llm_rate_limited", alias=alias, wait_s=round(wait, 1))
                self._sleep(wait)
                continue
            usage = getattr(response, "usage", None)
            return LLMResponse(
                text=str(response.choices[0].message.content or ""),
                model=str(getattr(response, "model", alias)),
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        raise LLMUnavailableError("rate limited")  # pragma: no cover - loop always returns

    def stream(self, alias: str, messages: list[Message], *, max_tokens: int) -> Iterator[str]:
        """Yield text deltas as the model produces them (no rate-limit retry mid-stream)."""
        try:
            response: Any = self._router.completion(
                model=alias,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens,
                reasoning_effort="low",
                drop_params=True,
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield str(delta)
        except Exception as exc:
            raise LLMUnavailableError(f"{type(exc).__name__}: {exc}") from exc


STREAM_REPLAY_CHARS = 24


class LLMClient:
    """Cached, logged access to a backend. ``backend=None`` means cache-only (CI/tests)."""

    def __init__(
        self,
        backend: Backend | None,
        cache_dir: Path,
        usage_log: Path | None = None,
    ) -> None:
        self.backend = backend
        self.cache_dir = cache_dir
        self.usage_log = usage_log
        self.calls = 0
        self.cache_hits = 0

    @staticmethod
    def cache_key(alias: str, messages: list[Message], json_mode: bool, max_tokens: int) -> str:
        payload = json.dumps(
            {"alias": alias, "messages": messages, "json": json_mode, "max_tokens": max_tokens},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def complete(
        self,
        messages: list[Message],
        *,
        alias: str = "fast-small",
        json_mode: bool = False,
        max_tokens: int = 1024,
        purpose: str = "",
    ) -> LLMResponse:
        key = self.cache_key(alias, messages, json_mode, max_tokens)
        path = self._cache_path(key)
        if path.exists():
            self.cache_hits += 1
            record = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse(**{**record["response"], "cached": True})
        if self.backend is None:
            raise LLMUnavailableError("no LLM backend configured and no cached answer")
        response = self.backend(alias, messages, json_mode=json_mode, max_tokens=max_tokens)
        self.calls += 1
        self._store(path, alias, purpose, response)
        return response

    def stream(
        self,
        messages: list[Message],
        *,
        alias: str = "reasoning-large",
        max_tokens: int = 1024,
        purpose: str = "",
    ) -> Iterator[str]:
        """Stream text; a cached answer is replayed in small pieces, a new one is cached."""
        key = self.cache_key(alias, messages, False, max_tokens)
        path = self._cache_path(key)
        if path.exists() or self.backend is None or not hasattr(self.backend, "stream"):
            text = self.complete(messages, alias=alias, max_tokens=max_tokens, purpose=purpose).text
            for start in range(0, len(text), STREAM_REPLAY_CHARS):
                yield text[start : start + STREAM_REPLAY_CHARS]
            return
        started = time.perf_counter()
        parts: list[str] = []
        for delta in self.backend.stream(alias, messages, max_tokens=max_tokens):
            parts.append(delta)
            yield delta
        response = LLMResponse(
            text="".join(parts), model=alias, latency_ms=(time.perf_counter() - started) * 1000
        )
        self.calls += 1
        self._store(path, alias, purpose, response)

    def _store(self, path: Path, alias: str, purpose: str, response: LLMResponse) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"alias": alias, "purpose": purpose, "response": asdict(response)}
        text = json.dumps(record, ensure_ascii=False, indent=1) + "\n"
        path.write_text(text, encoding="utf-8")
        self._log_usage(alias, purpose, response)

    def complete_json(
        self,
        messages: list[Message],
        *,
        alias: str = "fast-small",
        max_tokens: int = 1024,
        purpose: str = "",
        strict: bool = True,
    ) -> dict[str, Any]:
        """``strict=False`` skips the provider's JSON mode (some reasoning models, e.g. Qwen,
        emit thinking text the provider's JSON validator rejects); we parse it ourselves."""
        response = self.complete(
            messages, alias=alias, json_mode=strict, max_tokens=max_tokens, purpose=purpose
        )
        return parse_json_object(response.text)

    def _log_usage(self, alias: str, purpose: str, response: LLMResponse) -> None:
        if self.usage_log is None:
            return
        self.usage_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "alias": alias,
            "purpose": purpose,
            "model": response.model,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "latency_ms": round(response.latency_ms),
        }
        with self.usage_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


THINKING = re.compile(r"<think>.*?</think>", re.S)


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output (tolerates ```json fences / stray prose)."""
    text = THINKING.sub("", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if not match:
            raise ValueError(f"no JSON object in model output: {text[:200]!r}") from None
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("model output is JSON but not an object")
    return value


def build_client(settings: Any, *, cache_only: bool = False) -> LLMClient:
    """The project's LLM client: live backend when a key is set, cache-only otherwise."""
    backend: Backend | None = None
    if not cache_only and settings.groq_api_key is not None:
        backend = LiteLLMBackend(settings.llm_config_path, settings.groq_api_key.get_secret_value())
    return LLMClient(
        backend,
        cache_dir=settings.llm_cache_dir,
        usage_log=settings.artifacts_dir / "llm-usage.jsonl",
    )
