# 04: Configuration and secrets

**Files:** `src/reglens/config.py`, `.env.example`

## What
One `Settings` class holds every setting the app needs: environment name, log level,
folder paths, random seed and the Groq API key. Any setting can be changed **without
touching code**, by setting an environment variable such as `REGLENS_LOG_LEVEL=DEBUG` or a
line in a `.env` file.

## Why
- **The same code runs everywhere.** On your laptop the data folder is `D:\...\data`; inside
  Docker it's `/app/data`; in AWS it might be an S3 mount. Only the settings change, never the code.
- **Secrets never live in code.** The Groq key goes in `.env` (git-ignored) locally, and in a
  secret manager in the cloud (AWS Secrets Manager, Kubernetes Secrets).
- **Mistakes fail fast.** If someone sets `REGLENS_LOG_LEVEL=LOUD`, the app refuses to start
  with a clear error instead of misbehaving later.

## How it works (plain words)
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REGLENS_", env_file=".env")
    env: Literal["local", "dev", "prod", "test"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    data_dir: Path = PROJECT_ROOT / "data"
    groq_api_key: SecretStr | None = None
```
- Each line is a setting with a **type** and a **default**.
- `env_prefix="REGLENS_"` means the variable `REGLENS_ENV` fills the `env` field. The
  prefix stops clashes with other programs' variables.
- `Literal[...]` lists the only allowed values.
- `SecretStr` wraps the API key so that printing or logging the settings shows `**********`
  instead of the real key. A test checks this.
- `get_settings()` builds the object **once** and reuses it (`lru_cache`). Settings are read
  in one place, so every part of the app agrees.

`.env.example` is a committed template that shows *which* variables exist, with no real
values. New developers copy it to `.env` and fill it in.

## Why pydantic-settings?
It's the standard in modern Python services (FastAPI uses pydantic too). It reads, converts
and validates environment variables for us. Writing that by hand with `os.environ` is
error-prone.

## How to run
```bash
copy .env.example .env      # Windows   (cp on Mac/Linux)
# then put your Groq key after REGLENS_GROQ_API_KEY=
```
