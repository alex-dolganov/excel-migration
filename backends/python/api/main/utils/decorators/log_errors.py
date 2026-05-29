import json
import logging
import threading
import traceback
import urllib.request
from datetime import datetime, timezone
from functools import wraps
from http import HTTPStatus

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _extract_portal_member_id(args: tuple) -> str:
    """Safely extract portal member_id from the Django request (args[0])."""
    try:
        request = args[0] if args else None
        if request is None:
            return ""
        account = getattr(request, "bitrix24_account", None)
        if account is not None:
            return str(getattr(account, "member_id", "") or "")
        data = getattr(request, "data", {})
        if isinstance(data, dict):
            return str(data.get("member_id", "") or "")
    except Exception:
        pass
    return ""


def _get_current_trace_id() -> str:
    try:
        from otel import get_current_trace_id
        return get_current_trace_id()
    except Exception:
        return ""


def _send_error_ticket(portal_member_id: str, error_message: str, trace_id: str, endpoint: str, service_name: str) -> None:
    """POST error ticket to the internal proxy (fire-and-forget, runs in daemon thread)."""
    payload = json.dumps({
        "service": service_name,
        "portal_member_id": portal_member_id,
        "error": error_message[:2000],
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as exc:
        logger.debug("Error ticket delivery failed (endpoint=%s): %s", endpoint, exc)


def _send_error_ticket_async(
    portal_member_id: str,
    error_message: str,
    trace_id: str,
    endpoint: str,
    service_name: str,
) -> None:
    t = threading.Thread(
        target=_send_error_ticket,
        args=(portal_member_id, error_message, trace_id, endpoint, service_name),
        daemon=True,
    )
    t.start()


def log_errors(message: str):
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                response = func(*args, **kwargs)
            except Exception as exc:
                from config import config

                portal_member_id = _extract_portal_member_id(args)
                is_portal_debug = bool(portal_member_id and portal_member_id in config.debug_portals)

                if is_portal_debug:
                    logger.error(
                        "[DEBUG-PORTAL:%s] %s\n%s",
                        portal_member_id,
                        message,
                        traceback.format_exc(),
                    )
                else:
                    logger.error("%s, args=%s, kwargs=%s: %s", message, args, kwargs, exc)

                if config.error_tickets_enabled and config.error_tickets_endpoint:
                    _send_error_ticket_async(
                        portal_member_id=portal_member_id,
                        error_message=f"{message}: {exc}",
                        trace_id=_get_current_trace_id(),
                        endpoint=config.error_tickets_endpoint,
                        service_name=config.otel_service_name or "excel-migration-api",
                    )

                return JsonResponse({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
                return response
        return wrapper
    return inner
