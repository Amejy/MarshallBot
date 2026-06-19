FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY config /app/config

RUN pip install --no-cache-dir --no-build-isolation .

EXPOSE 8000
