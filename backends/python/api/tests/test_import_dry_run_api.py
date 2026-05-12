import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from importer.models import ImportSession


class FakeFieldsRequest:
    def __init__(self, result):
        self.result = result


class FakeAddRequest:
    def __init__(self, result):
        self.result = result


class FakeListRequest:
    def __init__(self, result):
        self.result = result


def build_xlsx_with_sheets(sheet_payloads):
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
{sheets}
  </sheets>
</workbook>
""".format(
        sheets="\n".join(
            f'    <sheet name="{sheet_name}" sheetId="{index}" r:id="rId{index}"/>'
            for index, (sheet_name, _rows) in enumerate(sheet_payloads, start=1)
        )
    )
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{relationships}
</Relationships>
""".format(
        relationships="\n".join(
            '  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'.format(
                index=index
            )
            for index, (_sheet_name, _rows) in enumerate(sheet_payloads, start=1)
        )
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        for index, (_sheet_name, rows) in enumerate(sheet_payloads, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", build_sheet_xml(rows))

    return buffer.getvalue()


def build_sheet_xml(rows):
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells_xml = []
        for column_index, value in enumerate(row, start=1):
            column_letter = chr(64 + column_index)
            cell_ref = f"{column_letter}{row_index}"
            escaped_value = escape(str(value))
            cells_xml.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{escaped_value}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells_xml)}</row>')

    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {rows}
  </sheetData>
