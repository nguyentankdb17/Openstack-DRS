# OpenStackDRS

OpenStackDRS is a Distributed Resource Scheduler for OpenStack. The system collects host and VM metrics, evaluates current and predicted cluster imbalance, builds migration plans, and optionally executes OpenStack live migrations.

The current architecture is split into:

- A REST API gateway for dashboard/operator access.
- gRPC runtime services for collector, analytics, scoring, and engine.
- Shared domain modules under `app/domain`.
- Generated protobuf clients/stubs under `app/grpc`.

## Architecture Overview

```mermaid
flowchart TD
    USER[Dashboard / Operator] --> API[REST API Gateway<br/>app.main or services.api.main<br/>HTTP :8000]
    ALERT[Prometheus Alertmanager] --> API

    API -->|EngineServiceStub| ENGINE[drs-engine<br/>services.engine.server<br/>gRPC :50054]

    ENGINE -->|CollectEvents| COLLECTOR[drs-collector<br/>services.collector.server<br/>gRPC :50051]
    ENGINE -->|CollectMetrics| COLLECTOR
    ENGINE -->|ScoreCluster| SCORING[drs-scoring<br/>services.scoring.server<br/>gRPC :50053]
    ENGINE -->|Predict| ANALYTICS[drs-analytics<br/>services.analytics.server<br/>gRPC :50052]

    COLLECTOR --> PROM[Prometheus]
    COLLECTOR --> NOVA_DB[Nova DB]
    COLLECTOR --> OPENSTACK[OpenStack API]
    SCORING --> PROM
    ANALYTICS --> PROM

    ENGINE --> DOMAIN[app.domain<br/>decision cycle, prediction, constraints,<br/>pending plan, cycle history]
    DOMAIN --> PLANNER[MigrationPlanner]
    DOMAIN --> EXECUTOR[MigrationExecutor]
    DOMAIN --> POSTGRES[PostgreSQL]
    EXECUTOR --> OPENSTACK
```

## Basic Runtime Flow

1. Dashboard/operator calls the REST API, or Alertmanager sends a webhook.
2. REST API uses `app.clients.rpc_clients.engine_client()` to call `drs-engine` through gRPC.
3. `drs-engine` runs `app.domain.engine_cycle.run_decision_cycle()`.
4. Engine asks `drs-collector` to check recent VM events and collect fresh metrics.
5. Engine asks `drs-scoring` to compute current cluster imbalance.
6. If current imbalance is below threshold, engine asks `drs-analytics` for prediction.
7. If current or predicted imbalance exceeds threshold, engine builds a migration plan.
8. If `APPROVAL_MODE=manual`, the plan is stored as pending and must be approved through REST API.
9. If `APPROVAL_MODE=auto`, engine executes selected migrations through OpenStack.
10. Cycle results are recorded into PostgreSQL cycle history.

## Project Structure

```text
OpenstackDRS/
├── app/
│   ├── api/                    # FastAPI routers exposed by the REST API gateway
│   │   ├── monitor.py           # Latest decision endpoint
│   │   ├── plan.py              # Pending plan approve/reject endpoints
│   │   ├── webhook.py           # Alertmanager webhook endpoint
│   │   ├── constraints.py       # Constraint CRUD endpoints
│   │   ├── cycle_history.py     # Decision cycle history endpoint
│   │   ├── configuration.py     # Runtime config and scheduler control endpoints
│   │   └── inventory.py         # Inventory test/debug endpoint
│   ├── clients/                # Client adapters to external/internal services
│   │   └── rpc_clients.py       # gRPC client helper for EngineService
│   ├── collector/              # Prometheus and OpenStack/Nova event collectors
│   ├── core/                   # Settings and constants
│   ├── db/                     # PostgreSQL initialization and connection helpers
│   ├── decision/               # Placement constraints, datasources, migration planner
│   ├── domain/                 # Shared business logic
│   │   ├── engine_cycle.py      # Engine orchestration / DRS decision cycle
│   │   ├── engine_approval.py   # Pending plan approve/reject/execute logic
│   │   ├── decision_service.py  # Decision builders and latest decision state
│   │   ├── metrics_service.py   # Metric collection wrappers
│   │   ├── prediction_service.py # Chronos prediction wrappers
│   │   ├── constraint_service.py # Constraint persistence and loading
│   │   ├── cycle_history_service.py
│   │   ├── pending_plan_store.py
│   │   └── config_service.py
│   ├── executor/               # OpenStack migration execution
│   ├── grpc/                   # Generated protobuf Python files
│   ├── models/                 # Pydantic schemas
│   ├── scheduler/              # API-side scheduler control helpers
│   ├── scoring/                # Imbalance scoring functions
│   ├── utils/                  # Logging utilities
│   └── main.py                 # Local REST API entrypoint
├── services/
│   ├── api/                    # Docker/runtime REST API entrypoint
│   ├── collector/              # gRPC collector runtime
│   ├── analytics/              # gRPC analytics/runtime prediction service
│   ├── scoring/                # gRPC scoring runtime
│   └── engine/                 # gRPC engine runtime
├── protos/                     # Protobuf service definitions
├── scripts/
│   └── gen_protos.sh           # Generate app/grpc/*_pb2.py stubs
├── dashboard/                  # Next.js dashboard
├── docs/
│   └── system-grpc-flow.md     # Detailed Mermaid system flow
├── docker-compose.yml
└── requirements.txt
```

