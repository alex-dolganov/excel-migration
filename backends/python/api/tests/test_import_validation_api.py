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


class ImportValidationApiTest(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def create_account(self, member_id="member-1", domain_url="test.bitrix24.ru"):
        return SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
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
                                    "isMultiple": False,
                                },
                                "BIRTHDATE": {
                                    "title": "Birthdate",
                                    "type": "date",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "STAGE_ID": {
                                    "title": "Stage",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": {
                                        "NEW": "New",
                                        "IN_PROGRESS": "In progress",
                                    },
                                },
                            }
                        )
                    )
                )
            ),
        )

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
                        (
                            "Leads",
                            [
                                ["Lead title", "Email", "Phone", "Birthdate"],
                                ["Alice", "alice@example.com", "+123456789", "2026-05-01"],
                                ["", "broken-email", "12", "32.13.2026"],
                            ],
                        ),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_session_with_stage(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads-stage.xlsx",
        )
        session.stored_file.save(
            "leads-stage.xlsx",
            SimpleUploadedFile(
                "leads-stage.xlsx",
                build_xlsx_with_sheets(
                    [
                        (
                            "Leads",
                            [
                                ["Lead title", "Stage"],
                                ["Alice", "Queued"],
                                ["Bob", "Paused"],
                            ],
                        ),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def save_mapping(self, session):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
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
                    "BIRTHDATE": {
                        "source_header": "Birthdate",
                        "column": "D",
                    },
                }
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

    def save_stage_mapping(self, session):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "TITLE": {
                        "source_header": "Lead title",
                        "column": "A",
                    },
                    "STAGE_ID": {
                        "source_header": "Stage",
                        "column": "B",
                    },
                }
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_validation_returns_row_level_issues_and_persists_summary(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        self.save_mapping(session)

        response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["checked_rows"], 2)
        self.assertEqual(response.json()["item"]["valid_rows"], 1)
        self.assertEqual(response.json()["item"]["invalid_rows"], 1)
        self.assertEqual(response.json()["item"]["issue_count"], 4)
        self.assertEqual(
            response.json()["item"]["issues"],
            [
                {
                    "row_number": 3,
                    "column": "A",
                    "source_header": "Lead title",
                    "target_field": "TITLE",
                    "code": "required",
                    "message": "Field \"Lead title\" is required",
                    "value": "",
                },
                {
                    "row_number": 3,
                    "column": "B",
                    "source_header": "Email",
                    "target_field": "EMAIL",
                    "code": "email",
                    "message": "Field \"Email\" must contain a valid email",
                    "value": "broken-email",
                },
                {
                    "row_number": 3,
                    "column": "C",
                    "source_header": "Phone",
                    "target_field": "PHONE",
                    "code": "phone",
                    "message": "Field \"Phone\" must contain a valid phone",
                    "value": "12",
                },
                {
                    "row_number": 3,
                    "column": "D",
                    "source_header": "Birthdate",
                    "target_field": "BIRTHDATE",
                    "code": "date",
                    "message": "Field \"Birthdate\" must contain a valid date",
                    "value": "32.13.2026",
                },
            ],
        )

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.VALIDATED)
        self.assertEqual(session.summary["validation"]["issue_count"], 4)
        self.assertEqual(session.summary["validation"]["invalid_rows"], 1)
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(session.failed_rows, 1)
        self.assertEqual(session.processed_rows, 2)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_validation_requires_saved_mapping(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Saved mapping is required before validation")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_validation_rejects_unmapped_list_values_before_run(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_stage()
        self.save_stage_mapping(session)

        response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Complete value mapping for list and status fields before validation")
        self.assertEqual(response.json()["unmapped_values"], {
            "STAGE_ID": ["Queued", "Paused"],
        })
        self.assertEqual(response.json()["unmapped_value_count"], 2)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_validation_is_limited_to_current_portal_session(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account(member_id="member-1", domain_url="test.bitrix24.ru")

        session = ImportSession.objects.create(
            portal_member_id="member-2",
            portal_domain="other.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="other.xlsx",
        )

        response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 404)
