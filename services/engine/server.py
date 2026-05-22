"""
drs-engine - gRPC :50054

Thin gRPC runtime for the engine service. Decision orchestration and pending-plan
approval live in app.domain so this module stays focused on transport and
lifecycle concerns.
"""
from __future__ import annotations

import asyncio
import os
import sys

import grpc

from app.core import settings
from app.domain.engine_approval import (
	NoMatchingCandidateError,
	PendingPlanNotFoundError,
	approve_pending_plan,
	execute_migration,
	latest_decision_json,
	pending_plan_json,
	reject_pending_plan,
)
from app.domain.engine_cycle import run_decision_cycle
from app.grpc import engine_pb2, engine_pb2_grpc
from app.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


class EngineServicer(engine_pb2_grpc.EngineServiceServicer):
	async def ComputeDecision(
		self,
		request: engine_pb2.ComputeDecisionRequest,
		context: grpc.ServicerContext,
	) -> engine_pb2.ComputeDecisionResponse:
		try:
			trigger_source = request.trigger_source or "rpc"
			logger.info("[engine] ComputeDecision requested: trigger_source=%s", trigger_source)
			result = await run_decision_cycle(trigger_source=trigger_source)
			return engine_pb2.ComputeDecisionResponse(
				status=result.get("status", "unknown"),
				plan_id=str(result.get("plan_id", "")),
				planned=int(result.get("planned", result.get("candidates", 0)) or 0),
				executed=int(result.get("executed", 0) or 0),
				error=str(result.get("error", "")),
			)
		except Exception as exc:  
			logger.exception("ComputeDecision error: %s", exc)
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INTERNAL)
			return engine_pb2.ComputeDecisionResponse(status="error", error=str(exc))

	async def ExecuteMigration(
		self,
		request: engine_pb2.ExecuteMigrationRequest,
		context: grpc.ServicerContext,
	) -> engine_pb2.ExecuteMigrationResponse:
		try:
			status = await execute_migration(request.migration_id)
			return engine_pb2.ExecuteMigrationResponse(status=status)
		except PendingPlanNotFoundError as exc:
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.NOT_FOUND)
			return engine_pb2.ExecuteMigrationResponse(status="no_pending_plan")
		except Exception as exc:  
			logger.exception("ExecuteMigration error: %s", exc)
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INTERNAL)
			return engine_pb2.ExecuteMigrationResponse(status="error")

	async def GetLatestDecision(
		self,
		request: engine_pb2.GetLatestDecisionRequest,
		context: grpc.ServicerContext,
	) -> engine_pb2.GetLatestDecisionResponse:
		try:
			return engine_pb2.GetLatestDecisionResponse(decision_json=latest_decision_json())
		except Exception as exc:  
			logger.exception("GetLatestDecision error: %s", exc)
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INTERNAL)
			return engine_pb2.GetLatestDecisionResponse(decision_json="")

	async def GetPendingPlan(
		self,
		request: engine_pb2.GetPendingPlanRequest,
		context: grpc.ServicerContext,
	) -> engine_pb2.GetPendingPlanResponse:
		try:
			has_pending, plan_json = pending_plan_json()
			return engine_pb2.GetPendingPlanResponse(pending=has_pending, plan_json=plan_json)
		except Exception as exc:  
			logger.exception("GetPendingPlan error: %s", exc)
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INTERNAL)
			return engine_pb2.GetPendingPlanResponse(pending=False, plan_json="")

	async def RejectPendingPlan(
		self,
		request: engine_pb2.RejectPendingPlanRequest,
		context: grpc.ServicerContext,
	) -> engine_pb2.RejectPendingPlanResponse:
		try:
			rejected, plan_id, status = reject_pending_plan()
			return engine_pb2.RejectPendingPlanResponse(
				rejected=rejected,
				plan_id=plan_id,
				status=status,
			)
		except PendingPlanNotFoundError as exc:
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.NOT_FOUND)
			return engine_pb2.RejectPendingPlanResponse(rejected=False, status="no_pending_plan")
		except Exception as exc:  
			logger.exception("RejectPendingPlan error: %s", exc)
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INTERNAL)
			return engine_pb2.RejectPendingPlanResponse(rejected=False, status="error")

	async def ApprovePendingPlan(
		self,
		request: engine_pb2.ApprovePendingPlanRequest,
		context: grpc.ServicerContext,
	) -> engine_pb2.ApprovePendingPlanResponse:
		try:
			result = await approve_pending_plan(list(request.candidate_ids))
			return engine_pb2.ApprovePendingPlanResponse(
				approved=bool(result["approved"]),
				plan_id=str(result["plan_id"]),
				executed=int(result["executed"]),
				results_json=str(result["results_json"]),
				status=str(result["status"]),
			)
		except PendingPlanNotFoundError as exc:
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.NOT_FOUND)
			return engine_pb2.ApprovePendingPlanResponse(
				approved=False,
				status="no_pending_plan",
				error=str(exc),
			)
		except NoMatchingCandidateError as exc:
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
			return engine_pb2.ApprovePendingPlanResponse(
				approved=False,
				status="no_matching_candidates",
				error=str(exc),
			)
		except Exception as exc:  
			logger.exception("ApprovePendingPlan error: %s", exc)
			context.set_details(str(exc))
			context.set_code(grpc.StatusCode.INTERNAL)
			return engine_pb2.ApprovePendingPlanResponse(
				approved=False,
				status="error",
				error=str(exc),
			)


async def serve(host: str = "0.0.0.0", port: int = 50054) -> None:
	from app.db.postgres import initialize_database

	initialize_database()
	logger.info("[engine] Internal scheduler disabled - waiting for ComputeDecision RPC")

	server = grpc.aio.server(
		options=[
			("grpc.max_send_message_length", 16 * 1024 * 1024),
			("grpc.max_receive_message_length", 16 * 1024 * 1024),
			("grpc.keepalive_time_ms", 30_000),
			("grpc.keepalive_timeout_ms", 10_000),
		]
	)
	engine_pb2_grpc.add_EngineServiceServicer_to_server(EngineServicer(), server)
	listen_addr = f"{host}:{port}"
	server.add_insecure_port(listen_addr)
	logger.info("Starting drs-engine gRPC server on %s", listen_addr)
	await server.start()
	await server.wait_for_termination()


if __name__ == "__main__":
	if __package__ in {None, ""}:
		project_root = os.path.dirname(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		)
		if project_root not in sys.path:
			sys.path.insert(0, project_root)

	setup_logging(settings.app.log_level)
	asyncio.run(serve())
