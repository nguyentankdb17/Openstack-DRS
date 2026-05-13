from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg2.extras import Json

from app.db.postgres import get_connection
from app.models.schemas import (
	ConstraintRecord,
	ExcludeConstraintUpsert,
	ExcludeRule,
	VMAffinityRule,
	VMHostAffinityRule,
	VMVMConstraintUpsert,
	VMHostConstraintUpsert,
)


def _record_from_row(row: tuple[Any, ...]) -> ConstraintRecord:
	constraint_type = str(row[2])
	forbidden_hosts = list(row[7] or [])
	return ConstraintRecord(
		rule_name=str(row[0]),
		description=str(row[1]) if row[1] is not None else "",
		constraint_type=constraint_type,
		vm_id=str(row[3]) if row[3] is not None else None,
		policy=str(row[4]) if row[4] is not None else None,
		vm_ids=list(row[5] or []),
		allowed_hosts=list(row[6] or []),
		forbidden_hosts=forbidden_hosts,
		host_ids=forbidden_hosts if constraint_type == "exclude" else [],
		is_enabled=bool(row[8]),
		created_at=row[9] if isinstance(row[9], datetime) else datetime.now(),
		updated_at=row[10] if isinstance(row[10], datetime) else datetime.now(),
	)


def list_constraints() -> list[ConstraintRecord]:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					created_at,
					updated_at
				FROM drs_constraints
				ORDER BY created_at DESC
				"""
			)
			rows = cursor.fetchall()
	return [_record_from_row(row) for row in rows]


def get_constraint(rule_name: str) -> ConstraintRecord | None:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					created_at,
					updated_at
				FROM drs_constraints
				WHERE rule_name = %s
				""",
				(rule_name,),
			)
			row = cursor.fetchone()
	if row is None:
		return None
	return _record_from_row(row)


def upsert_vm_host_constraint(payload: VMHostConstraintUpsert) -> ConstraintRecord:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				INSERT INTO drs_constraints (
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					updated_at
				)
				VALUES (%s, %s, 'vm_host', %s, NULL, '[]'::jsonb, %s::jsonb, %s::jsonb, %s, NOW())
				ON CONFLICT (rule_name)
				DO UPDATE SET
					description = EXCLUDED.description,
					constraint_type = 'vm_host',
					vm_id = EXCLUDED.vm_id,
					policy = NULL,
					vm_ids = '[]'::jsonb,
					allowed_hosts = EXCLUDED.allowed_hosts,
					forbidden_hosts = EXCLUDED.forbidden_hosts,
					is_enabled = EXCLUDED.is_enabled,
					updated_at = NOW()
				RETURNING
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					created_at,
					updated_at
				""",
				(
					payload.rule_name,
					payload.description,
					payload.vm_id,
					Json(payload.allowed_hosts),
					Json(payload.forbidden_hosts),
					payload.is_enabled,
				),
			)
			row = cursor.fetchone()
		connection.commit()

	return _record_from_row(row)


def upsert_vm_vm_constraint(payload: VMVMConstraintUpsert) -> ConstraintRecord:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				INSERT INTO drs_constraints (
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					updated_at
				)
				VALUES (%s, %s, 'vm_vm', NULL, %s, %s::jsonb, '[]'::jsonb, '[]'::jsonb, %s, NOW())
				ON CONFLICT (rule_name)
				DO UPDATE SET
					description = EXCLUDED.description,
					constraint_type = 'vm_vm',
					vm_id = NULL,
					policy = EXCLUDED.policy,
					vm_ids = EXCLUDED.vm_ids,
					allowed_hosts = '[]'::jsonb,
					forbidden_hosts = '[]'::jsonb,
					is_enabled = EXCLUDED.is_enabled,
					updated_at = NOW()
				RETURNING
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					created_at,
					updated_at
				""",
				(
					payload.rule_name,
					payload.description,
					payload.policy,
					Json(payload.vm_ids),
					payload.is_enabled,
				),
			)
			row = cursor.fetchone()
		connection.commit()

	return _record_from_row(row)


