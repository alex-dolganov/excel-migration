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


class FakeUsersRequest:
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


class ImportMappingApiTest(TestCase):
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
                        ("Leads", [["Lead title", "Phone", "City"], ["Alice", "+123", "Moscow"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_session_with_headers(self, headers, data_rows, *, filename="leads-custom.xlsx"):
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
                build_xlsx_with_sheets(
                    [
                        ("Leads", [headers, *data_rows]),
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
            original_filename="leads.xlsx",
        )
        session.stored_file.save(
            "leads.xlsx",
            SimpleUploadedFile(
                "leads.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Lead title", "Stage"], ["Alice", "Queued"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_session_with_exact_and_unknown_stage_values(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads-stage-mixed.xlsx",
        )
        session.stored_file.save(
            "leads-stage-mixed.xlsx",
            SimpleUploadedFile(
                "leads-stage-mixed.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Lead title", "Stage"], ["Alice", "New"], ["Bob", "IN_PROGRESS"], ["Eve", "Paused"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_session_with_many_stage_values(self):
        rows = [["Lead title", "Stage"]]
        rows.extend([[f"Lead {index}", f"Stage {index}"] for index in range(1, 12)])

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads-many-stages.xlsx",
        )
        session.stored_file.save(
            "leads-many-stages.xlsx",
            SimpleUploadedFile(
                "leads-many-stages.xlsx",
                build_xlsx_with_sheets([("Leads", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_candidate_mapping_and_saved_mapping(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["headers"], ["Lead title", "Phone", "City"])
        self.assertEqual(response.json()["item"]["candidate_mapping"], {
            "TITLE": {
                "source_header": "Lead title",
                "column": "A",
                "target_field": "TITLE",
                "match_type": "exact",
            },
            "PHONE": {
                "source_header": "Phone",
                "column": "B",
                "target_field": "PHONE",
                "match_type": "exact",
            },
            "UF_CRM_CITY": {
                "source_header": "City",
                "column": "C",
                "target_field": "UF_CRM_CITY",
                "match_type": "exact",
            },
        })
        self.assertEqual(response.json()["item"]["saved_mapping"], {})

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_fuzzy_candidate_mapping_for_close_headers(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_headers(
            ["Lead Name", "Mobile phone", "Town"],
            [["Alice", "+123", "Moscow"]],
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["candidate_mapping"], {
            "TITLE": {
                "source_header": "Lead Name",
                "column": "A",
                "target_field": "TITLE",
                "match_type": "fuzzy",
            },
            "PHONE": {
                "source_header": "Mobile phone",
                "column": "B",
                "target_field": "PHONE",
                "match_type": "fuzzy",
            },
            "UF_CRM_CITY": {
                "source_header": "Town",
                "column": "C",
                "target_field": "UF_CRM_CITY",
                "match_type": "fuzzy",
            },
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_persists_mapping_schema_in_import_settings(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session()
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.patch(
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
                        "target_field": "PHONE",
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

        self.assertEqual(response.status_code, 200)
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
        self.assertEqual(response.json()["item"]["saved_dedup"], {
            "strategy": "update",
            "fields": ["PHONE"],
        })

        session.refresh_from_db()
        self.assertEqual(session.import_settings["mapping"], {
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
        self.assertEqual(session.import_settings["dedup"], {
            "strategy": "update",
            "fields": ["PHONE"],
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_persists_value_mapping_for_stage_field(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_stage()
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "STAGE_ID": {
                        "source_header": "Stage",
                        "column": "B",
                        "value_mapping": {
                            "Queued": "IN_PROGRESS",
                        },
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["saved_mapping"], {
            "STAGE_ID": {
                "source_header": "Stage",
                "column": "B",
                "target_field": "STAGE_ID",
                "value_mapping": {
                    "Queued": "IN_PROGRESS",
                },
            },
        })

        session.refresh_from_db()
        self.assertEqual(session.import_settings["mapping"]["STAGE_ID"]["value_mapping"], {
            "Queued": "IN_PROGRESS",
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_observed_values_for_enum_fields_from_full_file(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_many_stage_values()
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(len(preview_response.json()["item"]["preview_rows"]), 10)

        response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["observed_values"], {
            "STAGE_ID": [
                "Stage 1",
                "Stage 2",
                "Stage 3",
                "Stage 4",
                "Stage 5",
                "Stage 6",
                "Stage 7",
                "Stage 8",
                "Stage 9",
                "Stage 10",
                "Stage 11",
            ],
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_treats_exact_list_values_as_already_resolved(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_exact_and_unknown_stage_values()
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
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(mapping_response.status_code, 200)
        self.assertEqual(mapping_response.json()["item"]["observed_values"], {
            "STAGE_ID": ["New", "IN_PROGRESS", "Paused"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_values"], {
            "STAGE_ID": ["Paused"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_value_count"], 1)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_task_mapping_returns_default_responsible_options_and_persists_selection(self, get_from_jwt_token):
        def get_users(*, filter=None, select=None):
            return FakeUsersRequest([
                {"ID": 59, "NAME": "Alice", "LAST_NAME": "Owner", "EMAIL": "alice@example.com"},
                {"ID": 73, "NAME": "Bob", "LAST_NAME": "Manager", "EMAIL": "bob@example.com"},
            ])

        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=get_users,
                )
            ),
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="tasks.xlsx",
            preview_data={
                "headers": ["Task title"],
                "columns": ["A"],
            },
        )

        response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "TITLE": {
                        "source_header": "Task title",
                        "column": "A",
                    },
                },
                "default_responsible_id": "59",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["task_defaults"], {
            "default_responsible_id": "59",
        })
        self.assertEqual(response.json()["item"]["task_user_options"], [
            {"value": "59", "label": "Alice Owner · alice@example.com · ID 59"},
            {"value": "73", "label": "Bob Manager · bob@example.com · ID 73"},
        ])

        session.refresh_from_db()
        self.assertEqual(session.import_settings["task_defaults"], {
            "default_responsible_id": "59",
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_task_comment_mapping_returns_default_author_options_and_persists_selection(self, get_from_jwt_token):
        def get_users(*, filter=None, select=None):
            return FakeUsersRequest([
                {"ID": 59, "NAME": "Alice", "LAST_NAME": "Owner", "EMAIL": "alice@example.com"},
                {"ID": 73, "NAME": "Bob", "LAST_NAME": "Manager", "EMAIL": "bob@example.com"},
            ])

        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=get_users,
                )
            ),
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK_COMMENT,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="comments.xlsx",
            preview_data={
                "headers": ["Task", "Message"],
                "columns": ["A", "B"],
            },
        )

        response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "TASK_ID": {
                        "source_header": "Task",
                        "column": "A",
                    },
                    "POST_MESSAGE": {
                        "source_header": "Message",
                        "column": "B",
                    },
                },
                "default_comment_author_id": "73",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["task_defaults"], {
            "default_comment_author_id": "73",
        })
        self.assertEqual(response.json()["item"]["task_user_options"], [
            {"value": "59", "label": "Alice Owner · alice@example.com · ID 59"},
            {"value": "73", "label": "Bob Manager · bob@example.com · ID 73"},
        ])

        session.refresh_from_db()
        self.assertEqual(session.import_settings["task_defaults"], {
            "default_comment_author_id": "73",
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_requires_existing_preview_headers(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads.xlsx",
        )

        response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Preview data is required before mapping")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_is_limited_to_current_portal_session(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account(member_id="member-1", domain_url="test.bitrix24.ru")

        session = ImportSession.objects.create(
            portal_member_id="member-2",
            portal_domain="other.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="other.xlsx",
            preview_data={
                "headers": ["Lead title"],
                "columns": ["A"],
            },
        )

        response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 404)
