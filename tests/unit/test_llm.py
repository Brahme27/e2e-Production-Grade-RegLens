"""LLM client: caching, usage log, JSON parsing, rate-limit handling (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from reglens.config import PROJECT_ROOT, Settings
from reglens.llm.client import (
    LiteLLMBackend,
    LLMClient,
    LLMResponse,
    LLMUnavailableError,
    _parse_wait,
    build_client,
    parse_json_object,
)


class CountingBackend:
    def __init__(self, text: str = '{"ok": true}') -> None:
        self.text = text
        self.calls: list[str] = []

    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        self.calls.append(alias)
        return LLMResponse(self.text, model="fake", prompt_tokens=10, completion_tokens=5)


def test_cache_means_one_call_per_unique_request(tmp_path: Path) -> None:
    backend = CountingBackend()
    client = LLMClient(backend, tmp_path / "cache", usage_log=tmp_path / "usage.jsonl")
    msgs = [{"role": "user", "content": "hi"}]
    first = client.complete_json(msgs, purpose="t")
    second = client.complete_json(msgs, purpose="t")
    assert first == second == {"ok": True}
    assert backend.calls == ["fast-small"]
    assert (client.calls, client.cache_hits) == (1, 1)
    client.complete(msgs, alias="reasoning-large")  # a different alias is a different request
    assert len(backend.calls) == 2
    usage = [json.loads(line) for line in (tmp_path / "usage.jsonl").read_text().splitlines()]
    assert usage[0]["prompt_tokens"] == 10
    assert usage[0]["purpose"] == "t"


def test_cache_only_client_replays_or_refuses(tmp_path: Path) -> None:
    msgs = [{"role": "user", "content": "x"}]
    LLMClient(CountingBackend('{"a": 1}'), tmp_path).complete_json(msgs)
    replay = LLMClient(None, tmp_path)
    assert replay.complete_json(msgs) == {"a": 1}
    with pytest.raises(LLMUnavailableError):
        replay.complete([{"role": "user", "content": "never asked"}])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": [1, 2]}\n```', {"a": [1, 2]}),
        ('Sure! {"repealed": []} hope that helps', {"repealed": []}),
    ],
)
def test_parse_json_object_tolerates_wrapping(text: str, expected: dict[str, Any]) -> None:
    assert parse_json_object(text) == expected


def test_parse_json_object_rejects_non_objects() -> None:
    with pytest.raises(ValueError, match="no JSON"):
        parse_json_object("no json here")
    with pytest.raises(ValueError, match="not an object"):
        parse_json_object("[1, 2]")


def test_parse_rate_limit_wait() -> None:
    assert _parse_wait("Rate limit reached. Please try again in 7.5s.") == 7.5
    assert _parse_wait("Please try again in 1m2.5s") == 62.5
    assert _parse_wait("some other error") is None


def _backend_with(
    monkeypatch: pytest.MonkeyPatch, completion: Any
) -> tuple[LiteLLMBackend, list[float]]:
    slept: list[float] = []
    backend = LiteLLMBackend(
        PROJECT_ROOT / "configs" / "litellm.yaml", "test-key", sleep=slept.append
    )
    monkeypatch.setattr(backend._router, "completion", completion)
    return backend, slept


def test_backend_injects_key_and_reads_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def completion(**kwargs: Any) -> Any:
        seen.update(kwargs)
        usage = SimpleNamespace(prompt_tokens=12, completion_tokens=3)
        message = SimpleNamespace(content='{"x": 1}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model="m")

    backend, _ = _backend_with(monkeypatch, completion)
    reply = backend("fast-small", [{"role": "user", "content": "q"}], json_mode=True, max_tokens=50)
    assert reply.text == '{"x": 1}'
    assert reply.prompt_tokens == 12
    assert seen["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in seen  # per model, from the config (a fallback gets its own)
    efforts = {
        m["model_name"]: m["litellm_params"].get("reasoning_effort")
        for m in backend._router.model_list
    }
    assert efforts["reasoning-large"] == "low" and efforts["fallback"] == "none"
    assert all(m["litellm_params"]["api_key"] == "test-key" for m in backend._router.model_list)


def test_backend_waits_on_rate_limit_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"n": 0}

    def completion(**_: Any) -> Any:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("Rate limit reached. Please try again in 2s.")
        message = SimpleNamespace(content="ok")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None, model="m")

    backend, slept = _backend_with(monkeypatch, completion)
    assert backend("fast-small", [], json_mode=False, max_tokens=5).text == "ok"
    assert slept == [3.0]


def test_backend_gives_up_on_other_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def completion(**_: Any) -> Any:
        raise RuntimeError("invalid api key")

    backend, _ = _backend_with(monkeypatch, completion)
    with pytest.raises(LLMUnavailableError, match="invalid api key"):
        backend("fast-small", [], json_mode=False, max_tokens=5)


def test_build_client_without_key_is_cache_only(tmp_path: Path) -> None:
    settings = Settings(groq_api_key=None, llm_cache_dir=tmp_path, artifacts_dir=tmp_path)
    assert build_client(settings).backend is None
    keyed = Settings(groq_api_key="k", llm_cache_dir=tmp_path, artifacts_dir=tmp_path)
    assert build_client(keyed).backend is not None
    assert build_client(keyed, cache_only=True).backend is None


def test_blank_replies_are_not_cached(tmp_path: Path) -> None:
    class Blank:
        calls = 0

        def __call__(self, *args: Any, **kwargs: Any) -> LLMResponse:
            Blank.calls += 1
            return LLMResponse("  ", model="m", completion_tokens=900)

    client = LLMClient(Blank(), tmp_path)
    msgs = [{"role": "user", "content": "judge this"}]
    client.complete(msgs)
    client.complete(msgs)
    assert Blank.calls == 2 and not list(tmp_path.rglob("*.json"))
