# 05: Logging

**File:** `src/reglens/log.py`

## What
Two functions:
- `configure_logging(level, json_logs)` is called once when a program starts.
- `get_logger(name)` gives each module its own logger.

```python
log = get_logger(__name__)
log.info("decision_made", application_id="A123", decision="approve", pd=0.041)
```

## Why
`print("approved")` is fine for a script, useless for a service. When a customer
complains *"why was I declined at 3:14 pm?"*, you need to **search** logs by
`application_id`, filter by `decision`, and see the exact model version. That only works if
logs are **structured**: fields, not sentences.

| Where we run | Log format | Why |
|---|---|---|
| Your laptop | Coloured, human-readable | Easy to read while developing |
| Docker / cloud (`REGLENS_LOG_JSON=true`) | One JSON object per line | Log tools (CloudWatch, Grafana Loki) can index and query every field |

Every line gets a UTC timestamp and a level (`info`, `warning`, `error`) automatically.

## Why structlog?
It's the most popular structured-logging library for Python. It adds key-value context
cleanly, and the same code can output pretty text or JSON with one switch.

## Naming note
The file is `log.py`, not `logging.py`. A file called `logging.py` would sit right next to
Python's own `logging` module with the same name, which confuses humans and tools.
