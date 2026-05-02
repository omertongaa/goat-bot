FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7778 \
    GOAT_DATA_DIR=/app/data \
    GOAT_OUTPUTS_DIR=/app/outputs

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Persist data + outputs as named volumes
VOLUME ["/app/data", "/app/outputs"]

EXPOSE 7778

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:7778/api/core/system || exit 1

CMD ["python", "app.py"]
