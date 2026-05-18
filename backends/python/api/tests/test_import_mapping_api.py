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

    def create_linked_company_contact_account(self, member_id="member-1", domain_url="test.bitrix24.ru"):
        return SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    company=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название компании",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "PHONE": {
                                    "title": "Телефон компании",
                                    "type": "phone",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        )
                    ),
                    contact=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "NAME": {
                                    "title": "Имя контакта",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "EMAIL": {
                                    "title": "Email контакта",
                                    "type": "email",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        )
                    ),
                )
            ),
        )

    def create_linked_company_deal_account(self, member_id="member-1", domain_url="test.bitrix24.ru"):
        return SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    company=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название компании",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "PHONE": {
                                    "title": "Телефон компании",
                                    "type": "phone",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        )
                    ),
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Название сделки",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "OPPORTUNITY": {
                                    "title": "Сумма",
                                    "type": "money",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    ),
                )
            ),
        )

    def create_deal_account_with_generic_titles(self, member_id="member-1", domain_url="test.bitrix24.ru"):
        return SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    deal=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "TITLE": {
                                    "title": "Title",
                                    "type": "string",
                                    "isRequired": True,
                                    "isMultiple": False,
                                },
                                "SOURCE_ID": {
                                    "title": "Source",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": {
                                        "SALE": "Продажа",
                                        "ADVERTISING": "Реклама",
                                    },
                                },
                                "TYPE_ID": {
                                    "title": "Type",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": {
                                        "SALE": "Продажа",
                                        "COMPLEX": "Комплексная",
                                    },
                                },
                                "OPENED": {
                                    "title": "Available to all",
                                    "type": "boolean",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        )
                    )
                )
            ),
        )

    def create_account_with_nested_source_items(self, member_id="member-1", domain_url="test.bitrix24.ru"):
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
                                "SOURCE_ID": {
                                    "title": "Source",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": {
                                        "SALE": {
                                            "ID": "SALE",
                                            "VALUE": "Продажа",
                                        },
                                        "ADVERTISING": {
                                            "ID": "ADVERTISING",
                                            "VALUE": "Реклама",
                                        },
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

    def create_uploaded_linked_company_contact_session(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type="linked_company_contact",
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="linked-company-contact.xlsx",
        )
        session.stored_file.save(
            "linked-company-contact.xlsx",
            SimpleUploadedFile(
                "linked-company-contact.xlsx",
                build_xlsx_with_sheets(
                    [
                        (
                            "Linked",
                            [
                                ["Название компании", "Телефон компании", "Имя контакта", "Email контакта"],
                                ["ООО Альфа", "+78005550101", "Алиса", "alice@example.ru"],
                            ],
                        ),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_linked_company_contact_session_with_headers(
        self,
        headers,
        data_rows,
        *,
        filename="linked-company-contact-custom.xlsx",
    ):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type="linked_company_contact",
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
                        ("Linked", [headers, *data_rows]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_linked_company_deal_session(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type="linked_company_deal",
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="linked-company-deal.xlsx",
        )
        session.stored_file.save(
            "linked-company-deal.xlsx",
            SimpleUploadedFile(
                "linked-company-deal.xlsx",
                build_xlsx_with_sheets(
                    [
                        (
                            "Linked",
                            [
                                ["Название компании", "Телефон компании", "Название сделки", "Сумма"],
                                ["ООО Альфа", "+78005550101", "Редизайн сайта", "150000"],
                            ],
                        ),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_deal_session_with_headers(self, headers, data_rows, *, filename="deal-custom.xlsx"):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.DEAL,
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
                        ("Deals", [headers, *data_rows]),
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

    def create_uploaded_task_session_with_headers(self, headers, data_rows, *, filename="tasks-custom.xlsx"):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK,
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
                        ("Tasks", [headers, *data_rows]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_linked_company_contact_session_with_custom_rows(
        self,
        rows,
        *,
        filename="linked-company-contact-repeat.xlsx",
    ):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type="linked_company_contact",
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename=filename,
        )
        session.stored_file.save(
            filename,
            SimpleUploadedFile(
                filename,
                build_xlsx_with_sheets([("Linked", rows)]),
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

    def create_uploaded_session_with_source(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads-source.xlsx",
        )
        session.stored_file.save(
            "leads-source.xlsx",
            SimpleUploadedFile(
                "leads-source.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Lead title", "Source"], ["Alice", "Реклама"]]),
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

    def create_uploaded_crm_note_session(self, rows, *, filename="crm-note.xlsx"):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type="crm_note",
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename=filename,
        )
        session.stored_file.save(
            filename,
            SimpleUploadedFile(
                filename,
                build_xlsx_with_sheets([("Notes", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_smart_process_session(self, headers, data_rows, *, filename="smart-process.xlsx"):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.SMART_PROCESS,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename=filename,
            import_settings={
                "entity_config": {
                    "entityTypeId": 128,
                    "title": "Согласования",
                }
            },
        )
        session.stored_file.save(
            filename,
            SimpleUploadedFile(
                filename,
                build_xlsx_with_sheets(
                    [
                        ("Smart", [headers, *data_rows]),
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
    def test_mapping_returns_linked_entity_metadata_for_linked_import_sessions(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_linked_company_contact_account()

        session = self.create_uploaded_linked_company_contact_session()
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
        self.assertEqual(
            response.json()["item"]["linked_entities"],
            [
                {
                    "id": "company",
                    "label": "Компания",
                    "source_entity_type": "company",
                    "prefix": "COMPANY__",
                    "excluded_source_ids": [],
                },
                {
                    "id": "contact",
                    "label": "Контакт",
                    "source_entity_type": "contact",
                    "prefix": "CONTACT__",
                    "excluded_source_ids": ["COMPANY_ID"],
                },
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_candidate_mapping_for_short_russian_linked_headers(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_linked_company_contact_account()

        session = self.create_uploaded_linked_company_contact_session_with_headers(
            ["Название", "Телефон", "Имя", "Почта"],
            [["ООО Альфа", "+78005550101", "Алиса", "alice@example.ru"]],
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
            "COMPANY__TITLE": {
                "source_header": "Название",
                "column": "A",
                "target_field": "COMPANY__TITLE",
                "match_type": "fuzzy",
            },
            "COMPANY__PHONE": {
                "source_header": "Телефон",
                "column": "B",
                "target_field": "COMPANY__PHONE",
                "match_type": "fuzzy",
            },
            "CONTACT__NAME": {
                "source_header": "Имя",
                "column": "C",
                "target_field": "CONTACT__NAME",
                "match_type": "fuzzy",
            },
            "CONTACT__EMAIL": {
                "source_header": "Почта",
                "column": "D",
                "target_field": "CONTACT__EMAIL",
                "match_type": "fuzzy",
            },
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_linked_entity_metadata_for_linked_company_deal_sessions(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_linked_company_deal_account()

        session = self.create_uploaded_linked_company_deal_session()
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
        self.assertEqual(
            response.json()["item"]["linked_entities"],
            [
                {
                    "id": "company",
                    "label": "Компания",
                    "source_entity_type": "company",
                    "prefix": "COMPANY__",
                    "excluded_source_ids": [],
                },
                {
                    "id": "deal",
                    "label": "Сделка",
                    "source_entity_type": "deal",
                    "prefix": "DEAL__",
                    "excluded_source_ids": ["COMPANY_ID"],
                },
            ],
        )

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
    def test_mapping_auto_matches_russian_deal_headers_to_generic_source_type_and_opened_fields(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_deal_account_with_generic_titles()

        session = self.create_uploaded_deal_session_with_headers(
            ["Название сделки", "Источник", "Тип сделки", "Доступна для всех"],
            [["Редизайн сайта", "Реклама", "Продажа", "Да"]],
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
                "source_header": "Название сделки",
                "column": "A",
                "target_field": "TITLE",
                "match_type": "fuzzy",
            },
            "SOURCE_ID": {
                "source_header": "Источник",
                "column": "B",
                "target_field": "SOURCE_ID",
                "match_type": "fuzzy",
            },
            "TYPE_ID": {
                "source_header": "Тип сделки",
                "column": "C",
                "target_field": "TYPE_ID",
                "match_type": "fuzzy",
            },
            "OPENED": {
                "source_header": "Доступна для всех",
                "column": "D",
                "target_field": "OPENED",
                "match_type": "fuzzy",
            },
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_candidate_suggestions_and_match_reasons_for_transliterated_headers(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_headers(
            ["Nazvanie", "Telefon", "Gorod"],
            [["Alice", "+123", "Moscow"]],
            filename="leads-translit.xlsx",
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
                "source_header": "Nazvanie",
                "column": "A",
                "target_field": "TITLE",
                "match_type": "fuzzy",
                "match_reason": "translit_alias",
            },
            "PHONE": {
                "source_header": "Telefon",
                "column": "B",
                "target_field": "PHONE",
                "match_type": "fuzzy",
                "match_reason": "translit_alias",
            },
            "UF_CRM_CITY": {
                "source_header": "Gorod",
                "column": "C",
                "target_field": "UF_CRM_CITY",
                "match_type": "fuzzy",
                "match_reason": "translit_alias",
            },
        })
        self.assertEqual(response.json()["item"]["candidate_suggestions"], {
            "A:Nazvanie": [
                {
                    "target_field": "TITLE",
                    "target_field_title": "Lead title",
                    "match_type": "fuzzy",
                    "match_reason": "translit_alias",
                },
            ],
            "B:Telefon": [
                {
                    "target_field": "PHONE",
                    "target_field_title": "Phone",
                    "match_type": "fuzzy",
                    "match_reason": "translit_alias",
                },
            ],
            "C:Gorod": [
                {
                    "target_field": "UF_CRM_CITY",
                    "target_field_title": "City",
                    "match_type": "fuzzy",
                    "match_reason": "translit_alias",
                },
            ],
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_auto_matches_task_headers_and_ignores_internal_task_fields(self, get_from_jwt_token):
        def get_users(*, filter=None, select=None):
            return FakeUsersRequest([])

        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        getFields=lambda: FakeFieldsRequest(
                            {
                                "fields": {
                                    "TITLE": {
                                        "title": "Title",
                                        "type": "string",
                                        "required": True,
                                    },
                                    "RESPONSIBLE_ID": {
                                        "title": "Responsible",
                                        "type": "integer",
                                        "required": True,
                                    },
                                    "isPinned": {
                                        "title": "Is pinned",
                                        "type": "boolean",
                                    },
                                }
                            }
                        )
                    )
                ),
                user=SimpleNamespace(
                    get=get_users,
                ),
            ),
        )

        session = self.create_uploaded_task_session_with_headers(
            ["Task title", "Responsible"],
            [["Подготовить КП", "59"]],
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

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["item"]["candidate_mapping"],
            {
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                    "target_field": "TITLE",
                    "match_type": "fuzzy",
                },
                "RESPONSIBLE_ID": {
                    "source_header": "Responsible",
                    "column": "B",
                    "target_field": "RESPONSIBLE_ID",
                    "match_type": "exact",
                },
            },
        )
        field_ids = {
            item["id"]
            for item in response.json()["item"]["fields"]
        }
        self.assertNotIn("isPinned", field_ids)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_applies_saved_alias_rule_to_candidate_mapping(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_headers(
            ["Контрагент", "Телефон"],
            [["ООО Альфа", "+123"]],
            filename="leads-alias.xlsx",
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        create_rule_response = self.client.post(
            reverse("importer:alias-rules"),
            data={
                "session_id": str(session.id),
                "source_label": "Контрагент",
                "target_field_id": "TITLE",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(create_rule_response.status_code, 201)
        self.assertEqual(create_rule_response.json()["item"]["source_label"], "Контрагент")
        self.assertEqual(create_rule_response.json()["item"]["target_field_id"], "TITLE")

        list_response = self.client.get(
            f"{reverse('importer:alias-rules')}?entity_type=lead",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["items"]), 1)

        response = self.client.get(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["candidate_mapping"]["TITLE"], {
            "source_header": "Контрагент",
            "column": "A",
            "target_field": "TITLE",
            "match_type": "alias",
            "match_reason": "alias_rule",
        })
        self.assertEqual(response.json()["item"]["alias_rules"], [
            {
                "id": create_rule_response.json()["item"]["id"],
                "source_label": "Контрагент",
                "target_field_id": "TITLE",
                "target_field_title": "Lead title",
            },
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_linked_preflight_warning_for_repeated_company_rows_without_identity_strategy(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_linked_company_contact_account()

        session = self.create_uploaded_linked_company_contact_session_with_custom_rows(
            [
                ["Название компании", "Имя контакта"],
                ["ООО Альфа", "Алиса"],
                ["ООО Альфа", "Боб"],
            ],
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "COMPANY__TITLE": {
                        "source_header": "Название компании",
                        "column": "A",
                    },
                    "CONTACT__NAME": {
                        "source_header": "Имя контакта",
                        "column": "B",
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["preflight"], {
            "blocking_issue_count": 0,
            "warning_count": 1,
            "issues": [
                {
                    "code": "linked_company_identity_missing",
                    "severity": "warning",
                    "entity": "company",
                    "row_count": 2,
                },
            ],
        })

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_preflight_error_for_unmapped_stage_values(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session_with_exact_and_unknown_stage_values()
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
                    "STAGE_ID": {
                        "source_header": "Stage",
                        "column": "B",
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["preflight"], {
            "blocking_issue_count": 1,
            "warning_count": 0,
            "issues": [
                {
                    "code": "field_values_unmapped",
                    "severity": "error",
                    "field_id": "STAGE_ID",
                    "value_count": 1,
                    "values": ["Paused"],
                },
            ],
        })

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_returns_preflight_error_when_smart_process_status_field_has_no_options(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = self.create_account()
        bitrix_api_request.side_effect = [
            SimpleNamespace(
                result={
                    "title": {
                        "title": "Название",
                        "type": "string",
                        "isRequired": True,
                        "isReadOnly": False,
                        "upperName": "TITLE",
                    },
                    "sourceId": {
                        "title": "Источник",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "SOURCE_ID",
                        "settings": {
                            "statusType": "SOURCE",
                        },
                    },
                }
            ),
            SimpleNamespace(result={"statuses": []}),
            SimpleNamespace(
                result={
                    "title": {
                        "title": "Название",
                        "type": "string",
                        "isRequired": True,
                        "isReadOnly": False,
                        "upperName": "TITLE",
                    },
                    "sourceId": {
                        "title": "Источник",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "SOURCE_ID",
                        "settings": {
                            "statusType": "SOURCE",
                        },
                    },
                }
            ),
            SimpleNamespace(result={"statuses": []}),
        ]

        session = self.create_uploaded_smart_process_session(
            ["Название", "Источник"],
            [["Согласование 1", "Реклама"]],
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "title": {
                        "source_header": "Название",
                        "column": "A",
                    },
                    "sourceId": {
                        "source_header": "Источник",
                        "column": "B",
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["preflight"], {
            "blocking_issue_count": 1,
            "warning_count": 0,
            "issues": [
                {
                    "code": "field_options_unavailable",
                    "severity": "error",
                    "field_id": "sourceId",
                    "value_count": 1,
                    "values": ["Реклама"],
                },
            ],
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
            "condition": "any",
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
            "condition": "any",
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
        self.assertEqual(len(preview_response.json()["item"]["preview_rows"]), 12)

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
    def test_mapping_treats_nested_bitrix_list_items_as_exact_matches(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account_with_nested_source_items()

        session = self.create_uploaded_session_with_source()
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
                    "SOURCE_ID": {
                        "source_header": "Source",
                        "column": "B",
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(mapping_response.status_code, 200)
        self.assertEqual(mapping_response.json()["item"]["observed_values"], {
            "SOURCE_ID": ["Реклама"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_values"], {})
        self.assertEqual(mapping_response.json()["item"]["unmapped_value_count"], 0)
        self.assertEqual(
            next(field for field in mapping_response.json()["item"]["fields"] if field["id"] == "SOURCE_ID")["items"],
            [
                {"id": "SALE", "title": "Продажа"},
                {"id": "ADVERTISING", "title": "Реклама"},
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_treats_status_alias_values_as_already_resolved(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account_with_nested_source_items()

        session = self.create_uploaded_session_with_headers(
            ["Lead title", "Source"],
            [["Alice", " advertising "]],
            filename="leads-source-alias.xlsx",
        )
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
                    "SOURCE_ID": {
                        "source_header": "Source",
                        "column": "B",
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(mapping_response.status_code, 200)
        self.assertEqual(mapping_response.json()["item"]["observed_values"], {
            "SOURCE_ID": ["advertising"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_values"], {})
        self.assertEqual(mapping_response.json()["item"]["unmapped_value_count"], 0)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_treats_exact_crm_note_entity_types_as_already_resolved(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_crm_note_session(
            [
                ["Тип сущности CRM", "ID записи CRM", "Текст заметки"],
                ["Контакт", "101", "Клиент заинтересован"],
                ["Сделка", "55", "Договор согласован"],
                ["Партнер", "77", "Неизвестный тип"],
            ]
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "ENTITY_TYPE": {
                        "source_header": "Тип сущности CRM",
                        "column": "A",
                    },
                    "ENTITY_ID": {
                        "source_header": "ID записи CRM",
                        "column": "B",
                    },
                    "COMMENT": {
                        "source_header": "Текст заметки",
                        "column": "C",
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(mapping_response.status_code, 200)
        self.assertEqual(mapping_response.json()["item"]["observed_values"], {
            "ENTITY_TYPE": ["Контакт", "Сделка", "Партнер"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_values"], {
            "ENTITY_TYPE": ["Партнер"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_value_count"], 1)

    @patch("importer.services.b24_fields.BitrixAPIRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_mapping_treats_smart_process_source_status_values_as_already_resolved(self, get_from_jwt_token, bitrix_api_request):
        get_from_jwt_token.return_value = self.create_account()
        bitrix_api_request.side_effect = [
            SimpleNamespace(
                result={
                    "title": {
                        "title": "Название",
                        "type": "string",
                        "isRequired": True,
                        "isReadOnly": False,
                        "upperName": "TITLE",
                    },
                    "sourceId": {
                        "title": "Источник",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "SOURCE_ID",
                        "settings": {
                            "statusType": "SOURCE",
                        },
                    },
                }
            ),
            SimpleNamespace(
                result={
                    "statuses": [
                        {
                            "ENTITY_ID": "SOURCE",
                            "STATUS_ID": "OTHER",
                            "NAME": "Другое",
                        },
                        {
                            "ENTITY_ID": "SOURCE",
                            "STATUS_ID": "ADVERTISING",
                            "NAME": "Реклама",
                        },
                    ]
                }
            ),
            SimpleNamespace(
                result={
                    "title": {
                        "title": "Название",
                        "type": "string",
                        "isRequired": True,
                        "isReadOnly": False,
                        "upperName": "TITLE",
                    },
                    "sourceId": {
                        "title": "Источник",
                        "type": "crm_status",
                        "isRequired": False,
                        "isReadOnly": False,
                        "upperName": "SOURCE_ID",
                        "settings": {
                            "statusType": "SOURCE",
                        },
                    },
                }
            ),
            SimpleNamespace(
                result={
                    "statuses": [
                        {
                            "ENTITY_ID": "SOURCE",
                            "STATUS_ID": "OTHER",
                            "NAME": "Другое",
                        },
                        {
                            "ENTITY_ID": "SOURCE",
                            "STATUS_ID": "ADVERTISING",
                            "NAME": "Реклама",
                        },
                    ]
                }
            ),
        ]

        session = self.create_uploaded_smart_process_session(
            ["Название", "Источник"],
            [["Согласование 1", "другое"]],
        )
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "title": {
                        "source_header": "Название",
                        "column": "A",
                    },
                    "sourceId": {
                        "source_header": "Источник",
                        "column": "B",
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(mapping_response.status_code, 200)
        self.assertEqual(mapping_response.json()["item"]["observed_values"], {
            "sourceId": ["другое"],
        })
        self.assertEqual(mapping_response.json()["item"]["unmapped_values"], {})
        self.assertEqual(mapping_response.json()["item"]["unmapped_value_count"], 0)
        self.assertEqual(
            next(field for field in mapping_response.json()["item"]["fields"] if field["id"] == "sourceId")["items"],
            [
                {"id": "OTHER", "title": "Другое"},
                {"id": "ADVERTISING", "title": "Реклама"},
            ],
        )

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
    def test_task_mapping_returns_default_creator_options_and_persists_selection(self, get_from_jwt_token):
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
                "default_creator_id": "73",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["task_defaults"], {
            "default_creator_id": "73",
        })
        self.assertEqual(response.json()["item"]["task_user_options"], [
            {"value": "59", "label": "Alice Owner · alice@example.com · ID 59"},
            {"value": "73", "label": "Bob Manager · bob@example.com · ID 73"},
        ])

        session.refresh_from_db()
        self.assertEqual(session.import_settings["task_defaults"], {
            "default_creator_id": "73",
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
