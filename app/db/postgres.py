from __future__ import annotations

from contextlib import contextmanager

import psycopg2

from app import config
from app.utils.logger import get_logger


logger = get_logger(__name__)


@contextmanager
def get_connection():
	if not config.DATABASE_URL:
		raise RuntimeError("DATABASE_URL is not configured")

	connection = psycopg2.connect(config.DATABASE_URL)
	try:
		yield connection
	finally:
		connection.close()


def initialize_database() -> None:
	if not config.DATABASE_URL:
		logger.warning("DATABASE_URL is not configured; database features are disabled")
		return

	with get_connection() as connection:
		with connection.cursor() as cursor:
			cursor.execute(
				"""
				DO $$
				BEGIN
					IF EXISTS (
						SELECT 1
						FROM information_schema.columns
						WHERE table_name = 'drs_constraints' AND column_name = 'rule_id'
					) AND NOT EXISTS (
						SELECT 1
						FROM information_schema.columns
						WHERE table_name = 'drs_constraints' AND column_name = 'rule_name'
					) THEN
						ALTER TABLE drs_constraints RENAME COLUMN rule_id TO rule_name;
					END IF;
				END $$;
				"""
			)
			cursor.execute(
				"""
				CREATE TABLE IF NOT EXISTS drs_constraints (
					id BIGSERIAL PRIMARY KEY,
					rule_name TEXT NOT NULL UNIQUE,
					description TEXT NOT NULL DEFAULT '',
					constraint_type TEXT NOT NULL CHECK (constraint_type IN ('vm_host', 'vm_vm')),
					vm_id TEXT,
					policy TEXT CHECK (policy IN ('must_together', 'must_separate')),
					vm_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
					allowed_hosts JSONB NOT NULL DEFAULT '[]'::jsonb,
					forbidden_hosts JSONB NOT NULL DEFAULT '[]'::jsonb,
					is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
					updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
				)
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE drs_constraints
				ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''
				"""
			)
			cursor.execute(
				"""
				CREATE INDEX IF NOT EXISTS idx_drs_constraints_type_enabled
				ON drs_constraints (constraint_type, is_enabled)
				"""
			)
			cursor.execute(
				"""
				CREATE TABLE IF NOT EXISTS drs_cycle_history (
					id BIGSERIAL PRIMARY KEY,
					cycle_started_at TIMESTAMPTZ NOT NULL,
					cycle_finished_at TIMESTAMPTZ,
					trigger_source TEXT NOT NULL,
					status TEXT NOT NULL,
					current_cluster_imbalance DOUBLE PRECISION,
					predicted_cluster_imbalance DOUBLE PRECISION,
					threshold DOUBLE PRECISION,
					planned_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
					executed_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
					details TEXT,
					decision_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
					error_message TEXT,
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
				)
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE drs_cycle_history
				ADD COLUMN IF NOT EXISTS planned_candidates JSONB NOT NULL DEFAULT '[]'::jsonb
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE drs_cycle_history
				ADD COLUMN IF NOT EXISTS executed_candidates JSONB NOT NULL DEFAULT '[]'::jsonb
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE drs_cycle_history
				DROP COLUMN IF EXISTS planned_candidates_count
				"""
			)
			cursor.execute(
				"""
				ALTER TABLE drs_cycle_history
				DROP COLUMN IF EXISTS executed_candidates_count
				"""
			)
			cursor.execute(
				"""
				CREATE INDEX IF NOT EXISTS idx_drs_cycle_history_started_at
				ON drs_cycle_history (cycle_started_at DESC)
				"""
			)
		connection.commit()

	logger.info("Database tables ensured: drs_constraints, drs_cycle_history")
