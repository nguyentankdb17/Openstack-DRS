FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY . .

RUN python -m grpc_tools.protoc \
    -I protos \
    --python_out app/grpc \
    --grpc_python_out app/grpc \
    protos/*.proto

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 50053

RUN echo 'import socket,sys\ns=socket.socket()\ntry:\n s.settimeout(2)\n s.connect(("127.0.0.1",50053))\n sys.exit(0)\nexcept Exception:\n sys.exit(1)\nfinally:\n s.close()' > /healthcheck.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python /healthcheck.py

CMD ["python", "services/scoring/server.py"]