import logging
from datetime import timedelta

import requests
from django.utils import timezone

from config import config

logger = logging.getLogger(__name__)

_REFRESH_AHEAD_MINUTES = 90
_STALE_CUTOFF_HOURS = 2


def refresh_expiring_tokens() -> dict:
    """Refresh Bitrix24 OAuth tokens that expire within the next 90 minutes.

    Called by Celery Beat every 30 minutes so no portal loses API access mid-import.
    Tokens already refreshed reactively by b24pysdk won't match the query (their
    expires timestamp will be > threshold), so double-refresh never happens.
    """
    from main.models import Bitrix24Account

    now = timezone.now()
    threshold_ts = int((now + timedelta(minutes=_REFRESH_AHEAD_MINUTES)).timestamp())
    stale_cutoff_ts = int((now - timedelta(hours=_STALE_CUTOFF_HOURS)).timestamp())

    accounts = Bitrix24Account.objects.filter(
        access_token__isnull=False,
        refresh_token__isnull=False,
        expires__lte=threshold_ts,
        expires__gte=stale_cutoff_ts,
    )

    refreshed = 0
    failed = 0

    for account in accounts:
        try:
            domain = account.domain_url
            if not domain.startswith("http"):
                domain = f"https://{domain}"

            resp = requests.post(
                f"{domain}/oauth/token/",
                data={
                    "grant_type": "refresh_token",
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "refresh_token": account.refresh_token,
                },
                timeout=15,
            )

            if resp.ok:
                data = resp.json()
                account.access_token = data.get("access_token", account.access_token)
                account.refresh_token = data.get("refresh_token", account.refresh_token)
                if data.get("expires"):
                    account.expires = int(data["expires"])
                if data.get("expires_in"):
                    account.expires_in = int(data["expires_in"])
                account.save(update_fields=["access_token", "refresh_token", "expires", "expires_in"])
                refreshed += 1
            else:
                logger.warning(
                    "Token refresh HTTP %s for account=%s portal=%s",
                    resp.status_code, account.pk, account.domain_url,
                )
                failed += 1

        except Exception:
            logger.exception("Token refresh error for account=%s", account.pk)
            failed += 1

    logger.info("Token refresh: refreshed=%d failed=%d", refreshed, failed)
    return {"refreshed": refreshed, "failed": failed}
