"""API endpoints for manual approval of pending migration plans."""
from __future__ import annotations

import json
from typing import Any

import grpc
from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ApproveRequest
from app.grpc import engine_pb2
from app.clients.rpc_clients import engine_client, grpc_status_to_http_status
from app.utils.logger import get_logger

router = APIRouter(tags=["plan"])
logger = get_logger(__name__)


@router.get("/plan/pending")
async def get_pending_plan() -> dict[str, Any]:
    """Return the current pending migration plan (if any)."""
    try:
        async with engine_client() as stub:
            response = await stub.GetPendingPlan(
                engine_pb2.GetPendingPlanRequest(),
                timeout=10,
            )
    except grpc.aio.AioRpcError as exc:
        raise HTTPException(
            status_code=grpc_status_to_http_status(exc.code()),
            detail=exc.details() or "Engine gRPC request failed",
        ) from exc

    if not response.pending:
        return {"pending": False, "plan": None}
    return {"pending": True, "plan": json.loads(response.plan_json)}


@router.delete("/plan/pending", status_code=status.HTTP_200_OK)
async def reject_pending_plan() -> dict[str, Any]:
    """Discard the current pending plan without executing it."""
    try:
        async with engine_client() as stub:
            response = await stub.RejectPendingPlan(
                engine_pb2.RejectPendingPlanRequest(),
                timeout=10,
            )
    except grpc.aio.AioRpcError as exc:
        raise HTTPException(
            status_code=grpc_status_to_http_status(exc.code()),
            detail=exc.details() or "Engine gRPC request failed",
        ) from exc

    logger.info("Pending plan rejected by operator via gRPC (plan_id=%s)", response.plan_id)
    return {"rejected": response.rejected, "plan_id": response.plan_id}


@router.post("/plan/approve", status_code=status.HTTP_202_ACCEPTED)
async def approve_pending_plan(body: ApproveRequest) -> dict[str, Any]:
    """
    Approve and execute the current pending plan.

    - Leave `candidate_ids` empty to execute **all** candidates.
    - Pass specific VM IDs to execute only a subset.
    """
    try:
        async with engine_client() as stub:
            response = await stub.ApprovePendingPlan(
                engine_pb2.ApprovePendingPlanRequest(candidate_ids=body.candidate_ids),
                timeout=300,
            )
    except grpc.aio.AioRpcError as exc:
        raise HTTPException(
            status_code=grpc_status_to_http_status(exc.code()),
            detail=exc.details() or "Engine gRPC request failed",
        ) from exc

    if not response.approved:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=response.error or response.status or "Pending plan approval failed",
        )

    results = json.loads(response.results_json) if response.results_json else []

    return {
        "approved": True,
        "plan_id": response.plan_id,
        "executed": response.executed,
        "results": results,
    }
