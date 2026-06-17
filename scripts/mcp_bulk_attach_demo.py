"""Ad-hoc demo: bulk-attach a file to CRM entities (mp24) for contact/company/deal.
Lead is skipped (no file-type field in this portal).
Run:  Get-Content scripts/mcp_bulk_attach_demo.py -Raw | docker exec -i api-python-worker python manage.py shell
"""
import base64
import io
import json

from django.conf import settings as _settings
_settings.ALLOWED_HOSTS = ["*"]

from django.test import Client

from main.models import Bitrix24Account
from importer.models import ImportSession
from importer.services.bulk_attach import execute_bulk_attach

# 1x1 transparent PNG (valid image for PHOTO/LOGO image fields)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

acc = Bitrix24Account.objects.filter(domain_url__icontains="mp24").first()
print("ACCOUNT", acc.pk, getattr(acc, "domain_url", None))
token = acc.create_jwt_token(minutes=60)
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
c = Client()

# entity_type, file_field_id, filter (scope to our test records)
CONFIGS = [
    ("contact", "PHOTO", {"%NAME": "MCP-DEDUP-DEMO"}),
    ("company", "LOGO", {"%TITLE": "MCP-DEDUP-DEMO"}),
    ("deal", "UF_CRM_1779450511", {"%TITLE": "MCP-DEDUP-DEMO"}),
]

for entity_type, field_id, flt in CONFIGS:
    print("\n" + "=" * 60)
    print(f"BULK ATTACH -> {entity_type} (field={field_id})")
    print("=" * 60)

    # preview how many entities match
    r = c.post("/api/crm-filter-preview",
               data=json.dumps({"entity_type": entity_type, "filter": flt}),
               content_type="application/json", **AUTH)
    prev = r.json()
    print(f"  filter matches total={prev.get('total')} sample={[s['id'] for s in prev.get('sample', [])]}")

    # upload file
    f = io.BytesIO(PNG); f.name = "mcp-test.png"
    r = c.post("/api/bulk-attach-upload", data={"file": f}, **AUTH)
    assert r.status_code == 200, ("upload", r.status_code, r.content[:300])
    up = r.json(); file_id = up["file_id"]; file_name = up["file_name"]

    # create bulk-attach session
    r = c.post("/api/bulk-attach-sessions",
               data=json.dumps({
                   "entity_type": entity_type,
                   "file_id": file_id,
                   "file_name": file_name,
                   "field_id": field_id,
                   "filter": flt,
               }),
               content_type="application/json", **AUTH)
    assert r.status_code == 201, ("create", r.status_code, r.content[:400])
    sid = r.json()["item"]["id"]

    # run synchronously
    session = ImportSession.objects.get(pk=sid)
    result = execute_bulk_attach(session=session, account=acc)
    session.refresh_from_db()
    print(f"  RESULT status={session.status} total={result['total']} "
          f"successful={result['successful']} failed={result['failed']}")
    for rr in result["results"]:
        line = f"    entity {rr['entity_id']}: {rr['status']}"
        if rr.get("error"):
            line += f" ERR={rr['error'][:120]}"
        print(line)

print("\nlead: SKIPPED (no file-type field in this portal)")
print("DONE")
