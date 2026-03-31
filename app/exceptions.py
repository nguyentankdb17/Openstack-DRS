"""
Custom exceptions and error handling for OpenstackDRS app.
"""

from fastapi import HTTPException, status


class OpenstackDRSBusinessException(Exception):
    """Base exception for all OpenstackDRS business logic errors"""
    pass


class CollectorNotInitializedError(OpenstackDRSBusinessException):
    """Raised when collector service is not initialized"""
    
    http_exception = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Service not initialized - collector not available"
    )


class MetricsNotFoundError(OpenstackDRSBusinessException):
    """Raised when metrics are not found"""
    
    http_exception = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Metrics not found"
    )


class RedisConnectionError(OpenstackDRSBusinessException):
    """Raised when Redis connection fails"""
    
    http_exception = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Redis service unavailable"
    )


class PrometheusConnectionError(OpenstackDRSBusinessException):
    """Raised when Prometheus connection fails"""
    
    http_exception = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Prometheus service unavailable"
    )


class InvalidQueryError(OpenstackDRSBusinessException):
    """Raised when a query is invalid"""
    
    http_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid query parameters"
    )


class DataExportError(OpenstackDRSBusinessException):
    """Raised when data export fails"""
    
    http_exception = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to export data"
    )


def get_http_exception_for_error(error: Exception) -> HTTPException:
    """
    Convert business exceptions to HTTP exceptions.
    
    Args:
        error: The exception to convert
    
    Returns:
        Corresponding HTTPException
    """
    if isinstance(error, OpenstackDRSBusinessException):
        return error.http_exception
    
    # Default to 500 for unknown errors
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Internal server error: {str(error)}"
    )
