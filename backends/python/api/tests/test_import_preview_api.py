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


def build_xlsx_with_shared_strings(rows):
    shared_string_values = []
    shared_string_index = {}

    def get_shared_string_index(value):
        key = str(value)
        if key not in shared_string_index:
            shared_string_index[key] = len(shared_string_values)
            shared_string_values.append(key)
        return shared_string_index[key]

    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells_xml = []
        for column_index, value in enumerate(row, start=1):
            column_letter = chr(64 + column_index)
            cell_ref = f"{column_letter}{row_index}"

            if isinstance(value, str):
                cells_xml.append(
                    f'<c r="{cell_ref}" t="s"><v>{get_shared_string_index(value)}</v></c>'
                )
            else:
                cells_xml.append(
                    f'<c r="{cell_ref}"><v>{escape(str(value))}</v></c>'
                )
        row_xml.append(f'<row r="{row_index}">{"".join(cells_xml)}</row>')

    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {rows}
  </sheetData>
</worksheet>
""".format(rows="".join(row_xml))

    shared_strings_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{count}" uniqueCount="{count}">
{items}
</sst>
""".format(
        count=len(shared_string_values),
        items="".join(f"<si><t>{escape(value)}</t></si>" for value in shared_string_values),
    )

    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/sharedStrings.xml", shared_strings_xml)

    return buffer.getvalue()


