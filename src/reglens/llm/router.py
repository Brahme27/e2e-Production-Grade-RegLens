"""LLM access through LiteLLM's Router: aliases, fallbacks, retries, timeouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml


class ChatModel(Protocol):
    """Anything that turns chat messages into text (real LLM or a test fake)."""

    def complete(self, messages: list[dict[str, str]]) -> str: ...


class LiteLLMChat:
    """Open-weight models via a LiteLLM Router built from configs/litellm.yaml."""

    def __init__(self, config_path: Path, groq_api_key: str, alias: str = "fast-small") -> None:
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
            timeout=settings.get("timeout", 20),
        )
        self._alias = alias

    def complete(self, messages: list[dict[str, str]]) -> str:
        response: Any = self._router.completion(
            model=self._alias,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return str(response.choices[0].message.content)
