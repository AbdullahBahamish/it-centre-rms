import logging
import time
from dataclasses import dataclass
from typing import Any

from django.db import OperationalError


security_logger = logging.getLogger("security")


@dataclass(frozen=True)
class ServiceResult:
    success: bool
    error: str | None = None
    payload: Any = None
    status_code: int = 403


def log_security_event(*, action, result, actor=None, target=None, reason=None, **extra):
    try:
        security_logger.info(
            "security_event",
            extra={
                "security_event": {
                    "action": action,
                    "actor": getattr(actor, "pk", actor),
                    "target": getattr(target, "pk", target),
                    "result": result,
                    "reason": reason,
                    **extra,
                }
            },
        )
    except Exception:
        pass


def log_security_failure(*, action, actor=None, target=None, reason=None):
    try:
        security_logger.exception(
            "security_failure",
            extra={
                "security_event": {
                    "action": action,
                    "actor": getattr(actor, "pk", actor),
                    "target": getattr(target, "pk", target),
                    "result": "denied",
                    "reason": reason,
                }
            },
        )
    except Exception:
        pass


def with_retry(fn, *, retries=3, delay_seconds=0.05):
    for attempt in range(retries):
        try:
            return fn()
        except OperationalError:
            if attempt == retries - 1:
                return ServiceResult(success=False, error="deadlock", status_code=409)
            time.sleep(delay_seconds)