</worksheet>
""".format(rows="".join(row_xml))


class ImportDryRunApiTest(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def create_account(self, *, duplicates_by_filter=None):
        add_calls = []
        list_calls = []
        duplicates_by_filter = duplicates_by_filter or {}

        def add(fields, *, params=None, timeout=None):
            add_calls.append(dict(fields))
            return FakeAddRequest(501)

        def list_method(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            list_calls.append(
                {
                    "filter": dict(filter or {}),
                    "select": list(select or []),
                }
            )
            return FakeListRequest(duplicates_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    lead=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Lead title",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "EMAIL": {
                                    "title": "Email",
                                    "type": "email",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "PHONE": {
                                    "title": "Phone",
                                    "type": "phone",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        ),
                        list=list_method,
                        add=add,
                    )
                )
            ),
        )
        account.add_calls = add_calls
        account.list_calls = list_calls
        return account

    def create_uploaded_session(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads.xlsx",
        )
        session.stored_file.save(
            "leads.xlsx",
            SimpleUploadedFile(
                "leads.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Lead title", "Phone"], ["Alice", "+123456789"], ["", "12"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_session_with_rows(self, rows, *, filename="leads-custom.xlsx"):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename=filename,
        )
        session.stored_file.save(
            filename,
            SimpleUploadedFile(
                filename,
                build_xlsx_with_sheets([("Leads", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def prepare_session(self, session, *, validate=True, mapping=None):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": mapping or {
                    "TITLE": {
                        "source_header": "Lead title",
                        "column": "A",
                    },
                    "PHONE": {
                        "source_header": "Phone",
                        "column": "B",
                    },
                }
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

        if validate:
            validation_response = self.client.post(
                reverse("importer:session-validate", kwargs={"session_id": session.id}),
                data={},
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-token",
            )
            self.assertEqual(validation_response.status_code, 200)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_dry_run_builds_payload_preview_without_creating_records(self, get_from_jwt_token):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session()
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-dry-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["checked_rows"], 2)
        self.assertEqual(response.json()["item"]["ready_rows"], 1)
        self.assertEqual(response.json()["item"]["skipped_rows"], 1)
        self.assertEqual(
            response.json()["item"]["results"],
            [
                {
                    "row_number": 2,
                    "status": "ready",
                    "fields": {
                        "TITLE": "Alice",
                        "PHONE": [
                            {
                                "VALUE": "+123456789",
                                "VALUE_TYPE": "WORK",
                            }
                        ],
                    },
                },
                {
                    "row_number": 3,
                    "status": "skipped",
                    "error": "Row has validation issues",
                },
            ],
        )
        self.assertEqual(account.add_calls, [])

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.VALIDATED)
        self.assertEqual(session.summary["dry_run"]["ready_rows"], 1)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_dry_run_requires_validation_before_execution(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        self.prepare_session(session, validate=False)

        response = self.client.post(
            reverse("importer:session-dry-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Validation is required before dry run")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_dry_run_marks_duplicate_rows_for_update_when_dedup_matches_existing_record(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("PHONE", "+123456789"),): [{"ID": 912}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session()
        self.prepare_session(session, validate=True)
        session.refresh_from_db()
        session.import_settings = {
            **session.import_settings,
            "dedup": {
                "strategy": "update",
                "fields": ["PHONE"],
            },
        }
        session.save(update_fields=["import_settings", "updated_at"])

        response = self.client.post(
            reverse("importer:session-dry-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["ready_rows"], 1)
        self.assertEqual(response.json()["item"]["results"][0], {
            "row_number": 2,
            "status": "ready_update",
            "record_id": 912,
            "duplicate_match_fields": ["PHONE"],
            "fields": {
                "TITLE": "Alice",
                "PHONE": [
                    {
                        "VALUE": "+123456789",
                        "VALUE_TYPE": "WORK",
                    }
                ],
            },
        })
        self.assertEqual(account.add_calls, [])
        self.assertEqual(account.list_calls, [{"filter": {"PHONE": "+123456789"}, "select": ["ID"]}])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_dry_run_uses_combined_dedup_filter_when_multiple_fields_are_selected(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("EMAIL", "alice@example.com"), ("PHONE", "+123456789")): [{"ID": 913}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session_with_rows(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(
            session,
            validate=True,
            mapping={
                "TITLE": {
                    "source_header": "Lead title",
                    "column": "A",
                },
                "EMAIL": {
                    "source_header": "Email",
                    "column": "B",
                },
                "PHONE": {
                    "source_header": "Phone",
                    "column": "C",
                },
            },
        )
        session.refresh_from_db()
        session.import_settings = {
            **session.import_settings,
            "dedup": {
                "strategy": "update",
                "fields": ["EMAIL", "PHONE"],
            },
        }
        session.save(update_fields=["import_settings", "updated_at"])

        response = self.client.post(
            reverse("importer:session-dry-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["results"], [
            {
                "row_number": 2,
                "status": "ready_update",
                "record_id": 913,
                "duplicate_match_fields": ["EMAIL", "PHONE"],
                "fields": {
                    "TITLE": "Alice",
                    "EMAIL": "alice@example.com",
                    "PHONE": [
                        {
                            "VALUE": "+123456789",
                            "VALUE_TYPE": "WORK",
                        }
                    ],
                },
            }
        ])
        self.assertEqual(account.list_calls, [
            {
                "filter": {
                    "EMAIL": "alice@example.com",
                    "PHONE": "+123456789",
                },
                "select": ["ID"],
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_dry_run_reports_missing_selected_dedup_fields_when_row_uses_partial_match(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("EMAIL", "alice@example.com"),): [{"ID": 914}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session_with_rows(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", ""],
            ]
        )
        self.prepare_session(
            session,
            validate=True,
            mapping={
                "TITLE": {
                    "source_header": "Lead title",
                    "column": "A",
                },
                "EMAIL": {
                    "source_header": "Email",
                    "column": "B",
                },
                "PHONE": {
                    "source_header": "Phone",
                    "column": "C",
                },
            },
        )
        session.refresh_from_db()
        session.import_settings = {
            **session.import_settings,
            "dedup": {
                "strategy": "update",
                "fields": ["EMAIL", "PHONE"],
            },
        }
        session.save(update_fields=["import_settings", "updated_at"])

        response = self.client.post(
            reverse("importer:session-dry-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["results"], [
            {
                "row_number": 2,
                "status": "ready_update",
                "record_id": 914,
                "duplicate_match_fields": ["EMAIL"],
                "dedup_missing_fields": ["PHONE"],
                "fields": {
                    "TITLE": "Alice",
                    "EMAIL": "alice@example.com",
                },
            }
        ])
        self.assertEqual(account.list_calls, [
            {
                "filter": {
                    "EMAIL": "alice@example.com",
                },
                "select": ["ID"],
            }
        ])
