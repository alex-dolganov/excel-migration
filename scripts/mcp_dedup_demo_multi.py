"""Ad-hoc demo: import lead/company/contact into Bitrix24 (mp24) with create/skip/update dedup.
Run:  Get-Content scripts/mcp_dedup_demo_multi.py -Raw | docker exec -i api-python-worker python manage.py shell
"""
import io
import json

from django.conf import settings as _settings
_settings.ALLOWED_HOSTS = ["*"]

from django.test import Client

from main.models import Bitrix24Account
from importer.models import ImportSession
from importer.views import execute_import_session_run_now

TITLE_BASE = "MCP-DEDUP-DEMO"

acc = Bitrix24Account.objects.filter(domain_url__icontains="mp24").first()
print("ACCOUNT", acc.pk, getattr(acc, "domain_url", None), "user_id=", getattr(acc, "b24_user_id", None))
token = acc.create_jwt_token(minutes=60)
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
c = Client()


def _csv(name_field_label, second_label, rows):
    lines = [f"{name_field_label},{second_label}"] + [f"{n},{v}" for n, v in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_strategy(entity_type, name_field, second_field, dedup_fields, strategy, rows):
    print(f"\n--- {entity_type} / strategy={strategy} ---")
    r = c.post(
        "/api/import-sessions",
        data=json.dumps({
            "entity_type": entity_type,
            "source_format": "csv",
            "original_filename": "data.csv",
            "import_mode": "advanced",
        }),
        content_type="application/json",
        **AUTH,
    )
    assert r.status_code == 201, ("create", r.status_code, r.content[:400])
    sid = r.json()["item"]["id"]

    f = io.BytesIO(_csv("Name", "Note", rows)); f.name = "data.csv"
    r = c.post(f"/api/import-sessions/{sid}/upload", data={"file": f}, **AUTH)
    assert r.status_code == 200, ("upload", r.status_code, r.content[:400])

    r = c.get(f"/api/import-sessions/{sid}/preview", **AUTH)
    assert r.status_code == 200, ("preview", r.status_code, r.content[:400])
    item = r.json()["item"]
    columns = item["columns"]; headers = item["headers"]

    mapping = {
        name_field: {"target_field": name_field, "source_header": headers[0], "column": columns[0]},
        second_field: {"target_field": second_field, "source_header": headers[1], "column": columns[1]},
    }
    dedup = {"strategy": strategy, "fields": dedup_fields, "condition": "any"}
    r = c.patch(
        f"/api/import-sessions/{sid}/mapping",
        data=json.dumps({"mapping": mapping, "dedup": dedup, "import_mode": "advanced"}),
        content_type="application/json",
        **AUTH,
    )
    assert r.status_code == 200, ("mapping", r.status_code, r.content[:600])

    r = c.post(f"/api/import-sessions/{sid}/validate", **AUTH)
    assert r.status_code == 200, ("validate", r.status_code, r.content[:600])

    session = ImportSession.objects.get(pk=sid)
    result = execute_import_session_run_now(session=session, account=acc)
    run = (session.summary or {}).get("import_run", {})
    print(f"    counts: created={run.get('created_rows')} updated={run.get('updated_rows')} "
          f"skipped={run.get('skipped_rows')} failed={run.get('failed_rows')}")
    for rr in (result.get("results") or []):
        print(f"      row {rr.get('row_number')}: {rr.get('status')} id={rr.get('report_record_id')} "
              f"title={rr.get('report_title')}" + (f" match={rr.get('duplicate_match_fields')}" if rr.get('duplicate_match_fields') else ""))


# entity_type, name_field, second_field, dedup_fields
CONFIGS = [
    ("lead", "TITLE", "COMMENTS", ["TITLE"]),
    ("company", "TITLE", "COMMENTS", ["TITLE"]),
    ("contact", "NAME", "COMMENTS", ["NAME"]),
]

for entity_type, name_field, second_field, dedup_fields in CONFIGS:
    print("\n" + "=" * 70)
    print(f"ENTITY = {entity_type}")
    print("=" * 70)

    # 1) create — always create (intra-file dup Alpha created twice)
    run_strategy(entity_type, name_field, second_field, dedup_fields, "create", [
        (f"{TITLE_BASE} Alpha", "v1"),
        (f"{TITLE_BASE} Beta", "v2"),
        (f"{TITLE_BASE} Alpha", "v3"),
    ])
    # 2) skip — existing Alpha/Beta skipped, Gamma created
    run_strategy(entity_type, name_field, second_field, dedup_fields, "skip", [
        (f"{TITLE_BASE} Alpha", "v9"),
        (f"{TITLE_BASE} Beta", "v9"),
        (f"{TITLE_BASE} Gamma", "vG"),
    ])
    # 3) update — existing Alpha updated, Delta created
    run_strategy(entity_type, name_field, second_field, dedup_fields, "update", [
        (f"{TITLE_BASE} Alpha", "v7-updated"),
        (f"{TITLE_BASE} Delta", "vD"),
    ])

print("\nDONE")
