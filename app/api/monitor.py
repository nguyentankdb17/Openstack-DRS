import json

from fastapi import APIRouter
import grpc

from app.grpc import engine_pb2
from app.models.schemas import MonitorResponse
from app.clients.rpc_clients import engine_client, grpc_status_to_http_status
from fastapi import HTTPException


router = APIRouter(tags=["monitor"])


@router.get("/monitor/latest", response_model=MonitorResponse)
async def latest_monitor_decision() -> MonitorResponse:
    try:
        async with engine_client() as stub:
            response = await stub.GetLatestDecision(
                engine_pb2.GetLatestDecisionRequest(),
                timeout=10,
            )
    except grpc.aio.AioRpcError as exc:
        raise HTTPException(
            status_code=grpc_status_to_http_status(exc.code()),
            detail=exc.details() or "Engine gRPC request failed",
        ) from exc

    if not response.decision_json:
        raise HTTPException(status_code=502, detail="Engine returned an empty decision")
    return MonitorResponse(data=json.loads(response.decision_json))
