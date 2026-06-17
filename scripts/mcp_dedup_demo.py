"""Ad-hoc demo: import deals into Bitrix24 (mp24) with create/skip/update dedup strategies.
Run inside api container:  cat scripts/mcp_dedup_demo.py | docker exec -i api-python-worker python manage.py shell
"""
import io
import json

from django.conf import settings as _settings
_settings.ALLOWED_HOSTS = ["*"]

from django.test import Client

from main.models import Bitrix24Account
from importer.views import execute_import_session_run_now

PORTAL = "mp24.bitrix24.ru"
TITLE_BASE = "MCP-DEDUP-DEMO"

acc = Bitrix24Account.objects.filter(domain_url__icontains="mp24").first()
print("ACCOUNT", acc.pk, getattr(acc, "domain_url", None), "user_id=", getattr(acc, "b24_user_id", None))
token = acc.create_jwt_token(minutes=60)
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
c = Client()


def _csv(rows):
    lines = ["Title,Amount"] + [f"{t},{a}" for t, a in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_strategy(label, strategy, rows):
    print("\n" + "=" * 70)
    print(f"STRATEGY = {strategy}  ({label})")
    print("=" * 70)

    # 1. create session
    r = c.post(
        "/api/import-sessions",
        data=json.dumps({
            "entity_type": "deal",
            "source_format": "csv",
            "original_filename": "deals.csv",
            "import_mode": "advanced",
        }),
        content_type="application/json",
        **AUTH,
    )
    assert r.status_code == 201, ("create", r.status_code, r.content[:400])
    sid = r.json()["item"]["id"]

    # 2. upload
    f = io.BytesIO(_csv(rows)); f.name = "deals.csv"
    r = c.post(f"/api/import-sessions/{sid}/upload", data={"file": f}, **AUTH)
    assert r.status_code == 200, ("upload", r.status_code, r.content[:400])

    # 3. preview (GET detects header/columns)
    r = c.get(f"/api/import-sessions/{sid}/preview", **AUTH)
    assert r.status_code == 200, ("preview", r.status_code, r.content[:400])
    item = r.json()["item"]
    columns = item["columns"]
    headers = item["headers"]
    print("  columns=", columns, "headers=", headers, "data_start_row=", item.get("data_start_row"))

    # 4. mapping (col0 -> TITLE, col1 -> OPPORTUNITY) + dedup
    mapping = {
        "TITLE": {"target_field": "TITLE", "source_header": headers[0], "column": columns[0]},
        "OPPORTUNITY": {"target_field": "OPPORTUNITY", "source_header": headers[1], "column": columns[1]},
    }
    dedup = {"strategy": strategy, "fields": ["TITLE"], "condition": "any"}
    r = c.patch(
        f"/api/import-sessions/{sid}/mapping",
        data=json.dumps({"mapping": mapping, "dedup": dedup, "import_mode": "advanced"}),
        content_type="application/json",
        **AUTH,
    )
    assert r.status_code == 200, ("mapping", r.status_code, r.content[:600])

    # 5. validate
    r = c.post(f"/api/import-sessions/{sid}/validate", **AUTH)
    assert r.status_code == 200, ("validate", r.status_code, r.content[:600])
    v = r.json()["item"]
    print(f"  validate: checked={v.get('checked_rows')} valid={v.get('valid_rows')} invalid={v.get('invalid_rows')}")

    # 6. run synchronously
    from importer.models import ImportSession
    session = ImportSession.objects.get(pk=sid)
    result = execute_import_session_run_now(session=session, account=acc)
    session.refresh_from_db()
    print(f"  RESULT status={session.status} processed={session.processed_rows} ok={session.successful_rows} failed={session.failed_rows}")
    # per-row results
    summary = session.summary if isinstance(session.summary, dict) else {}
    run = summary.get("import_run") if isinstance(summary.get("import_run"), dict) else {}
    counts = {k: run.get(k) for k in ("created", "updated", "skipped", "failed") if k in run}
    print("  import_run counts:", counts or run)
    rows_out = result.get("results") if isinstance(result, dict) else None
    if rows_out:
        for rr in rows_out:
            print(f"    row {rr.get('row_number')}: {rr.get('status')} id={rr.get('report_record_id')} title={rr.get('report_title')} err={rr.get('error')}")
    return result


# Strategy 1: create — all rows created (incl. intra-file dup Alpha)
run_strategy("all created, dup ignored", "create", [
    (f"{TITLE_BASE} Alpha", 1000),
    (f"{TITLE_BASE} Beta", 2000),
    (f"{TITLE_BASE} Alpha", 1500),
])

# Strategy 2: skip — Alpha/Beta exist -> skipped, Gamma new -> created
run_strategy("dups skipped, new created", "skip", [
    (f"{TITLE_BASE} Alpha", 9999),
    (f"{TITLE_BASE} Beta", 9999),
    (f"{TITLE_BASE} Gamma", 3000),
])

# Strategy 3: update — Alpha exists -> updated, Delta new -> created
run_strategy("dup updated, new created", "update", [
    (f"{TITLE_BASE} Alpha", 7777),
    (f"{TITLE_BASE} Delta", 4000),
])

print("\nDONE")
