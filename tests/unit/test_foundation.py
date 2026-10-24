"""Foundation tests: settings, logging, API basics, LLM router wiring (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_database_url_from_rds_secret() -> None:
    s = Settings(
        db_host="db.internal", db_credentials='{"username": "reglens", "password": "p@ss/word"}'
    )
    assert s.sqlalchemy_url == "postgresql+psycopg://reglens:p%40ss%2Fword@db.internal:5432/reglens"
    assert Settings(database_url="sqlite:///x.db").sqlalchemy_url == "sqlite:///x.db"
    assert Settings().sqlalchemy_url.startswith("sqlite:///")