def upsert_exclude_constraint(payload: ExcludeConstraintUpsert) -> ConstraintRecord:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				INSERT INTO drs_constraints (
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					updated_at
				)
				VALUES (%s, %s, 'exclude', NULL, NULL, %s::jsonb, '[]'::jsonb, %s::jsonb, %s, NOW())
				ON CONFLICT (rule_name)
				DO UPDATE SET
					description = EXCLUDED.description,
					constraint_type = 'exclude',
					vm_id = NULL,
					policy = NULL,
					vm_ids = EXCLUDED.vm_ids,
					allowed_hosts = '[]'::jsonb,
					forbidden_hosts = EXCLUDED.forbidden_hosts,
					is_enabled = EXCLUDED.is_enabled,
					updated_at = NOW()
				RETURNING
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					created_at,
					updated_at
				""",
				(
					payload.rule_name,
					payload.description,
					Json(payload.vm_ids),
					Json(payload.host_ids),
					payload.is_enabled,
				),
			)
			row = cursor.fetchone()
		connection.commit()

	return _record_from_row(row)


def delete_constraint(rule_name: str) -> bool:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute("DELETE FROM drs_constraints WHERE rule_name = %s", (rule_name,))
			deleted = cursor.rowcount
		connection.commit()
	return deleted > 0


def set_constraint_enabled(rule_name: str, enabled: bool) -> ConstraintRecord | None:
	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				UPDATE drs_constraints
				SET is_enabled = %s,
					updated_at = NOW()
				WHERE rule_name = %s
				RETURNING
					rule_name,
					description,
					constraint_type,
					vm_id,
					policy,
					vm_ids,
					allowed_hosts,
					forbidden_hosts,
					is_enabled,
					created_at,
					updated_at
				""",
				(enabled, rule_name),
			)
			row = cursor.fetchone()
		connection.commit()

	if row is None:
		return None
	return _record_from_row(row)


def load_active_affinity_rules() -> tuple[list[VMHostAffinityRule], list[VMAffinityRule]]:
	vm_host_rules, vm_vm_rules, _ = load_active_constraint_rules()
	return vm_host_rules, vm_vm_rules


def load_active_constraint_rules() -> tuple[list[VMHostAffinityRule], list[VMAffinityRule], list[ExcludeRule]]:
	vm_host_rules: list[VMHostAffinityRule] = []
	vm_vm_rules: list[VMAffinityRule] = []
	exclude_rules: list[ExcludeRule] = []

	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				SELECT rule_name, description, constraint_type, vm_id, policy, vm_ids, allowed_hosts, forbidden_hosts
				FROM drs_constraints
				WHERE is_enabled = TRUE
				"""
			)
			rows = cursor.fetchall()

	for row in rows:
		rule_name = str(row[0])
		constraint_type = str(row[2])
		vm_id = str(row[3]) if row[3] is not None else None
		policy = str(row[4]) if row[4] is not None else None
		vm_ids = list(row[5] or [])
		allowed_hosts = list(row[6] or [])
		forbidden_hosts = list(row[7] or [])

		if constraint_type == "vm_host" and vm_id:
			vm_host_rules.append(
				VMHostAffinityRule(
					rule_id=rule_name,
					vm_id=vm_id,
					allowed_hosts=allowed_hosts,
					forbidden_hosts=forbidden_hosts,
				)
			)
			continue

		if constraint_type == "vm_vm" and policy:
			vm_vm_rules.append(
				VMAffinityRule(
					rule_id=rule_name,
					policy=policy,
					vm_ids=vm_ids,
				)
			)
			continue

		if constraint_type == "exclude":
			exclude_rules.append(
				ExcludeRule(
					rule_id=rule_name,
					vm_ids=vm_ids,
					host_ids=forbidden_hosts,
				)
			)

	return vm_host_rules, vm_vm_rules, exclude_rules
