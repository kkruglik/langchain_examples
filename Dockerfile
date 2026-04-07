# Stage 1: install dependencies
FROM python:3.13-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv lock && uv sync --no-dev


# Stage 2: runtime
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY src/ src/
COPY config/ config/

ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken \
    HF_HOME=/app/.cache/huggingface \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed

RUN /app/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

RUN useradd --no-create-home --shell /bin/false app \
    && mkdir -p /app/data /app/.cache/fastembed /app/.cache/huggingface \
    && chown -R app:app /app

USER app

VOLUME /app/data

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "langchain_examples.main"]
