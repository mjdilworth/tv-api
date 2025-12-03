FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update \ 
    && apt-get install --no-install-recommends -y build-essential curl \ 
    && pip install --no-cache-dir "poetry==${POETRY_VERSION}" \ 
    && apt-get purge -y --auto-remove build-essential curl \ 
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --only main

COPY src ./src

EXPOSE 8280

CMD ["poetry", "run", "uvicorn", "tv_api.main:app", "--host", "0.0.0.0", "--port", "8280"]
