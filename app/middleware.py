from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Reload environment variables from .env if running server (not in pytest)
        import sys
        if "pytest" not in sys.modules:
            from dotenv import load_dotenv
            load_dotenv(override=True)

        # Clear contextvars to avoid leakage between requests
        clear_contextvars()

        # Extract x-request-id from headers or generate a new one
        correlation_id = request.headers.get("x-request-id")
        if not correlation_id:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"
        
        # Bind the correlation_id to structlog contextvars
        bind_contextvars(correlation_id=correlation_id)
        
        request.state.correlation_id = correlation_id
        
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        
        # Add correlation_id and processing time to response headers
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(elapsed_ms)
        
        return response
