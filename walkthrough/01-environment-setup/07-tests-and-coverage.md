# 07: Tests and coverage

**File:** `tests/unit/test_config_and_logging.py`

## What
Our first five automated tests:

| Test | Proves that… |
|---|---|
| `test_defaults_point_inside_project` | With no settings given, data folders sit inside the project |
| `test_environment_variables_override_defaults` | Environment variables really override defaults, **and the secret key never appears when settings are printed** |
| `test_get_settings_is_cached` | The whole app shares one settings object |
| `test_logging_emits_event` (×2) | Logging works in both pretty and JSON mode |

## Why test something this small?
1. **Tests are the safety net for everything later.** When phase 07 adds the API and phase 14
   adds Docker, these tests confirm the foundation still works.
2. **The secret test guards a real risk.** API keys leaking through logs is a classic incident.
3. **It sets the habit:** every chunk from now on ships with tests.

## How a test reads (Arrange → Act → Assert)
```python
def test_environment_variables_override_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("REGLENS_ENV", "test")          # Arrange: pretend env var is set
    settings = Settings()                                # Act: build settings
    assert settings.env == "test"                        # Assert: it was picked up
```
`monkeypatch` temporarily changes environment variables just for that test, and `tmp_path`
gives a throw-away folder. Neither touches your real machine.

## Coverage: the 80% rule
**Coverage** = the percentage of code lines that tests actually executed. In `pyproject.toml`:
```toml
[tool.coverage.report]
fail_under = 80
```
If coverage drops below 80%, the test run **fails**. That stops "I'll write tests later"
(which means never). 80% is a common industry bar: high enough to matter, without chasing
trivial lines.

## How to run
```bash
uv run poe test
```
You should see `5 passed` and `Total coverage: 100.00%`.
