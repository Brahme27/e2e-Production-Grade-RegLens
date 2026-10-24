"""Foundation tests: settings, logging, API basics, LLM router wiring (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reglens.api.app import create_app
from reglens.config import Settings, get_settings
from reglens.log import configure_logging, get_logger


def test_settings_env_override_and_secret_masking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("REGLENS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("REGLENS_GROQ_API_KEY", "secret-value")
    s = Settings()
    assert s.data_dir == tmp_path
    assert "secret-value" not in repr(s)
    assert get_settings() is get_settings()


@pytest.mark.parametrize("json_logs", [True, False])
def test_logging(capsys: pytest.CaptureFixture[str], json_logs: bool) -> None:
    configure_logging("INFO", json_logs)
    get_logger("t").info("hello", n=1)
    assert "hello" in capsys.readouterr().out


def test_api_ops_and_key() -> None:
    with TestClient(create_app(Settings(api_key="k"))) as c:
        assert c.get("/health").json() == {"status": "ok"}
        assert c.get("/ready").status_code == 200
        assert c.post("/v1/echo", json={"text": "hi"}).status_code == 401
        ok = c.post("/v1/echo", json={"text": "hi"}, headers={"X-API-Key": "k"})
        assert ok.json() == {"echo": "hi"}
        assert "reglens_requests_total" in c.get("/metrics").text
