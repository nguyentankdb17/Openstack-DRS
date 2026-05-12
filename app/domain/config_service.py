from __future__ import annotations

from typing import Any

from app import config


ALLOWED_RUNTIME_CONFIG_KEYS: set[str] = {
	"PROMETHEUS_BASE_URL",
	"PROMETHEUS_USERNAME",
	"PROMETHEUS_PASSWORD",
	"PROMETHEUS_TIMEOUT_SECONDS",
	"SCHEDULER_INTERVAL_MINUTES",
	"SCHEDULER_START_MODE",
	"SCHEDULER_STARTUP_DELAY_SECONDS",
	"CHECK_EVENT_LOOKBACK_MINUTES",
	"HISTORY_LOOKBACK_MINUTES",
	"PREDICTION_HORIZON_MINUTES",
	"PREDICTION_STEP_SECONDS",
	"CLUSTER_IMBALANCE_THRESHOLD",
	"CPU_WEIGHT",
	"RAM_WEIGHT",
	"SWAP_WEIGHT",
	"MIGRATION_TARGET_MAX_CPU_USAGE",
	"MIGRATION_TARGET_MAX_RAM_USAGE",
	"MIGRATION_TARGET_MAX_SWAP_USAGE",
	"MIGRATION_MIN_NET_BENEFIT",
	"MAX_MIGRATIONS_PER_CYCLE",
	"CPU_ALLOCATION_RATIO",
	"RAM_ALLOCATION_RATIO",
	"DECISION_POLICY",
	"RL_MODEL_PATH",
	"RL_REPLAY_BUFFER_SIZE",
	"RL_BATCH_SIZE",
	"RL_MIN_REPLAY_SIZE",
	"RL_LEARNING_RATE",
	"RL_HIDDEN_DIMS",
	"RL_DEVICE",
	"RL_GAMMA",
	"RL_EPSILON_START",
	"RL_EPSILON_END",
	"RL_EPSILON_DECAY",
	"RL_TRAIN_STEPS_PER_UPDATE",
	"RL_TARGET_UPDATE_INTERVAL",
	"RL_TARGET_SOFT_UPDATE_TAU",
	"RL_TRAINING_EPISODES_PER_STEP",
	"RL_PERSIST_MODEL",
	"CHRONOS_MODEL_NAME",
	"CHRONOS_DEVICE",
	"HOST_CPU_QUERY",
	"HOST_MEM_QUERY",
	"HOST_SWAP_QUERY",
	"HOST_RUNNING_VM_QUERY",
	"HOST_TOTAL_CPU_QUERY",
	"HOST_TOTAL_MEM_QUERY",
	"HOST_TOTAL_SWAP_QUERY",
	"VM_CPU_QUERY",
	"VM_MEM_QUERY",
}


def get_runtime_config() -> dict[str, Any]:
	return {key: getattr(config, key) for key in sorted(ALLOWED_RUNTIME_CONFIG_KEYS)}


def update_runtime_config(updates: dict[str, Any]) -> dict[str, Any]:
	if not updates:
		return {}

	applied: dict[str, Any] = {}
	for key, raw_value in updates.items():
		if key not in ALLOWED_RUNTIME_CONFIG_KEYS:
			raise ValueError(f"Unsupported config key: {key}")

		if not hasattr(config, key):
			raise ValueError(f"Unknown config key: {key}")

		current_value = getattr(config, key)
		new_value = _coerce_value(raw_value, current_value)
		setattr(config, key, new_value)
		applied[key] = new_value

	return applied


def _coerce_value(raw_value: Any, current_value: Any) -> Any:
	if isinstance(current_value, bool):
		if isinstance(raw_value, bool):
			return raw_value
		if isinstance(raw_value, str):
			normalized = raw_value.strip().lower()
			if normalized in {"true", "1", "yes", "on"}:
				return True
			if normalized in {"false", "0", "no", "off"}:
				return False
		raise ValueError(f"Invalid boolean value: {raw_value}")

	if isinstance(current_value, int):
		if isinstance(raw_value, bool):
			raise ValueError(f"Invalid integer value: {raw_value}")
		try:
			return int(raw_value)
		except (TypeError, ValueError) as exc:
			raise ValueError(f"Invalid integer value: {raw_value}") from exc

	if isinstance(current_value, float):
		try:
			return float(raw_value)
		except (TypeError, ValueError) as exc:
			raise ValueError(f"Invalid float value: {raw_value}") from exc

	if isinstance(current_value, str):
		return str(raw_value)

	if isinstance(current_value, tuple):
		if isinstance(raw_value, str):
			parts = [part.strip() for part in raw_value.split(",") if part.strip()]
			try:
				return tuple(int(part) for part in parts if int(part) > 0)
			except (TypeError, ValueError) as exc:
				raise ValueError(f"Invalid tuple value: {raw_value}") from exc
		if isinstance(raw_value, list):
			try:
				return tuple(int(part) for part in raw_value if int(part) > 0)
			except (TypeError, ValueError) as exc:
				raise ValueError(f"Invalid tuple value: {raw_value}") from exc
		raise ValueError(f"Invalid tuple value: {raw_value}")

	raise ValueError("Unsupported config value type")
