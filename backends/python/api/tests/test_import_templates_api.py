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

from importer.models import ImportSession, ImportTemplate


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


class ImportTemplatesApiTest(TestCase):
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
                                "PHONE": {
                                    "title": "Phone",
                                    "type": "phone",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                                "UF_CRM_CITY": {
                                    "title": "City",
                                    "type": "string",
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
                                        "WON": "Won",
                                    },
                                },
                            }
                        )
                    )
                )
            ),
        )

    def create_uploaded_session(self, *, rows=None):
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
                        ("Leads", rows or [["Lead title", "Phone", "City"], ["Alice", "+123", "Moscow"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def prepare_session_mapping(self, session):
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
                    "PHONE": {
                        "source_header": "Phone",
                        "column": "B",
                    },
                },
                "dedup": {
                    "strategy": "update",
                    "fields": ["PHONE"],
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

    def prepare_session_stage_mapping(self, session):
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
                        "value_mapping": {
                            "Queued": "IN_PROGRESS",
                            "Closed won": "WON",
                        },
                    },
                },
                "dedup": {
                    "strategy": "create",
                    "fields": [],
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_list_only_active_templates_for_current_portal_and_entity(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Lead default",
            mapping_schema={"TITLE": {"target_field": "TITLE"}},
        )
        ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.CONTACT,
            name="Contact default",
            mapping_schema={"NAME": {"target_field": "NAME"}},
        )
        ImportTemplate.objects.create(
            portal_member_id="member-2",
            portal_domain="other.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Foreign",
            mapping_schema={"TITLE": {"target_field": "TITLE"}},
        )

        response = self.client.get(
            f"{reverse('importer:templates')}?entity_type=lead",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["items"][0]["name"], "Lead default")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_template_from_session_mapping_and_structure(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        self.prepare_session_mapping(session)

        response = self.client.post(
            reverse("importer:templates"),
            data={
                "session_id": str(session.id),
                "name": "Leads from Excel",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["name"], "Leads from Excel")
        self.assertEqual(response.json()["item"]["mapping_schema"], {
            "TITLE": {
                "source_header": "Lead title",
                "column": "A",
                "target_field": "TITLE",
            },
            "PHONE": {
                "source_header": "Phone",
                "column": "B",
                "target_field": "PHONE",
            },
        })
        self.assertEqual(response.json()["item"]["column_settings"], {
            "sheet_name": "Leads",
            "header_row": 1,
            "data_start_row": 2,
        })
        self.assertEqual(response.json()["item"]["dedup_settings"], {
            "strategy": "update",
            "fields": ["PHONE"],
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_template_prefers_mapping_payload_over_stale_session_mapping(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        self.prepare_session_mapping(session)

        response = self.client.post(
            reverse("importer:templates"),
            data={
                "session_id": str(session.id),
                "name": "Leads current draft",
                "mapping": {
                    "TITLE": {
                        "source_header": "Lead title",
                        "column": "A",
                        "target_field": "TITLE",
                    },
                    "UF_CRM_CITY": {
                        "source_header": "City",
                        "column": "C",
                        "target_field": "UF_CRM_CITY",
                    },
                },
                "dedup": {
                    "strategy": "skip",
                    "fields": ["TITLE"],
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["mapping_schema"], {
            "TITLE": {
                "source_header": "Lead title",
                "column": "A",
                "target_field": "TITLE",
            },
            "UF_CRM_CITY": {
                "source_header": "City",
                "column": "C",
                "target_field": "UF_CRM_CITY",
            },
        })
        self.assertEqual(response.json()["item"]["dedup_settings"], {
            "strategy": "skip",
            "fields": ["TITLE"],
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_create_template_persists_value_mapping_for_stage_fields(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session(
            rows=[
                ["Lead title", "Stage"],
                ["Alice", "Queued"],
                ["Bob", "Closed won"],
            ]
        )
        self.prepare_session_stage_mapping(session)

        response = self.client.post(
            reverse("importer:templates"),
            data={
                "session_id": str(session.id),
                "name": "Leads with stage mapping",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["mapping_schema"], {
            "TITLE": {
                "source_header": "Lead title",
                "column": "A",
                "target_field": "TITLE",
            },
            "STAGE_ID": {
                "source_header": "Stage",
                "column": "B",
                "target_field": "STAGE_ID",
                "value_mapping": {
                    "Queued": "IN_PROGRESS",
                    "Closed won": "WON",
                },
            },
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_apply_template_to_session_updates_structure_and_mapping(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        template = ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Leads from Excel",
            mapping_schema={
                "TITLE": {
                    "source_header": "Lead title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "PHONE": {
                    "source_header": "Phone",
                    "column": "B",
                    "target_field": "PHONE",
                },
            },
            column_settings={
                "sheet_name": "Leads",
                "header_row": 1,
                "data_start_row": 2,
            },
            dedup_settings={
                "strategy": "update",
                "fields": ["PHONE"],
            },
        )

        session = self.create_uploaded_session(
            rows=[
                ["Lead title", "Phone", "City"],
                ["Bob", "+987", "Paris"],
            ]
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-apply-template", kwargs={"session_id": session.id}),
            data={
                "template_id": str(template.id),
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["applied_template_id"], str(template.id))
        self.assertEqual(response.json()["item"]["header_row"], 1)
        self.assertEqual(response.json()["item"]["data_start_row"], 2)
        self.assertEqual(response.json()["item"]["headers"], ["Lead title", "Phone", "City"])
        self.assertEqual(response.json()["item"]["saved_mapping"], {
            "TITLE": {
                "source_header": "Lead title",
                "column": "A",
                "target_field": "TITLE",
            },
            "PHONE": {
                "source_header": "Phone",
                "column": "B",
                "target_field": "PHONE",
            },
        })

        session.refresh_from_db()
        self.assertEqual(session.source_sheet_name, "Leads")
        self.assertEqual(session.header_row, 1)
        self.assertEqual(session.data_start_row, 2)
        self.assertEqual(session.import_settings["mapping"], template.mapping_schema)
        self.assertEqual(session.import_settings["dedup"], template.dedup_settings)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_apply_template_restores_stage_value_mapping_for_new_session(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        template = ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Leads with stages",
            mapping_schema={
                "TITLE": {
                    "source_header": "Lead title",
                    "column": "A",
                    "target_field": "TITLE",
                },
                "STAGE_ID": {
                    "source_header": "Stage",
                    "column": "B",
                    "target_field": "STAGE_ID",
                    "value_mapping": {
                        "Queued": "IN_PROGRESS",
                        "Closed won": "WON",
                    },
                },
            },
            column_settings={
                "sheet_name": "Leads",
                "header_row": 1,
                "data_start_row": 2,
            },
            dedup_settings={
                "strategy": "create",
                "fields": [],
            },
        )

        session = self.create_uploaded_session(
            rows=[
                ["Lead title", "Stage"],
                ["Alice", "Queued"],
                ["Bob", "Closed won"],
                ["Eve", "Paused"],
            ]
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        apply_response = self.client.post(
            reverse("importer:session-apply-template", kwargs={"session_id": session.id}),
            data={
                "template_id": str(template.id),
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(apply_response.status_code, 200)

        mapping_response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)
        self.assertEqual(mapping_response.json()["item"]["saved_mapping"], template.mapping_schema)
        self.assertEqual(mapping_response.json()["item"]["observed_values"], {
            "STAGE_ID": ["Queued", "Closed won", "Paused"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_values"], {
            "STAGE_ID": ["Paused"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_value_count"], 1)
