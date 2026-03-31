# OpenstackDRS API Guide

## Overview

OpenstackDRS (Decentralized Resource Scheduler for OpenStack) provides a comprehensive REST API for collecting, querying, and exporting metrics from Prometheus. All responses are in JSON format.

---

## Base URL

```
http://localhost:8000/api/v1
```

---

## Authentication

Currently, no authentication is required. Future versions will support token-based authentication.

---

## API Endpoints

### 1. Collector Endpoints

#### 1.1 Manual Metric Collection

**POST** `/collector/manual`

Trigger manual collection of metrics for a specific instance.

**Query Parameters:**
- `instance` (string, optional): Instance ID to collect from. If not provided, uses default from config.
- `metric_type` (string, required): Type of metric to collect
  - `memory`: Memory usage percentage
  - `cpu`: CPU usage percentage
  - `swap`: Swap usage percentage
  - `running_vm`: Count of running VMs

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/collector/manual?instance=compute1&metric_type=cpu"
```

**Success Response (200):**
```json
{
  "success": true,
  "entry_count": 150,
  "metric_type": "cpu",
  "instance": "compute1",
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

#### 1.2 Collect All Instances

**POST** `/collector/all-instances`

Collect metrics from all available instances.

**Query Parameters:**
- `start_minutes_ago` (integer, optional, default=5): Minutes to look back (1-240)

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/collector/all-instances?start_minutes_ago=10"
```

**Success Response (200):**
```json
{
  "success": true,
  "total_entries": 4500,
  "instances_count": 5,
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

#### 1.3 Collect Specific Instance

**POST** `/collector/instance/{instance_id}`

Collect all metric types for a specific instance.

**Path Parameters:**
- `instance_id` (string, required): Instance identifier

**Query Parameters:**
- `start_minutes_ago` (integer, optional, default=5): Minutes to look back (1-240)

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/collector/instance/compute1?start_minutes_ago=30"
```

**Success Response (200):**
```json
{
  "success": true,
  "total_entries": 1200,
  "instances_count": 1,
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

#### 1.4 Get Available Instances

**GET** `/collector/instances`

Get list of all available instances from Prometheus.

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/collector/instances"
```

**Success Response (200):**
```json
{
  "instances": [
    "compute1",
    "compute2",
    "compute3",
    "controller1"
  ],
  "count": 4,
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

### 2. Export Endpoints

#### 2.1 Export Metrics as DataFrame

**POST** `/export/dataframe`

Export latest metrics as a pandas DataFrame (returned as JSON records).

**Query Parameters:**
- `count` (integer, optional, default=100): Number of metrics to export (1-5000)
- `item_id_field` (string, optional, default="metric_name"): Field to use as item ID
- `value_field` (string, optional, default="value"): Field to use as value

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/export/dataframe?count=200&item_id_field=metric_name&value_field=value"
```

**Success Response (200):**
```json
{
  "success": true,
  "count": 200,
  "data": [
    {
      "item_id": "cpu",
      "timestamp": "2024-03-29T10:25:30.000000",
      "value": 45.5,
      "host_id": "compute1",
      "labels": "{\"job\": \"compute-node-exporter\"}"
    },
    {
      "item_id": "memory",
      "timestamp": "2024-03-29T10:25:45.000000",
      "value": 72.3,
      "host_id": "compute1",
      "labels": "{\"job\": \"compute-node-exporter\"}"
    }
  ],
  "columns": [
    "item_id",
    "timestamp",
    "value",
    "host_id",
    "labels"
  ],
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

**Error Response (404):**
```json
{
  "detail": "No metrics found to export"
}
```

---

#### 2.2 Export Joined Metrics as DataFrame

**POST** `/export/joined-dataframe`

Export metrics joined with running VMs information as a pandas DataFrame (returned as JSON records).

**Query Parameters:**
- `start_hours_ago` (integer, optional, default=1): Hours to look back (1-30)
- `metric_names` (string, optional): Comma-separated metric names to include (e.g., "cpu,memory")

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/export/joined-dataframe?start_hours_ago=2&metric_names=cpu,memory"
```

**Success Response (200):**
```json
{
  "success": true,
  "count": 150,
  "data": [
    {
      "item_id": "cpu",
      "timestamp": "2024-03-29T08:30:00.000000",
      "value": 35.2,
      "host_id": "compute1",
      "running_vm": 12,
      "labels": "{\"job\": \"compute-node-exporter\"}"
    },
    {
      "item_id": "memory",
      "timestamp": "2024-03-29T08:30:15.000000",
      "value": 65.8,
      "host_id": "compute1",
      "running_vm": 12,
      "labels": "{\"job\": \"compute-node-exporter\"}"
    }
  ],
  "columns": [
    "item_id",
    "timestamp",
    "value",
    "host_id",
    "running_vm",
    "labels"
  ],
  "time_range": {
    "start": "2024-03-29T08:30:45.123456",
    "end": "2024-03-29T10:30:45.123456"
  },
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

### 3. Metrics Query Endpoints

#### 3.1 Get Latest Metrics

**GET** `/metrics/latest`

Get the latest N metrics from the metrics stream.

**Query Parameters:**
- `count` (integer, optional, default=10): Number of metrics to return

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/metrics/latest?count=20"
```

**Success Response (200):**
```json
{
  "success": true,
  "count": 20,
  "data": [
    {
      "entry_id": "1711770645000-0",
      "metric_name": "cpu_usage_percent",
      "host_id": "compute1",
      "value": 42.5,
      "timestamp": "1711770645",
      "labels": "{\"job\": \"compute-node-exporter\"}"
    }
  ],
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

#### 3.2 Get Metrics by Host

**GET** `/metrics/host/{host_id}`

Get metrics filtered by specific host/instance.

**Path Parameters:**
- `host_id` (string, required): Host identifier

**Query Parameters:**
- `count` (integer, optional, default=100): Number of metrics to return

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/metrics/host/compute1?count=50"
```

**Success Response (200):**
```json
{
  "success": true,
  "host_id": "compute1",
  "count": 50,
  "data": [
    {
      "entry_id": "1711770645000-0",
      "metric_name": "cpu_usage_percent",
      "value": 42.5,
      "timestamp": "1711770645"
    }
  ],
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

#### 3.3 Get Metrics by Name

**GET** `/metrics/name/{metric_name}`

Get metrics filtered by metric name.

**Path Parameters:**
- `metric_name` (string, required): Metric name (e.g., "cpu_usage_percent")

**Query Parameters:**
- `count` (integer, optional, default=100): Number of metrics to return

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/metrics/name/memory_usage_percent?count=50"
```

**Success Response (200):**
```json
{
  "success": true,
  "metric_name": "memory_usage_percent",
  "count": 50,
  "data": [
    {
      "entry_id": "1711770645000-0",
      "host_id": "compute1",
      "value": 72.3,
      "timestamp": "1711770645"
    }
  ],
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

### 4. Health Check Endpoints

#### 4.1 Health Status

**GET** `/health`

Check overall application health status.

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

**Success Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2024-03-29T10:30:45.123456",
  "services": {
    "prometheus": "connected",
    "redis": "connected"
  }
}
```

---

#### 4.2 Stream Info

**GET** `/health/stream-info`

Get detailed information about the Redis metrics stream.

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/health/stream-info"
```

**Success Response (200):**
```json
{
  "success": true,
  "stream_key": "metrics:stream",
  "length": 45000,
  "first_entry": "1711700000000-0",
  "last_entry": "1711770645000-100",
  "first_timestamp": "2024-03-29T00:13:20.000000",
  "last_timestamp": "2024-03-29T10:30:45.000000",
  "consumer_groups": 1,
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

### 5. Stream Endpoints

#### 5.1 Stream Stats

**GET** `/streams/stats`

Get statistics about the metrics stream(s).

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/streams/stats"
```

**Success Response (200):**
```json
{
  "success": true,
  "total_streams": 1,
  "total_entries": 45000,
  "streams": [
    {
      "name": "metrics:stream",
      "entries_count": 45000,
      "first_id": "1711700000000-0",
      "last_id": "1711770645000-100"
    }
  ],
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

---

## Common Query Parameters

| Parameter | Type | Description | Default | Range |
|-----------|------|-------------|---------|-------|
| `count` | integer | Number of records/metrics to return | 10-100 | 1-5000 |
| `start_minutes_ago` | integer | Look back period in minutes | 5 | 1-240 |
| `start_hours_ago` | integer | Look back period in hours | 1 | 1-30 |
| `metric_type` | string | Type of metric | - | cpu, memory, swap, running_vm |

---

## Error Handling

### Common Error Responses

**400 Bad Request**
```json
{
  "detail": "Invalid query parameters"
}
```

**404 Not Found**
```json
{
  "detail": "Resource not found"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Failed to collect metrics: Connection timeout"
}
```

---

## Data Types and Formats

### Timestamp Format
- ISO 8601 format: `"2024-03-29T10:30:45.123456"`
- Unix timestamp (in stream): `"1711770645000"` (milliseconds)

### Metric Types
- **cpu**: CPU usage percentage (0-100)
- **memory**: Memory usage percentage (0-100)
- **swap**: Swap usage percentage (0-100)
- **running_vm**: Count of running virtual machines (integer)

### Supported Hosts
Query `/collector/instances` to get the list of available hosts/instances.

---

## Usage Examples

### Python Example

```python
import requests
import pandas as pd

BASE_URL = "http://localhost:8000/api/v1"

# Export metrics as DataFrame
response = requests.post(
    f"{BASE_URL}/export/dataframe",
    params={"count": 500}
)

data = response.json()
df = pd.DataFrame(data["data"])

print(f"Exported {len(df)} metrics")
print(df.head())
```

### Bash Example

```bash
# Collect metrics from specific instance
curl -X POST "http://localhost:8000/api/v1/collector/instance/compute1?start_minutes_ago=30"

# Export as DataFrame
curl -X POST "http://localhost:8000/api/v1/export/dataframe?count=200" | jq '.data | length'

# Get stream info
curl -X GET "http://localhost:8000/api/v1/health/stream-info" | jq '.length'
```

---

## Rate Limiting

Currently no rate limiting is implemented. Future versions will include rate limiting for production deployments.

---

## Versioning

Current API Version: **v1**

All endpoints are prefixed with `/api/v1`. Future breaking changes will use new versions (e.g., `/api/v2`).

---

## Response Format

All API responses follow this standard format:

**Success Response:**
```json
{
  "success": true,
  "data": { /* endpoint-specific data */ },
  "timestamp": "2024-03-29T10:30:45.123456"
}
```

**Error Response:**
```json
{
  "detail": "Error description"
}
```

---

## Changelog

### Version 1.0.0 (2024-03-29)
- Initial API release
- Collector endpoints for metrics collection
- Export endpoints supporting pandas DataFrame
- Query endpoints for metrics retrieval
- Health check endpoints
- Stream statistics endpoints

---

## Support

For API issues or questions, please check:
1. Application logs in `/var/log/openstackdrs/` (if available)
2. Redis connection status
3. Prometheus connectivity

---

## Next Steps

- Integrate exported DataFrames with ML models
- Perform data analysis and visualization
- Use data for predictive analytics
- Export for external systems integration
