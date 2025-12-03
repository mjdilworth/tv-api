"""Reusable FastAPI middleware components."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_logger = logging.getLogger("tv_api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each HTTP request with timing and correlation id."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        client_host = request.client.host if request.client else "-"
        _logger.info(
            "request.start id=%s method=%s path=%s client=%s",
            request_id,
            request.method,
            request.url.path,
            client_host,
        )
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - defensive logging
            duration = time.perf_counter() - start
            _logger.exception(
                "request.error id=%s method=%s path=%s duration_ms=%d",
                request_id,
                request.method,
                request.url.path,
                int(duration * 1000),
            )
            raise exc

        duration = time.perf_counter() - start
        response.headers.setdefault("x-request-id", request_id)
        _logger.info(
            "request.complete id=%s method=%s path=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            int(duration * 1000),
        )
        return response
