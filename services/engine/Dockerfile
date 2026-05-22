FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-engine.txt .
RUN pip install --no-cache-dir -r requirements-engine.txt

COPY services/engine ./services/engine
COPY app/config.py ./app/
COPY app/collector/prometheus-collector.py ./app/collector/prometheus-collector.py
COPY app/core ./app/core
COPY app/db ./app/db
COPY app/decision ./app/decision
COPY app/domain ./app/domain
COPY app/executor ./app/executor
COPY app/grpc ./app/grpc
COPY app/models ./app/models
COPY app/scoring ./app/scoring
COPY app/utils ./app/utils

EXPOSE 50054

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1', 50054), 2); s.close()"

CMD ["python", "-m", "services.engine.server"]
