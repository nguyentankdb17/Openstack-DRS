# OpenstackDRS - Distributed Resource Scheduler for OpenStack

Decentralized Resource Scheduler for OpenStack (OpenstackDRS) is a comprehensive metrics collection and analysis system built for OpenStack environments. It collects metrics from Prometheus, stores them in Redis, and provides APIs for querying and exporting data in pandas DataFrame format.

## Features

- 📊 **Metrics Collection**: Automatic collection from Prometheus
- 🔄 **Redis Stream Storage**: Efficient metrics storage with consumer groups
- 📈 **Data Export**: Export metrics as pandas DataFrames
- 🔍 **Advanced Querying**: Filter metrics by host, metric type, and time range
- 🏥 **Health Monitoring**: Real-time health checks for services
- 🚀 **Async API**: Fast, non-blocking REST API built with FastAPI

## Quick Start

### Installation

1. Clone the repository
```bash
git clone https://github.com/nguyentankdb17/OpenstackDRS.git
cd OpenstackDRS
```

2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure environment
```bash
cp .env.example .env
# Edit .env with your Prometheus and Redis connection details
```

5. Run the application
```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

For detailed API documentation and usage examples, see [API_GUIDE.md](docs/API_GUIDE.md)

### Quick API Examples

**Get available instances:**
```bash
curl http://localhost:8000/api/v1/collector/instances
```

**Collect metrics from all instances:**
```bash
curl -X POST http://localhost:8000/api/v1/collector/all-instances
```

**Export metrics as DataFrame:**
```bash
curl -X POST http://localhost:8000/api/v1/export/dataframe?count=100
```

## Project Structure

```
OpenstackDRS/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── collector.py      # Metrics collection endpoints
│   │       │   ├── export.py         # Data export endpoints
│   │       │   ├── health.py         # Health check endpoints
│   │       │   ├── metrics.py        # Metrics query endpoints
│   │       │   └── streams.py        # Stream statistics endpoints
│   │       └── router.py
│   ├── services/
│   │   └── collector/
│   │       ├── collector_service.py  # Metrics collection logic
│   │       └── reader_service.py     # Metrics query and export
│   ├── clients/
│   │   ├── prometheus_client.py      # Prometheus integration
│   │   └── redis_client.py           # Redis integration
│   ├── schemas/                      # Pydantic models
│   └── utils/
│       ├── constants.py
│       └── logger.py
├── docs/
│   └── API_GUIDE.md                  # Comprehensive API documentation
├── configs/
└── requirements.txt
```

## Configuration

Environment variables (create `.env` file):

```env
# Prometheus
PROMETHEUS_HOST=http://prometheus:9090
PROMETHEUS_TIMEOUT=30

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_STREAM_KEY=metrics:stream

# Collector
COLLECTOR_INSTANCE=compute1
COLLECTOR_LOOKBACK_MINUTES=5
COLLECTOR_QUERY_STEP=15s

# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=5
```

## Data Model

### MetricData Structure
```python
{
    "metric_name": "cpu_usage_percent",
    "host_id": "compute1",
    "value": 42.5,
    "timestamp": "1711770645000",
    "labels": "{\"job\": \"compute-node-exporter\"}"
}
```

## Development

### Running Tests
```bash
pytest tests/
```

### Running with Docker
```bash
docker-compose up
```

### Code Style
- Follow PEP 8
- Use type hints
- Document all public functions

## Dependencies

- **FastAPI**: Modern web framework
- **Pandas**: Data manipulation and export
- **Redis**: Metrics storage
- **Prometheus Client**: Metrics querying
- **APScheduler**: Task scheduling

See [requirements.txt](requirements.txt) for complete list.

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/collector/manual` | Collect specific metric type |
| POST | `/api/v1/collector/all-instances` | Collect from all instances |
| POST | `/api/v1/collector/instance/{id}` | Collect from specific instance |
| GET | `/api/v1/collector/instances` | List available instances |
| POST | `/api/v1/export/dataframe` | Export metrics as DataFrame |
| POST | `/api/v1/export/joined-dataframe` | Export with running VMs info |
| GET | `/api/v1/statistics/latest` | Get latest metrics |
| GET | `/api/v1/statistics/host/{id}` | Get metrics by host |
| GET | `/api/v1/statistics/name/{name}` | Get metrics by name |
| GET | `/api/v1/health` | Health status |

## Troubleshooting

### Connection Issues
- Verify Prometheus is running and accessible
- Check Redis connection settings
- Review logs in `app/utils/logger.py`

### No Metrics Returned
- Check if metrics have been collected via `/collector/` endpoints
- Verify Prometheus has data for the requested metric types
- Review Redis stream contents with `redis-cli XLEN metrics:stream`

## Contributing

1. Create a feature branch
2. Make your changes
3. Write tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Author

Nguyen Tan

## Support

For issues and questions:
1. Check [API_GUIDE.md](docs/API_GUIDE.md)
2. Review application logs
3. Open an issue on GitHub