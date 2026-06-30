from __future__ import annotations

import logging
from typing import Any

from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler

from .services import InsufficientStock


logger = logging.getLogger(__name__)


def log_exception(exc: Exception, *, level: str = "warning", message: str, **context: Any) -> None:
    log_method = getattr(logger, level, logger.error)
    log_method(message, extra=context, exc_info=(type(exc), exc, exc.__traceback__))


def custom_exception_handler(exc, context):
    view_name = context.get("view").__class__.__name__ if context.get("view") else "unknown"
    request = context.get("request")
    request_path = getattr(request, "path", "unknown")

    if isinstance(exc, InsufficientStock):
        log_exception(
            exc,
            level="warning",
            message="Insufficient stock while processing request",
            view=view_name,
            path=request_path,
        )
    elif not isinstance(exc, APIException):
        log_exception(
            exc,
            level="critical",
            message="Unhandled system exception while processing request",
            view=view_name,
            path=request_path,
        )

    return drf_exception_handler(exc, context)