## Component Responsibilities

| Component | Runtime | Responsibility |
|---|---:|---|
| REST API Gateway | HTTP `:8000` | Public API for dashboard/operators. Delegates decision and plan operations to engine gRPC. |
| `drs-engine` | gRPC `:50054` | Orchestrates DRS cycle, coordinates collector/scoring/analytics, builds/stores/executes plans. |
| `drs-collector` | gRPC `:50051` | Collects Prometheus metrics and checks recent OpenStack/Nova VM events. |
| `drs-analytics` | gRPC `:50052` | Builds Chronos inputs and predicts next-window host metrics. |
| `drs-scoring` | gRPC `:50053` | Computes cluster/host imbalance scores. |
| PostgreSQL | `:5432` | Stores constraints and cycle history. |
| Dashboard | HTTP `:3000` | Operator UI. |

## REST API

Base URL:

```text
http://localhost:8000/api/v1
```

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/monitor/latest` | Return latest engine decision. Calls `EngineService.GetLatestDecision`. |
| `GET` | `/plan/pending` | Return current pending migration plan. Calls `EngineService.GetPendingPlan`. |
| `DELETE` | `/plan/pending` | Reject and clear pending plan. Calls `EngineService.RejectPendingPlan`. |
| `POST` | `/plan/approve` | Approve pending plan and execute selected candidates. Calls `EngineService.ApprovePendingPlan`. |
| `POST` | `/webhook/alertmanager` | Receive Alertmanager firing alerts and trigger `EngineService.ComputeDecision`. |
| `GET` | `/constraints` | List migration constraints. |
| `GET` | `/constraints/{rule_name}` | Get one constraint. |
| `POST` | `/constraints/vm-host` | Create/update VM-host constraint. |
| `POST` | `/constraints/vm-vm` | Create/update VM-VM constraint. |
| `PUT` | `/constraints/vm-host/{rule_name}` | Replace VM-host constraint. |
| `PUT` | `/constraints/vm-vm/{rule_name}` | Replace VM-VM constraint. |
| `PATCH` | `/constraints/{rule_name}/enable?enabled=true` | Enable/disable constraint. |
| `DELETE` | `/constraints/{rule_name}` | Delete constraint. |
| `GET` | `/cycles/history?limit=50` | List cycle history records. |
| `GET` | `/admin/config` | Read runtime configuration. |
| `PATCH` | `/admin/config` | Update runtime configuration. |
| `GET` | `/admin/jobs/monitor` | Read API scheduler control status. |
| `POST` | `/admin/jobs/monitor/pause` | Pause API scheduler helper job. |
| `POST` | `/admin/jobs/monitor/restart?run_now=false` | Restart API scheduler helper job. |
| `GET` | `/inventory/test` | Debug endpoint for merged OpenStack/Prometheus inventory. |

Health check for the Docker API runtime:

```text
GET http://localhost:8000/health
```

### REST Examples

```bash
curl http://localhost:8000/api/v1/monitor/latest
curl http://localhost:8000/api/v1/plan/pending
curl -X POST http://localhost:8000/api/v1/plan/approve \
  -H "Content-Type: application/json" \
  -d '{"candidate_ids":[]}'
