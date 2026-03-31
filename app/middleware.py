"""
Middleware setup for FastAPI application.
Includes CORS, compression, error handling, and logging.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import time
from typing import Callable
from datetime import datetime

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI):
    """Configure middleware: GZIP, CORS, logging, error handlers."""
    
    app.add_middleware(
        GZipMiddleware,
        minimum_size=500,
        compresslevel=6
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable):
        """Log HTTP requests/responses with timing."""
        start_time = time.time()
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "client": request.client.host if request.client else "unknown",
                }
            }
        )
        
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(f"Request failed: {str(exc)}")
            raise
        process_time = time.time() - start_time
        
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(
            f"← {request.method} {request.url.path} {response.status_code} ({process_time:.3f}s)",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time,
                }
            }
        )
        
        return response
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": exc.errors(),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Custom handler for HTTP exceptions.
        Returns structured error response.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """
        Generic exception handler for unexpected errors.
        """
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path,
            }
        )

    logger.info("Middleware configured successfully")
