from datetime import datetime
from pydantic import BaseModel, Field


class HostMetricSnapshot(BaseModel):
	host: str
	cpu: float = Field(ge=0)
	ram: float = Field(ge=0)
	swap: float = Field(ge=0)
	running_vm: float = Field(default=0, ge=0)


class HostDeviation(BaseModel):
	host: str
	score: float


class ClusterDecision(BaseModel):
	status: str
	timestamp: datetime
	current_cluster_imbalance: float | None = None
	predicted_cluster_imbalance: float | None = None
	threshold: float
	recent_events: list[str] = []
	unbalanced_hosts: list[HostDeviation] = []
	details: str | None = None


class MonitorResponse(BaseModel):
	data: ClusterDecision
