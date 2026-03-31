"""
OpenstackDRS Metrics API - Decentralized Resource Scheduler for OpenStack
A FastAPI application for collecting, storing, and querying Prometheus metrics
via Redis Streams with advanced analytics capabilities.
"""

from .main import app, create_app

__version__ = "1.0.0"
__author__ = "OpenstackDRS Team"

__all__ = ["app", "create_app"]
