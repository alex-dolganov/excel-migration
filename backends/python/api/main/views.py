import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.clickjacking import xframe_options_exempt

from .utils.decorators import auth_required, log_errors, rate_limit
from .utils import AuthorizedRequest
from .models import ApplicationInstallation, Bitrix24Account

from config import load_config

logger = logging.getLogger(__name__)

__all__ = [
    "root",
    "health",
    "healthz",
    "get_enum",
    "get_list",
    "install",
    "uninstall",
    "get_token",
]

config = load_config()


def _coerce_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    return False


def _extract_admin_user_ids(payload) -> set[int]:
    if not isinstance(payload, (list, tuple, set)):
        return set()

    admin_user_ids = set()
    for item in payload:
        candidate = item
        if isinstance(item, dict):
            candidate = item.get("ID") or item.get("id") or item.get("USER_ID") or item.get("user_id")

        try:
            normalized_candidate = int(candidate)
        except (TypeError, ValueError):
            continue

        if normalized_candidate > 0:
            admin_user_ids.add(normalized_candidate)

    return admin_user_ids


def refresh_portal_admin_flag(account) -> None:
    try:
        admin_users_response = account.client.user.admin()
        admin_user_ids = _extract_admin_user_ids(getattr(admin_users_response, "result", None))
    except Exception:
        return

    current_user_id = int(getattr(account, "b24_user_id", 0) or 0)
    if current_user_id <= 0:
        return

    is_portal_admin = current_user_id in admin_user_ids
    if bool(getattr(account, "is_b24_user_admin", False)) == is_portal_admin:
        return

    account.is_b24_user_admin = is_portal_admin
    account.save(update_fields=["is_b24_user_admin"])


@xframe_options_exempt
@require_GET
@log_errors("root")
@auth_required
def root(request: AuthorizedRequest):
    return JsonResponse({"message": "Python Backend is running"})


@xframe_options_exempt
@require_GET
@log_errors("health")
@auth_required
def health(request: AuthorizedRequest):
    return JsonResponse({
        "status": "healthy",
        "backend": "python",
        "timestamp": timezone.now().timestamp(),
    })


@xframe_options_exempt
@require_GET
@log_errors("healthz")
def healthz(request):
    return JsonResponse({
        "status": "healthy",
        "backend": "python",
        "timestamp": timezone.now().timestamp(),
    })


@xframe_options_exempt
@require_GET
@log_errors("get_enum")
@auth_required
def get_enum(request: AuthorizedRequest):
    options = ["option 1", "option 2", "option 3"]
    return JsonResponse(options, safe=False)


@xframe_options_exempt
@require_GET
@log_errors("get_list")
@auth_required
def get_list(request: AuthorizedRequest):
    elements = ["element 1", "element 2", "element 3"]
    return JsonResponse(elements, safe=False)


@xframe_options_exempt
@csrf_exempt
@require_POST
@log_errors("install")
@auth_required
def install(request: AuthorizedRequest):
    bitrix24_account = request.bitrix24_account

    ApplicationInstallation.objects.update_or_create(
        bitrix_24_account=bitrix24_account,
        defaults={
            "status": bitrix24_account.status,
            "portal_license_family": "",
            "application_token": bitrix24_account.application_token,
        },
    )

    return JsonResponse({"message": "Installation successful"})


@xframe_options_exempt
@csrf_exempt
@require_POST
@log_errors("uninstall")
def uninstall(request):
    """Handle ONAPPUNINSTALL event from Bitrix24 marketplace.

    Bitrix24 sends: member_id, application_token, event=ONAPPUNINSTALL.
    We verify application_token against ApplicationInstallation before acting.
    Tokens are nullified but import history is preserved for reinstall.
    """
    member_id = request.POST.get("member_id") or request.POST.get("auth[member_id]")
    application_token = request.POST.get("application_token")
    if not member_id:
        try:
            body = json.loads(request.body)
            member_id = body.get("member_id") or (body.get("auth") or {}).get("member_id")
            application_token = application_token or body.get("application_token")
        except Exception:
            pass

    if not member_id or not application_token:
        return JsonResponse({"error": "member_id and application_token required"}, status=400)

    # Verify the request is legitimately from Bitrix24 for this portal
    valid = ApplicationInstallation.objects.filter(
        bitrix_24_account__member_id=member_id,
        application_token=application_token,
    ).exists()

    if not valid:
        logger.warning("ONAPPUNINSTALL rejected: unknown member_id=%s or wrong token", member_id)
        return JsonResponse({"error": "Forbidden"}, status=403)

    updated = Bitrix24Account.objects.filter(member_id=member_id).update(
        access_token=None,
        refresh_token=None,
        status="uninstalled",
    )

    logger.info("ONAPPUNINSTALL: member_id=%s accounts_deactivated=%d", member_id, updated)
    return JsonResponse({"message": "Uninstalled", "accounts_deactivated": updated})


@xframe_options_exempt
@csrf_exempt
@require_POST
@log_errors("get_token")
@rate_limit("get_token", limit=20, window=60)
@auth_required
def get_token(request: AuthorizedRequest):
    bitrix24_account = request.bitrix24_account
    refresh_portal_admin_flag(bitrix24_account)

    return JsonResponse({"token": bitrix24_account.create_jwt_token(minutes=480)})