class ImportPreviewApiTest(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_returns_sheet_names_from_uploaded_xlsx(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

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
                        ("Leads", [["Name", "Phone"], ["Alice", "+123"]]),
                        ("Companies", [["", ""], ["Company", "Owner"], ["Acme", "Bob"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["sheet_names"], ["Leads", "Companies"])
        self.assertEqual(response.json()["item"]["selected_sheet_name"], "Leads")
        self.assertEqual(response.json()["item"]["columns"], ["A", "B"])
        self.assertEqual(response.json()["item"]["header_row"], 1)
        self.assertEqual(response.json()["item"]["data_start_row"], 2)
        self.assertEqual(response.json()["item"]["headers"], ["Name", "Phone"])
        self.assertEqual(
            response.json()["item"]["preview_rows"],
            [["Name", "Phone"], ["Alice", "+123"]],
        )

        session.refresh_from_db()
        self.assertEqual(session.source_sheet_name, "Leads")
        self.assertEqual(session.header_row, 1)
        self.assertEqual(session.data_start_row, 2)
        self.assertEqual(session.preview_data["sheet_names"], ["Leads", "Companies"])
        self.assertEqual(session.preview_data["columns"], ["A", "B"])
        self.assertEqual(session.preview_data["header_row"], 1)
        self.assertEqual(session.preview_data["data_start_row"], 2)
        self.assertEqual(session.preview_data["headers"], ["Name", "Phone"])
        self.assertEqual(
            session.preview_data["preview_rows"],
            [["Name", "Phone"], ["Alice", "+123"]],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_reads_shared_strings_from_real_excel_xlsx(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="book.xlsx",
        )
        session.stored_file.save(
            "book.xlsx",
            SimpleUploadedFile(
                "book.xlsx",
                build_xlsx_with_shared_strings(
                    [
                        ["Имя", "Фамилия", "Телефон"],
                        ["Петя", "Петькин", 89778383838],
                        ["Галя", "Кальнина", 9876464634],
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["columns"], ["A", "B", "C"])
        self.assertEqual(response.json()["item"]["header_row"], 1)
        self.assertEqual(response.json()["item"]["data_start_row"], 2)
        self.assertEqual(response.json()["item"]["headers"], ["Имя", "Фамилия", "Телефон"])
        self.assertEqual(
            response.json()["item"]["preview_rows"],
            [
                ["Имя", "Фамилия", "Телефон"],
                ["Петя", "Петькин", "89778383838"],
                ["Галя", "Кальнина", "9876464634"],
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_allows_selecting_specific_sheet(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

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
                        ("Leads", [["Name", "Phone"], ["Alice", "+123"]]),
                        ("Companies", [["", ""], ["Company", "Owner"], ["Acme", "Bob"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            data={"sheet_name": "Companies"},
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["selected_sheet_name"], "Companies")
        self.assertEqual(response.json()["item"]["columns"], ["A", "B"])
        self.assertEqual(response.json()["item"]["header_row"], 2)
        self.assertEqual(response.json()["item"]["data_start_row"], 3)
        self.assertEqual(response.json()["item"]["headers"], ["Company", "Owner"])
        self.assertEqual(
            response.json()["item"]["preview_rows"],
            [["", ""], ["Company", "Owner"], ["Acme", "Bob"]],
        )

        session.refresh_from_db()
        self.assertEqual(session.source_sheet_name, "Companies")
        self.assertEqual(session.header_row, 2)
        self.assertEqual(session.data_start_row, 3)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_returns_rows_for_uploaded_csv(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.CSV,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads.csv",
        )
        session.stored_file.save(
            "leads.csv",
            SimpleUploadedFile(
                "leads.csv",
                b"Name,Phone\nAlice,+123\nBob,+456\n",
                content_type="text/csv",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["sheet_names"], ["CSV"])
        self.assertEqual(response.json()["item"]["selected_sheet_name"], "CSV")
        self.assertEqual(response.json()["item"]["columns"], ["A", "B"])
        self.assertEqual(response.json()["item"]["header_row"], 1)
        self.assertEqual(response.json()["item"]["data_start_row"], 2)
        self.assertEqual(response.json()["item"]["headers"], ["Name", "Phone"])
        self.assertEqual(
            response.json()["item"]["preview_rows"],
            [["Name", "Phone"], ["Alice", "+123"], ["Bob", "+456"]],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_splits_single_cell_xlsx_rows_by_comma(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads-comma.xlsx",
        )
        session.stored_file.save(
            "leads-comma.xlsx",
            SimpleUploadedFile(
                "leads-comma.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Name,Phone,City"], ["Alice,+123,Moscow"], ["Bob,+456,Samara"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["columns"], ["A", "B", "C"])
        self.assertEqual(response.json()["item"]["headers"], ["Name", "Phone", "City"])
        self.assertEqual(
            response.json()["item"]["preview_rows"],
            [
                ["Name", "Phone", "City"],
                ["Alice", "+123", "Moscow"],
                ["Bob", "+456", "Samara"],
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_splits_single_cell_xlsx_rows_by_semicolon(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads-semicolon.xlsx",
        )
        session.stored_file.save(
            "leads-semicolon.xlsx",
            SimpleUploadedFile(
                "leads-semicolon.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Name;Phone;City"], ["Alice;+123;Moscow"], ["Bob;+456;Samara"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["columns"], ["A", "B", "C"])
        self.assertEqual(response.json()["item"]["headers"], ["Name", "Phone", "City"])
        self.assertEqual(
            response.json()["item"]["preview_rows"],
            [
                ["Name", "Phone", "City"],
                ["Alice", "+123", "Moscow"],
                ["Bob", "+456", "Samara"],
            ],
        )

    @patch("importer.views.MAX_IMPORT_ROWS", 2)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_returns_row_limit_warning_when_file_has_too_many_data_rows(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="too-many-rows.xlsx",
        )
        session.stored_file.save(
            "too-many-rows.xlsx",
            SimpleUploadedFile(
                "too-many-rows.xlsx",
                build_xlsx_with_sheets(
                    [
                        ("Leads", [["Name", "Phone"], ["Alice", "+123"], ["Bob", "+456"], ["Carol", "+789"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["total_rows"], 3)
        self.assertEqual(response.json()["item"]["max_import_rows"], 2)
        self.assertEqual(response.json()["item"]["row_limit_exceeded"], True)
        self.assertEqual(
            response.json()["item"]["row_limit_error"],
            "Файл содержит слишком много строк данных (3). Максимум: 2 строк за один импорт.",
        )

        session.refresh_from_db()
        self.assertEqual(session.total_rows, 3)
        self.assertEqual(session.preview_data["total_rows"], 3)
        self.assertEqual(session.preview_data["max_import_rows"], 2)
        self.assertEqual(session.preview_data["row_limit_exceeded"], True)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_requires_uploaded_file(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="draft.xlsx",
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Uploaded file is required")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_is_limited_to_current_portal_session(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-2",
            portal_domain="other.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="other.xlsx",
        )
        session.stored_file.save(
            "other.xlsx",
            SimpleUploadedFile(
                "other.xlsx",
                build_xlsx_with_sheets([("Other", [["Only"]])]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 404)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_allows_manual_structure_override(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

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
                        ("Leads", [["ignore", "ignore"], ["Name", "Phone"], ["Alice", "+123"]]),
                    ]
                ),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        response = self.client.patch(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            data={
                "header_row": 2,
                "data_start_row": 3,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["header_row"], 2)
        self.assertEqual(response.json()["item"]["data_start_row"], 3)
        self.assertEqual(response.json()["item"]["headers"], ["Name", "Phone"])

        session.refresh_from_db()
        self.assertEqual(session.header_row, 2)
        self.assertEqual(session.data_start_row, 3)
        self.assertEqual(session.preview_data["headers"], ["Name", "Phone"])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_rejects_invalid_manual_structure_override(self, get_from_jwt_token):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )

        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.CSV,
            status=ImportSession.Status.UPLOADED,
            original_filename="leads.csv",
        )
        session.stored_file.save(
            "leads.csv",
            SimpleUploadedFile(
                "leads.csv",
                b"Name,Phone\nAlice,+123\n",
                content_type="text/csv",
            ),
        )

        response = self.client.patch(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            data={
                "header_row": 2,
                "data_start_row": 2,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Data start row must be greater than header row")
