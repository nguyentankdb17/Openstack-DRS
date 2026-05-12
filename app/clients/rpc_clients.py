from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import grpc
from grpc import aio as grpc_aio

from app.grpc.engine_pb2_grpc import EngineServiceStub


def _grpc_target(prefix: str, default_host: str, default_port: int) -> str:
	host = os.getenv(f"{prefix}_HOST", default_host)
	port = int(os.getenv(f"{prefix}_PORT", str(default_port)))
	return f"{host}:{port}"


@asynccontextmanager
async def engine_client() -> AsyncIterator[EngineServiceStub]:
	channel = grpc_aio.insecure_channel(
		_grpc_target("DRS_ENGINE", "localhost", 50054),
		options=[
			("grpc.keepalive_time_ms", 30_000),
			("grpc.keepalive_timeout_ms", 10_000),
		],
	)
	try:
		yield EngineServiceStub(channel)
	finally:
		await channel.close()


def grpc_status_to_http_status(code: grpc.StatusCode) -> int:
	if code == grpc.StatusCode.NOT_FOUND:
		return 404
	if code == grpc.StatusCode.INVALID_ARGUMENT:
		return 422
	if code == grpc.StatusCode.DEADLINE_EXCEEDED:
		return 504
	if code == grpc.StatusCode.UNAVAILABLE:
		return 503
	return 500
