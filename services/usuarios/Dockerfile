FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /run/parking-keys \
    && chown -R appuser:appuser /app /run/parking-keys

USER appuser

EXPOSE 8000
CMD ["sh", "-c", "python scripts/ensure_keys.py && alembic upgrade head && python scripts/seed_admin.py && python scripts/seed_sensor.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