curl http://localhost:8000/api/v1/cycles/history?limit=20
```

## gRPC API

Definitions are in `protos/*.proto`; generated Python files are in `app/grpc/`.

| Service | RPC | Purpose |
|---|---|---|
| `CollectorService` | `CollectMetrics` | Collect current Prometheus host metrics. |
| `CollectorService` | `CollectEvents` | Check recent Nova/OpenStack VM events. |
| `AnalyticsService` | `Predict` | Predict next-window values for host/metric. |
| `AnalyticsService` | `BuildFeatures` | Build Chronos input features. |
| `ScoringService` | `ScoreCluster` | Compute cluster imbalance. |
| `ScoringService` | `ScoreHost` | Compute host-level score. |
| `EngineService` | `ComputeDecision` | Trigger a full DRS decision cycle. |
| `EngineService` | `ExecuteMigration` | Execute one pending migration by VM/migration id. |
| `EngineService` | `GetLatestDecision` | Return latest decision as JSON. |
| `EngineService` | `GetPendingPlan` | Return pending plan as JSON. |
| `EngineService` | `RejectPendingPlan` | Clear pending plan. |
| `EngineService` | `ApprovePendingPlan` | Approve and execute pending plan candidates. |

Regenerate gRPC stubs after editing proto files:

```bash
bash scripts/gen_protos.sh
```

## Configuration

Create `.env` from `.env.example` and set the values for your OpenStack, Prometheus, PostgreSQL, and scheduler environment.

Important variables:

```env
APP_ENVIRONMENT=development
APP_LOG_LEVEL=DEBUG

DATABASE_URL=postgresql://drs_user:drs_password@localhost/drs_db

PROMETHEUS_BASE_URL=http://localhost:9090
PROMETHEUS_USERNAME=admin
PROMETHEUS_PASSWORD=admin

OPENSTACK_AUTH_URL=http://openstack.example:5000/v3
OPENSTACK_USERNAME=admin
OPENSTACK_PASSWORD=secret
OPENSTACK_PROJECT_NAME=admin
OPENSTACK_REGION_NAME=RegionOne

NOVA_DB_HOST=127.0.0.1
NOVA_DB_PORT=3306
NOVA_DB_NAME=nova
NOVA_DB_USER=nova
NOVA_DB_PASSWORD=secret

SCHEDULER_INTERVAL_MINUTES=10
SCHEDULER_START_MODE=lazy
CHECK_EVENT_LOOKBACK_MINUTES=5
HISTORY_LOOKBACK_MINUTES=1440
PREDICTION_HORIZON_MINUTES=10
PREDICTION_STEP_SECONDS=15

CLUSTER_IMBALANCE_THRESHOLD=0.25
MAX_MIGRATIONS_PER_CYCLE=1
APPROVAL_MODE=manual

DRS_COLLECTOR_HOST=localhost
DRS_COLLECTOR_PORT=50051
DRS_ANALYTICS_HOST=localhost
DRS_ANALYTICS_PORT=50052
DRS_SCORING_HOST=localhost
DRS_SCORING_PORT=50053
DRS_ENGINE_HOST=localhost
DRS_ENGINE_PORT=50054
```

## Running Locally

Install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Generate protobuf stubs:

```bash
bash scripts/gen_protos.sh
```

Start infrastructure services such as PostgreSQL and any required OpenStack/Prometheus endpoints, then run each service in separate terminals:

```bash
python -m services.collector.server
python -m services.analytics.server
python -m services.scoring.server
python -m services.engine.server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Dashboard, if needed:

```bash
cd dashboard
pnpm install
pnpm dev
```

## Running With Docker Compose

```bash
bash scripts/gen_protos.sh
docker compose up --build
```

Main ports:

| Service | Port |
|---|---:|
| REST API | `8000` |
| Dashboard | `3000` |
| PostgreSQL | `5432` |
| Redis | `6379` |
| Collector gRPC | `50051` internal |
| Analytics gRPC | `50052` internal |
| Scoring gRPC | `50053` internal |
| Engine gRPC | `50054` internal |

## Development Notes

- Treat `app/grpc/*_pb2.py` and `app/grpc/*_pb2_grpc.py` as generated files.
- Put business logic in `app/domain`.
- Put network/client adapters in `app/clients`.
- Keep `services/*/server.py` thin: gRPC runtime and transport concerns only.
- Keep public REST behavior in `app/api`.
- `pending_plan_store` is currently in-memory. For multi-replica production deployments, move pending plans to PostgreSQL or Redis.

## Troubleshooting

### gRPC import errors

Regenerate protobuf stubs:

```bash
bash scripts/gen_protos.sh
```

### Engine cannot reach backend services

Check `DRS_COLLECTOR_*`, `DRS_ANALYTICS_*`, `DRS_SCORING_*`, and `DRS_ENGINE_*` variables. In Docker Compose, use service names such as `drs-collector`; in local terminal runs, use `localhost`.

### `CollectEvents` deadline exceeded

`CollectEvents` checks Nova DB/OpenStack events. Verify Nova DB credentials, network access, and OpenStack API latency.

### No migration plan is produced

Check:

- Prometheus queries return host and VM metrics.
- OpenStack inventory is available.
- Constraints do not block all candidates.
- `CLUSTER_IMBALANCE_THRESHOLD` is appropriate for your environment.

## License

MIT License.
