# syntax=docker/dockerfile:1.7
# RegLens API image (also used for the one-shot indexer and the scheduled worker).
# Build AFTER the pipeline has run locally (`uv run poe pipeline`): the parsed corpus, the
# trained router, the evaluation reports, the LLM answer cache and the small ONNX models are
# baked in, so the image that was evaluated is the image that ships.

# ---------- stage 1: virtual environment with runtime dependencies only ----------
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --no-editable

# ---------- stage 2: runtime ----------
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/artifacts /app/data && chown -R 10001:10001 /app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY configs ./configs
COPY --chown=app:app data/processed/documents ./data/processed/documents
COPY --chown=app:app data/processed/*.json ./data/processed/
COPY --chown=app:app data/policies ./data/policies
COPY --chown=app:app evals ./evals
COPY --chown=app:app cache/llm ./cache/llm
COPY --chown=app:app artifacts/router.json artifacts/embeddings.sqlite ./artifacts/
COPY --chown=app:app artifacts/reports ./artifacts/reports
# CPU models: bge-small (dense), BM25 (sparse), MiniLM cross-encoder (rerank): ~150 MB
COPY --chown=app:app .cache/fastembed/models--Qdrant--bge-small-en-v1.5-onnx-Q ./models/models--Qdrant--bge-small-en-v1.5-onnx-Q
COPY --chown=app:app .cache/fastembed/models--Qdrant--bm25 ./models/models--Qdrant--bm25
COPY --chown=app:app .cache/fastembed/models--Xenova--ms-marco-MiniLM-L-6-v2 ./models/models--Xenova--ms-marco-MiniLM-L-6-v2

# writable folders; a new named volume copies the owner of the folder it is mounted on
RUN mkdir -p /app/artifacts/tickets /app/data/raw /app/data/processed/chunks \
    && chown -R 10001:10001 /app/artifacts /app/data /app/cache

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    REGLENS_ENV=prod \
    REGLENS_LOG_JSON=true \
    REGLENS_DATA_DIR=/app/data \
    REGLENS_ARTIFACTS_DIR=/app/artifacts \
    REGLENS_CONFIGS_DIR=/app/configs \
    REGLENS_EVALS_DIR=/app/evals \
    REGLENS_LLM_CONFIG_PATH=/app/configs/litellm.yaml \
    REGLENS_LLM_CACHE_DIR=/app/cache/llm \
    REGLENS_MODELS_CACHE_DIR=/app/models \
    HF_HUB_OFFLINE=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=True \
    OMP_NUM_THREADS=2 \
    WEB_CONCURRENCY=1

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
# One worker per container (in-process caches and Prometheus counters); scale with replicas.
CMD ["uvicorn", "reglens.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
