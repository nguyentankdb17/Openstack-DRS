FROM python:3.11.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-analytics.txt .
RUN pip install --no-cache-dir -r requirements-analytics.txt

COPY services/analytics ./services/analytics
COPY app/config.py ./app/
COPY app/core ./app/core
COPY app/domain ./app/domain
COPY app/collector/prometheus-collector.py ./app/collector/prometheus-collector.py
COPY app/grpc ./app/grpc
COPY app/models ./app/models
# Fine-tuned AutoGluon models are intentionally not copied into the image.
# Mount them at runtime and set CHRONOS_FINETUNED_MODEL_PATH.
COPY app/predictor/chronos_predictor.py app/predictor/feature_builder.py ./app/predictor/
COPY app/utils ./app/utils

EXPOSE 50052

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1', 50052), 2); s.close()"

CMD ["python", "-m", "services.analytics.server"]
