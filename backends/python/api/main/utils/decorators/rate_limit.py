from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def rate_limit(key_prefix: str, limit: int = 20, window: int = 60):
    """Limit requests per IP to `limit` per `window` seconds.

    Uses Django's default cache (LocMemCache per process). For a single
    Gunicorn worker this is exact; for multi-worker setups each worker
    tracks independently — effective limit is limit * workers, which is
    still a meaningful DoS barrier without needing Redis.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
            cache_key = f"rl:{key_prefix}:{ip}"

            # add() is a no-op if the key exists — sets initial value atomically
            cache.add(cache_key, 0, window)
            try:
                count = cache.incr(cache_key)
            except ValueError:
                count = 1

            if count > limit:
                return JsonResponse(
                    {"error": "Too many requests, please try again later."},
                    status=429,
                    headers={"Retry-After": str(window)},
                )

            return view_func(request, *args, **kwargs)

        return wrapped
    return decorator
