FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY config ./config
COPY fixtures ./fixtures
COPY services ./services
COPY data/models ./data/models

RUN mkdir -p /app/data/reports && chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app
ENV OBS_ROOT=/app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
