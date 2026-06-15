from __future__ import annotations

import contextvars
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_context.get()


class RequestIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_request_id_logging() -> None:
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [req-id:%(request_id)s] %(name)s: %(message)s")
    request_filter = RequestIdLogFilter()
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=logging.INFO)
    for handler in root_logger.handlers:
        handler.addFilter(request_filter)
        handler.setFormatter(formatter)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            status_code = getattr(locals().get("response", None), "status_code", 500)
            logging.getLogger("app.request").info(
                "%s %s -> %s in %sms [req-id: %s]",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
                request_id,
            )
            request_id_context.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response
