FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY services/api ./services/api
COPY app/config.py app/middleware.py ./app/
COPY app/api ./app/api
COPY app/clients ./app/clients
COPY app/collector/prometheus-collector.py ./app/collector/prometheus-collector.py
COPY app/core ./app/core
COPY app/db ./app/db
COPY app/decision ./app/decision
COPY app/domain ./app/domain
COPY app/grpc ./app/grpc
COPY app/models ./app/models
COPY app/scheduler ./app/scheduler
COPY app/utils ./app/utils

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()"

CMD ["python", "-m", "uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
