import itertools
import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

import requests
from b24pysdk.error import BitrixRequestTimeout
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from kombu.exceptions import OperationalError as KombuOperationalError

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


class FakeUpdateRequest:
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


class ImportExecutionApiTest(TestCase):
    def setUp(self):
        super().setUp()
        self.queue_env_override = patch.dict("os.environ", {"ENABLE_RABBITMQ": "0"}, clear=False)
        self.queue_env_override.start()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.queue_env_override.stop()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def _strip_report_meta(self, results):
        skip = {"report_date_time", "report_entity", "report_record_id", "report_title"}
        return [{k: v for k, v in r.items() if k not in skip} for r in results]

    def create_account(
        self,
        *,
        member_id="member-1",
        domain_url="test.bitrix24.ru",
        fail_on_titles=None,
        duplicates_by_filter=None,
    ):
        fail_on_titles = set(fail_on_titles or [])
        duplicates_by_filter = duplicates_by_filter or {}
        created_fields = []
        updated_records = []
        list_calls = []
        record_id_sequence = itertools.count(start=501)

        def add(fields, *, params=None, timeout=None):
            normalized_fields = dict(fields)
            created_fields.append(normalized_fields)
            if normalized_fields.get("TITLE") in fail_on_titles:
                raise RuntimeError(f'Bitrix create failed for "{normalized_fields.get("TITLE")}"')
            return FakeAddRequest(next(record_id_sequence))

        def list_method(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            list_calls.append(
                {
                    "filter": dict(filter or {}),
                    "select": list(select or []),
                }
            )
            return FakeListRequest(duplicates_by_filter.get(normalized_filter, []))

        def update(record_id, fields, *, params=None, timeout=None):
            normalized_fields = dict(fields)
            updated_records.append(
                {
                    "id": record_id,
                    "fields": normalized_fields,
                }
            )
            return FakeUpdateRequest(True)

        account = SimpleNamespace(
            id=f"account-{member_id}-{domain_url}",
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
                            }
                        ),
                        list=list_method,
                        update=update,
                        add=add,
                    )
                )
            ),
        )
        account.created_fields = created_fields
        account.updated_records = updated_records
        account.list_calls = list_calls
        return account

    def create_contact_account(self, *, member_id="member-1", domain_url="test.bitrix24.ru"):
        created_fields = []
        record_id_sequence = itertools.count(start=701)

        def add(fields, *, params=None, timeout=None):
            normalized_fields = dict(fields)
            created_fields.append(normalized_fields)
            return FakeAddRequest(next(record_id_sequence))

        account = SimpleNamespace(
            id=f"account-{member_id}-{domain_url}",
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                crm=SimpleNamespace(
                    contact=SimpleNamespace(
                        fields=lambda: FakeFieldsRequest(
                            {
                                "NAME": {
                                    "title": "First name",
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
                            }
                        ),
                        add=add,
                    )
                )
            ),
        )
        account.created_fields = created_fields
        return account

    def create_task_account(
        self,
        *,
        member_id="member-1",
        domain_url="test.bitrix24.ru",
        user_results_by_filter=None,
        task_results_by_filter=None,
    ):
        created_fields = []
        user_lookup_calls = []
        task_lookup_calls = []
        record_id_sequence = itertools.count(start=801)
        user_results_by_filter = user_results_by_filter or {}
        task_results_by_filter = task_results_by_filter or {}

        def add(fields, *, params=None, timeout=None):
            normalized_fields = dict(fields)
            created_fields.append(normalized_fields)
            return FakeAddRequest(next(record_id_sequence))

        def get_users(*, filter=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            user_lookup_calls.append(dict(filter or {}))
            return FakeUsersRequest(user_results_by_filter.get(normalized_filter, []))

        def list_tasks(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            task_lookup_calls.append(
                {
                    "filter": dict(filter or {}),
                    "select": list(select or []),
                }
            )
            return FakeListRequest(task_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            id=f"account-{member_id}-{domain_url}",
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=get_users,
                ),
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        add=add,
                        list=list_tasks,
                    )
                )
            ),
        )
        account.created_fields = created_fields
        account.user_lookup_calls = user_lookup_calls
        account.task_lookup_calls = task_lookup_calls
        return account

    def create_uploaded_session(self, rows):
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
                build_xlsx_with_sheets([("Leads", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_contact_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.CONTACT,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="contacts.xlsx",
        )
        session.stored_file.save(
            "contacts.xlsx",
            SimpleUploadedFile(
                "contacts.xlsx",
                build_xlsx_with_sheets([("Contacts", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_task_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="tasks.xlsx",
        )
        session.stored_file.save(
            "tasks.xlsx",
            SimpleUploadedFile(
                "tasks.xlsx",
                build_xlsx_with_sheets([("Tasks", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_linked_company_contact_session(self, rows):
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
                build_xlsx_with_sheets([("Linked", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_linked_company_deal_session(self, rows):
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
                build_xlsx_with_sheets([("Linked", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_crm_activity_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.CRM_ACTIVITY,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="crm-activity.xlsx",
        )
        session.stored_file.save(
            "crm-activity.xlsx",
            SimpleUploadedFile(
                "crm-activity.xlsx",
                build_xlsx_with_sheets([("Activities", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_crm_note_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.CRM_NOTE,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="crm-note.xlsx",
        )
        session.stored_file.save(
            "crm-note.xlsx",
            SimpleUploadedFile(
                "crm-note.xlsx",
                build_xlsx_with_sheets([("Notes", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_task_comment_account(self, *, member_id="member-1", domain_url="test.bitrix24.ru", user_results_by_filter=None):
        chat_message_calls = []
        record_id_sequence = itertools.count(start=4001)
        user_results_by_filter = user_results_by_filter or {}

        def send(fields, *, params=None, timeout=None):
            chat_message_calls.append(
                {
                    "fields": dict(fields),
                }
            )
            return FakeAddRequest(next(record_id_sequence))

        def get_users(*, filter=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            return FakeUsersRequest(user_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=get_users,
                ),
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        chat=SimpleNamespace(
                            message=SimpleNamespace(
                                send=send,
                            )
                        )
                    )
                ),
            ),
        )
        account.chat_message_calls = chat_message_calls
        return account

    def create_task_checklist_account(self, *, member_id="member-1", domain_url="test.bitrix24.ru"):
        checklist_calls = []
        record_id_sequence = itertools.count(start=5001)

        def add(task_id, fields, *, params=None, timeout=None):
            checklist_calls.append(
                {
                    "task_id": task_id,
                    "fields": dict(fields),
                }
            )
            return FakeAddRequest(next(record_id_sequence))

        account = SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    checklistitem=SimpleNamespace(
                        add=add,
                    )
                ),
            ),
        )
        account.checklist_calls = checklist_calls
        return account

    def create_linked_company_contact_account(
        self,
        *,
        member_id="member-1",
        domain_url="test.bitrix24.ru",
        company_duplicates_by_filter=None,
        contact_duplicates_by_filter=None,
    ):
        company_created_fields = []
        contact_created_fields = []
        company_updated_records = []
        contact_updated_records = []
        company_list_calls = []
        contact_list_calls = []
        company_record_id_sequence = itertools.count(start=601)
        contact_record_id_sequence = itertools.count(start=701)
        company_duplicates_by_filter = company_duplicates_by_filter or {}
        contact_duplicates_by_filter = contact_duplicates_by_filter or {}

        def company_add(fields, *, params=None, timeout=None):
            normalized_fields = dict(fields)
            company_created_fields.append(normalized_fields)
            return FakeAddRequest(next(company_record_id_sequence))

        def contact_add(fields, *, params=None, timeout=None):
            normalized_fields = dict(fields)
            contact_created_fields.append(normalized_fields)
            return FakeAddRequest(next(contact_record_id_sequence))

        def company_list(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            company_list_calls.append(
                {
                    "filter": dict(filter or {}),
                    "select": list(select or []),
                }
            )
            return FakeListRequest(company_duplicates_by_filter.get(normalized_filter, []))

        def contact_list(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            contact_list_calls.append(
                {
                    "filter": dict(filter or {}),
                    "select": list(select or []),
                }
            )
            return FakeListRequest(contact_duplicates_by_filter.get(normalized_filter, []))

        def company_update(record_id, fields, *, params=None, timeout=None):
            company_updated_records.append(
                {
                    "id": record_id,
                    "fields": dict(fields),
                }
            )
            return FakeUpdateRequest(True)

        def contact_update(record_id, fields, *, params=None, timeout=None):
            contact_updated_records.append(
                {
                    "id": record_id,
                    "fields": dict(fields),
                }
            )
            return FakeUpdateRequest(True)

        account = SimpleNamespace(
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
                                "EMAIL": {
                                    "title": "Email компании",
                                    "type": "email",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                            }
                        ),
                        add=company_add,
                        list=company_list,
                        update=company_update,
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
                                "LAST_NAME": {
                                    "title": "Фамилия контакта",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "PHONE": {
                                    "title": "Телефон контакта",
                                    "type": "phone",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                                "EMAIL": {
                                    "title": "Email контакта",
                                    "type": "email",
                                    "isRequired": False,
                                    "isMultiple": True,
                                },
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        ),
                        add=contact_add,
                        list=contact_list,
                        update=contact_update,
                    ),
                )
            ),
        )
        account.company_created_fields = company_created_fields
        account.contact_created_fields = contact_created_fields
        account.company_updated_records = company_updated_records
        account.contact_updated_records = contact_updated_records
        account.company_list_calls = company_list_calls
        account.contact_list_calls = contact_list_calls
        return account

    def create_linked_company_deal_account(
        self,
        *,
        member_id="member-1",
        domain_url="test.bitrix24.ru",
        company_duplicates_by_filter=None,
        deal_duplicates_by_filter=None,
    ):
        company_created_fields = []
        deal_created_fields = []
        company_updated_records = []
        deal_updated_records = []
        company_list_calls = []
        deal_list_calls = []
        company_record_id_sequence = itertools.count(start=601)
        deal_record_id_sequence = itertools.count(start=801)
        company_duplicates_by_filter = company_duplicates_by_filter or {}
        deal_duplicates_by_filter = deal_duplicates_by_filter or {}

        def company_add(fields, *, params=None, timeout=None):
            company_created_fields.append(dict(fields))
            return FakeAddRequest(next(company_record_id_sequence))

        def deal_add(fields, *, params=None, timeout=None):
            deal_created_fields.append(dict(fields))
            return FakeAddRequest(next(deal_record_id_sequence))

        def company_list(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            company_list_calls.append({"filter": dict(filter or {}), "select": list(select or [])})
            return FakeListRequest(company_duplicates_by_filter.get(normalized_filter, []))

        def deal_list(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            deal_list_calls.append({"filter": dict(filter or {}), "select": list(select or [])})
            return FakeListRequest(deal_duplicates_by_filter.get(normalized_filter, []))

        def company_update(record_id, fields, *, params=None, timeout=None):
            company_updated_records.append({"id": record_id, "fields": dict(fields)})
            return FakeUpdateRequest(True)

        def deal_update(record_id, fields, *, params=None, timeout=None):
            deal_updated_records.append({"id": record_id, "fields": dict(fields)})
            return FakeUpdateRequest(True)

        account = SimpleNamespace(
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
                        ),
                        add=company_add,
                        list=company_list,
                        update=company_update,
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
                                "CURRENCY_ID": {
                                    "title": "Валюта",
                                    "type": "string",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                                "STAGE_ID": {
                                    "title": "Стадия",
                                    "type": "crm_status",
                                    "isRequired": False,
                                    "isMultiple": False,
                                    "items": {
                                        "NEW": "Новая",
                                        "IN_PROGRESS": "В работе",
                                    },
                                },
                                "COMPANY_ID": {
                                    "title": "Компания",
                                    "type": "integer",
                                    "isRequired": False,
                                    "isMultiple": False,
                                },
                            }
                        ),
                        add=deal_add,
                        list=deal_list,
                        update=deal_update,
                    ),
                )
            ),
        )
        account.company_created_fields = company_created_fields
        account.deal_created_fields = deal_created_fields
        account.company_updated_records = company_updated_records
        account.deal_updated_records = deal_updated_records
        account.company_list_calls = company_list_calls
        account.deal_list_calls = deal_list_calls
        return account

    def create_uploaded_task_comment_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK_COMMENT,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="comments.xlsx",
        )
        session.stored_file.save(
            "comments.xlsx",
            SimpleUploadedFile(
                "comments.xlsx",
                build_xlsx_with_sheets([("Comments", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_task_checklist_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK_CHECKLIST_ITEM,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="checklist.xlsx",
        )
        session.stored_file.save(
            "checklist.xlsx",
            SimpleUploadedFile(
                "checklist.xlsx",
                build_xlsx_with_sheets([("Checklist", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def create_uploaded_task_attachment_session(self, rows):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.TASK_ATTACHMENT,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.UPLOADED,
            original_filename="attachments.xlsx",
        )
        session.stored_file.save(
            "attachments.xlsx",
            SimpleUploadedFile(
                "attachments.xlsx",
                build_xlsx_with_sheets([("Attachments", rows)]),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        return session

    def prepare_session(self, session, *, validate=True):
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

    def prepare_task_session(self, session, *, validate=True, mapping=None):
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
                        "source_header": "Task title",
                        "column": "A",
                    },
                    "RESPONSIBLE_ID": {
                        "source_header": "Responsible",
                        "column": "B",
                    },
                    "ACCOMPLICES": {
                        "source_header": "Accomplices",
                        "column": "C",
                    },
                    "AUDITORS": {
                        "source_header": "Auditors",
                        "column": "D",
                    },
                    "DEADLINE": {
                        "source_header": "Deadline",
                        "column": "E",
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

    def prepare_custom_mapping_session(self, session, mapping, *, validate=True):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={"mapping": mapping},
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

    def prepare_linked_company_contact_session(self, session, *, validate=True, dedup=None):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "COMPANY__TITLE": {
                        "source_header": "Название компании",
                        "column": "A",
                    },
                    "COMPANY__PHONE": {
                        "source_header": "Телефон компании",
                        "column": "B",
                    },
                    "CONTACT__NAME": {
                        "source_header": "Имя контакта",
                        "column": "C",
                    },
                    "CONTACT__LAST_NAME": {
                        "source_header": "Фамилия контакта",
                        "column": "D",
                    },
                    "CONTACT__EMAIL": {
                        "source_header": "Email контакта",
                        "column": "E",
                    },
                },
                "dedup": dedup or {
                    "company": {
                        "strategy": "create",
                        "fields": [],
                    },
                    "contact": {
                        "strategy": "create",
                        "fields": [],
                    },
                },
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

    def prepare_linked_company_deal_session(self, session, *, validate=True, dedup=None):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "COMPANY__TITLE": {
                        "source_header": "Название компании",
                        "column": "A",
                    },
                    "COMPANY__PHONE": {
                        "source_header": "Телефон компании",
                        "column": "B",
                    },
                    "DEAL__TITLE": {
                        "source_header": "Название сделки",
                        "column": "C",
                    },
                    "DEAL__OPPORTUNITY": {
                        "source_header": "Сумма",
                        "column": "D",
                    },
                    "DEAL__CURRENCY_ID": {
                        "source_header": "Валюта",
                        "column": "E",
                    },
                    "DEAL__STAGE_ID": {
                        "source_header": "Стадия",
                        "column": "F",
                    },
                },
                "dedup": dedup or {
                    "company": {
                        "strategy": "create",
                        "fields": [],
                    },
                    "deal": {
                        "strategy": "create",
                        "fields": [],
                    },
                },
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

    def prepare_task_attachment_session(self, session, *, validate=True):
        preview_response = self.client.get(
            reverse("importer:session-preview", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(preview_response.status_code, 200)

        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={
                "mapping": {
                    "TASK_ID": {"source_header": "Task", "column": "A"},
                    "FILE_URL": {"source_header": "URL", "column": "B"},
                    "FILE_NAME": {"source_header": "Name", "column": "C"},
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

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_only_rows_without_validation_issues(self, get_from_jwt_token, _batch):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["", "broken-email", "12"],
            ]
        )
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["checked_rows"], 2)
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["failed_rows"], 1)
        self.assertEqual(response.json()["item"]["skipped_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [501])
        self.assertEqual(
            self._strip_report_meta(response.json()["item"]["results"]),
            [
                {
                    "row_number": 2,
                    "status": "created",
                    "record_id": 501,
                },
                {
                    "row_number": 3,
                    "status": "skipped",
                    "error": "Row has validation issues",
                },
            ],
        )
        self.assertEqual(
            account.created_fields,
            [
                {
                    "TITLE": "Alice",
                    "EMAIL": "alice@example.com",
                    "PHONE": "+123456789",
                }
            ],
        )

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.COMPLETED)
        self.assertEqual(session.processed_rows, 2)
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(session.failed_rows, 1)
        self.assertEqual(session.summary["import_run"]["created_rows"], 1)
        self.assertEqual(session.summary["import_run"]["skipped_rows"], 1)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_continues_after_bitrix_error_and_records_failed_row(self, get_from_jwt_token, _batch):
        account = self.create_account(fail_on_titles={"Bob"})
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["failed_rows"], 1)
        self.assertEqual(response.json()["item"]["skipped_rows"], 0)
        self.assertEqual(response.json()["item"]["created_ids"], [501])
        self.assertEqual(
            self._strip_report_meta(response.json()["item"]["results"]),
            [
                {
                    "row_number": 2,
                    "status": "created",
                    "record_id": 501,
                },
                {
                    "row_number": 3,
                    "status": "failed",
                    "error": 'Bitrix create failed for "Bob"',
                },
            ],
        )

    @patch("importer.services.import_execution.BitrixAPIBatchRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_hides_portal_domain_in_batch_timeout_errors(self, get_from_jwt_token, bitrix_api_batch_request):
        account = self.create_account()
        get_from_jwt_token.return_value = account
        bitrix_api_batch_request.side_effect = BitrixRequestTimeout(
            requests.exceptions.ReadTimeout(
                "HTTPSConnectionPool(host='mp24.bitrix24.ru', port=443): Read timed out. (read timeout=10)"
            ),
            timeout=10,
        )

        session = self.create_uploaded_session(
            [["Lead title", "Email", "Phone"]]
            + [[f"Lead {index}", f"lead{index}@example.com", f"+7900000{index:03d}"] for index in range(1, 51)]
        )
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 0)
        self.assertEqual(response.json()["item"]["failed_rows"], 50)

        first_error = response.json()["item"]["results"][0]["error"]
        self.assertNotIn("mp24.bitrix24.ru", first_error)
        self.assertNotIn("HTTPSConnectionPool", first_error)
        self.assertEqual(first_error, "Bitrix24 не ответил за 10 сек. Повторите импорт.")

        session.refresh_from_db()
        self.assertEqual(session.last_error, "")
        self.assertEqual(
            session.summary["import_run"]["results"][0]["error"],
            "Bitrix24 не ответил за 10 сек. Повторите импорт.",
        )

    @patch("importer.services.error_messages.format_import_error", side_effect=RuntimeError("formatter failed"))
    @patch("importer.views.execute_import", side_effect=OSError(-5, "No address associated with hostname"))
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_marks_session_failed_even_when_error_formatter_crashes(
        self,
        get_from_jwt_token,
        _execute_import,
        _format_import_error,
    ):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "[Errno -5] No address associated with hostname")

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.FAILED)
        self.assertEqual(session.last_error, "[Errno -5] No address associated with hostname")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.enqueue_import_session_run")
    @patch.dict("os.environ", {"ENABLE_RABBITMQ": "1"}, clear=False)
    def test_run_enqueues_background_job_when_queue_enabled(self, enqueue_import_session_run, get_from_jwt_token):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 202, response.content)
        enqueue_import_session_run.assert_called_once()

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.RUNNING)
        self.assertEqual(response.json()["item"]["status"], ImportSession.Status.RUNNING)
        self.assertEqual(response.json()["item"]["session_id"], str(session.id))
        self.assertEqual(session.processed_rows, 0)
        self.assertEqual(session.successful_rows, 0)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(response.json()["item"]["processed_rows"], 0)
        self.assertEqual(response.json()["item"]["successful_rows"], 0)
        self.assertEqual(response.json()["item"]["failed_rows"], 0)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.enqueue_import_session_run", side_effect=KombuOperationalError("[Errno -5] No address associated with hostname"))
    @patch.dict("os.environ", {"ENABLE_RABBITMQ": "1"}, clear=False)
    def test_run_falls_back_to_synchronous_execution_when_queue_broker_is_unavailable(
        self,
        enqueue_import_session_run,
        get_from_jwt_token,
        _batch,
    ):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        enqueue_import_session_run.assert_called_once()
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["failed_rows"], 0)
        self.assertEqual(response.json()["item"]["created_ids"], [501])

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.COMPLETED)
        self.assertEqual(session.last_error, "")
        self.assertEqual(session.processed_rows, 1)
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(session.failed_rows, 0)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.enqueue_import_session_run")
    @patch.dict("os.environ", {"ENABLE_RABBITMQ": "1"}, clear=False)
    def test_run_returns_conflict_when_background_job_is_already_active(self, enqueue_import_session_run, get_from_jwt_token):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)
        session.status = ImportSession.Status.RUNNING
        session.summary = {
            **(session.summary if isinstance(session.summary, dict) else {}),
            "job": {
                "mode": "run",
                "state": "queued",
                "task_id": "task-123",
                "error": "",
            },
        }
        session.save(update_fields=["status", "summary", "updated_at"])

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()["error"], "Import session is already queued or running")
        enqueue_import_session_run.assert_not_called()

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.RUNNING)
        self.assertEqual(session.summary["job"]["state"], "queued")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.enqueue_import_session_retry")
    @patch.dict("os.environ", {"ENABLE_RABBITMQ": "1"}, clear=False)
    def test_retry_failed_enqueues_background_job_when_queue_enabled(self, enqueue_import_session_retry, get_from_jwt_token):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)
        session.summary = {
            **session.summary,
            "import_run": {
                "checked_rows": 2,
                "created_rows": 1,
                "updated_rows": 0,
                "failed_rows": 1,
                "skipped_rows": 0,
                "cancelled": False,
                "cancelled_rows": 0,
                "remaining_rows": 0,
                "created_ids": [501],
                "updated_ids": [],
                "results": [
                    {"row_number": 2, "status": "created", "record_id": 501},
                    {"row_number": 3, "status": "failed", "error": 'Bitrix create failed for "Bob"'},
                ],
            },
        }
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["summary", "status", "updated_at"])

        retry_response = self.client.post(
            reverse("importer:session-retry-failed", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(retry_response.status_code, 202, retry_response.content)
        enqueue_import_session_retry.assert_called_once()

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.RUNNING)
        self.assertEqual(retry_response.json()["item"]["status"], ImportSession.Status.RUNNING)
        self.assertEqual(session.processed_rows, 0)
        self.assertEqual(session.successful_rows, 0)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(retry_response.json()["item"]["processed_rows"], 0)
        self.assertEqual(retry_response.json()["item"]["successful_rows"], 0)
        self.assertEqual(retry_response.json()["item"]["failed_rows"], 0)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.enqueue_import_session_retry", side_effect=KombuOperationalError("[Errno -5] No address associated with hostname"))
    @patch.dict("os.environ", {"ENABLE_RABBITMQ": "1"}, clear=False)
    def test_retry_failed_falls_back_to_synchronous_execution_when_queue_broker_is_unavailable(
        self,
        enqueue_import_session_retry,
        get_from_jwt_token,
        _batch,
    ):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)
        session.summary = {
            **session.summary,
            "import_run": {
                "checked_rows": 2,
                "created_rows": 1,
                "updated_rows": 0,
                "failed_rows": 1,
                "skipped_rows": 0,
                "cancelled": False,
                "cancelled_rows": 0,
                "remaining_rows": 0,
                "created_ids": [501],
                "updated_ids": [],
                "results": [
                    {"row_number": 2, "status": "created", "record_id": 501},
                    {"row_number": 3, "status": "failed", "error": 'Bitrix create failed for "Bob"'},
                ],
            },
        }
        session.status = ImportSession.Status.COMPLETED
        session.save(update_fields=["summary", "status", "updated_at"])

        retry_response = self.client.post(
            reverse("importer:session-retry-failed", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(retry_response.status_code, 200, retry_response.content)
        enqueue_import_session_retry.assert_called_once()
        self.assertEqual(retry_response.json()["item"]["retried_rows"], 1)
        self.assertEqual(retry_response.json()["item"]["created_rows"], 2)
        self.assertEqual(retry_response.json()["item"]["failed_rows"], 0)

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.COMPLETED)
        self.assertEqual(session.last_error, "")
        self.assertEqual(session.successful_rows, 2)
        self.assertEqual(session.failed_rows, 0)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.views.enqueue_import_session_retry")
    @patch.dict("os.environ", {"ENABLE_RABBITMQ": "1"}, clear=False)
    def test_retry_failed_returns_conflict_when_background_job_is_already_active(self, enqueue_import_session_retry, get_from_jwt_token):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)
        session.summary = {
            **session.summary,
            "import_run": {
                "checked_rows": 2,
                "created_rows": 1,
                "updated_rows": 0,
                "failed_rows": 1,
                "skipped_rows": 0,
                "cancelled": False,
                "cancelled_rows": 0,
                "remaining_rows": 0,
                "created_ids": [501],
                "updated_ids": [],
                "results": [
                    {"row_number": 2, "status": "created", "record_id": 501},
                    {"row_number": 3, "status": "failed", "error": 'Bitrix create failed for "Bob"'},
                ],
            },
            "job": {
                "mode": "retry",
                "state": "running",
                "task_id": "task-456",
                "error": "",
            },
        }
        session.status = ImportSession.Status.RUNNING
        session.save(update_fields=["summary", "status", "updated_at"])

        response = self.client.post(
            reverse("importer:session-retry-failed", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()["error"], "Import session is already queued or running")
        enqueue_import_session_retry.assert_not_called()

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.RUNNING)
        self.assertEqual(session.summary["job"]["state"], "running")

    @patch("importer.services.import_execution.BitrixAPIBatchRequest")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_report_csv_downloads_import_results_after_run(self, get_from_jwt_token, bitrix_api_batch_request):
        account = self.create_account()
        get_from_jwt_token.return_value = account
        bitrix_api_batch_request.return_value = SimpleNamespace(
            result=SimpleNamespace(
                result={"0": 501},
                result_error={"1": 'Bitrix create failed for "Bob"'},
            )
        )

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)

        run_response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(run_response.status_code, 200, run_response.json())

        report_response = self.client.get(
            reverse("importer:session-report-csv", kwargs={"session_id": session.id}),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", report_response["Content-Disposition"])
        report_text = report_response.content.decode("utf-8-sig")
        self.assertIn("Строка;Статус;Дата и время;Сущность;Название;ID в Bitrix24;Обновлённые поля;Ошибка", report_text)
        self.assertIn("2;Создано;", report_text)
        self.assertIn("3;Ошибка;", report_text)
        self.assertIn('Bitrix create failed for ""Bob""', report_text)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_cancel_marks_running_session_as_cancelled(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        session.status = ImportSession.Status.RUNNING
        session.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("importer:session-cancel", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["status"], ImportSession.Status.CANCELLED)

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.CANCELLED)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    @patch("importer.services.import_execution.create_entity_record")
    def test_run_stops_when_session_was_cancelled_during_execution(self, create_entity_record, get_from_jwt_token, _batch):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)

        first_call = {"done": False}

        def create_entity_record_side_effect(*args, **kwargs):
            if not first_call["done"]:
                first_call["done"] = True
                running_session = ImportSession.objects.get(id=session.id)
                running_session.status = ImportSession.Status.CANCELLED
                running_session.save(update_fields=["status", "updated_at"])
                return 501

            return 502

        create_entity_record.side_effect = create_entity_record_side_effect

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["status"], ImportSession.Status.CANCELLED)
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["cancelled_rows"], 1)
        self.assertEqual(response.json()["item"]["remaining_rows"], 1)
        self.assertEqual(
            self._strip_report_meta(response.json()["item"]["results"]),
            [
                {
                    "row_number": 2,
                    "status": "created",
                    "record_id": 501,
                },
                {
                    "row_number": 3,
                    "status": "cancelled",
                    "error": "Import was cancelled before row execution",
                },
            ],
        )

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.CANCELLED)
        self.assertEqual(session.processed_rows, 1)
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(session.summary["import_run"]["created_rows"], 1)
        self.assertEqual(session.summary["import_run"]["cancelled_rows"], 1)
        self.assertEqual(session.summary["import_run"]["remaining_rows"], 1)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_retry_failed_rows_retries_only_unsuccessful_rows_and_merges_summary(self, get_from_jwt_token, _batch):
        first_account = self.create_account(fail_on_titles={"Bob"})
        get_from_jwt_token.return_value = first_account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
                ["Bob", "bob@example.com", "+987654321"],
            ]
        )
        self.prepare_session(session, validate=True)

        first_run_response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(first_run_response.status_code, 200, first_run_response.json())
        self.assertEqual(first_run_response.json()["item"]["created_rows"], 1)
        self.assertEqual(first_run_response.json()["item"]["failed_rows"], 1)

        retry_account = self.create_account()
        get_from_jwt_token.return_value = retry_account

        retry_response = self.client.post(
            reverse("importer:session-retry-failed", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(retry_response.status_code, 200, retry_response.json())
        self.assertEqual(retry_response.json()["item"]["retried_rows"], 1)
        self.assertEqual(retry_response.json()["item"]["created_rows"], 2)
        self.assertEqual(retry_response.json()["item"]["failed_rows"], 0)
        self.assertEqual(
            self._strip_report_meta(retry_response.json()["item"]["results"]),
            [
                {
                    "row_number": 2,
                    "status": "created",
                    "record_id": 501,
                },
                {
                    "row_number": 3,
                    "status": "created",
                    "record_id": 501,
                },
            ],
        )
        self.assertEqual(
            retry_account.created_fields,
            [
                {
                    "TITLE": "Bob",
                    "EMAIL": "bob@example.com",
                    "PHONE": "+987654321",
                }
            ],
        )

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.COMPLETED)
        self.assertEqual(session.successful_rows, 2)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(session.summary["import_run"]["created_rows"], 2)
        self.assertEqual(session.summary["import_run"]["failed_rows"], 0)
        self.assertEqual(len(session.summary["retry_runs"]), 1)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_retry_failed_rows_returns_error_when_session_has_no_retryable_rows(self, get_from_jwt_token, _batch):
        account = self.create_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)

        run_response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(run_response.status_code, 200, run_response.json())

        retry_response = self.client.post(
            reverse("importer:session-retry-failed", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(retry_response.status_code, 400)
        self.assertEqual(retry_response.json()["error"], "There are no failed rows to retry")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_requires_validation_before_execution(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account()

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=False)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Validation is required before import execution")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_is_limited_to_current_portal_session(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account(member_id="member-1", domain_url="test.bitrix24.ru")

        session = ImportSession.objects.create(
            portal_member_id="member-2",
            portal_domain="other.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.VALIDATED,
            original_filename="other.xlsx",
        )

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 404)

    @patch("importer.services.import_execution._is_batch_eligible", return_value=False)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_formats_contact_phone_as_bitrix_multifield(self, get_from_jwt_token, _batch):
        account = self.create_contact_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_contact_session(
            [
                ["First name", "Phone"],
                ["Alice", "+123456789"],
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
                    "NAME": {
                        "source_header": "First name",
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

        validation_response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(validation_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(
            account.created_fields,
            [
                {
                    "NAME": "Alice",
                    "PHONE": [
                        {
                            "VALUE": "+123456789",
                            "VALUE_TYPE": "WORK",
                        }
                    ],
                }
            ],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_skips_duplicate_rows_when_dedup_strategy_is_skip(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("EMAIL", "alice@example.com"),): [{"ID": 901}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)
        session.refresh_from_db()
        session.import_settings = {
            **session.import_settings,
            "dedup": {
                "strategy": "skip",
                "fields": ["EMAIL"],
            },
        }
        session.save(update_fields=["import_settings", "updated_at"])

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 0)
        self.assertEqual(response.json()["item"]["updated_rows"], 0)
        self.assertEqual(response.json()["item"]["skipped_rows"], 1)
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "skipped_duplicate",
                "record_id": 901,
                "duplicate_match_fields": ["EMAIL"],
                "error": "Duplicate matched existing record",
            }
        ])
        self.assertEqual(account.created_fields, [])
        self.assertEqual(account.updated_records, [])

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.COMPLETED)
        self.assertEqual(session.successful_rows, 0)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(session.summary["import_run"]["updated_rows"], 0)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_updates_existing_record_when_dedup_strategy_is_update(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("PHONE", "+123456789"),): [{"ID": 902}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
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
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 0)
        self.assertEqual(response.json()["item"]["updated_rows"], 1)
        self.assertEqual(response.json()["item"]["failed_rows"], 0)
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "updated",
                "record_id": 902,
                "duplicate_match_fields": ["PHONE"],
                "updated_fields": ["TITLE", "EMAIL", "PHONE"],
            }
        ])
        self.assertEqual(account.created_fields, [])
        self.assertEqual(account.updated_records, [
            {
                "id": 902,
                "fields": {
                    "TITLE": "Alice",
                    "EMAIL": "alice@example.com",
                    "PHONE": "+123456789",
                },
            }
        ])

        session.refresh_from_db()
        self.assertEqual(session.status, ImportSession.Status.COMPLETED)
        self.assertEqual(session.successful_rows, 1)
        self.assertEqual(session.failed_rows, 0)
        self.assertEqual(session.summary["import_run"]["updated_rows"], 1)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_does_not_use_single_field_duplicate_when_multiple_dedup_fields_are_selected(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("EMAIL", "alice@example.com"),): [{"ID": 901}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", "+123456789"],
            ]
        )
        self.prepare_session(session, validate=True)
        session.refresh_from_db()
        session.import_settings = {
            **session.import_settings,
            "dedup": {
                "strategy": "skip",
                "fields": ["EMAIL", "PHONE"],
                "condition": "all",
            },
        }
        session.save(update_fields=["import_settings", "updated_at"])

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["updated_rows"], 0)
        self.assertEqual(response.json()["item"]["skipped_rows"], 0)
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "created",
                "record_id": 501,
            }
        ])
        self.assertEqual(account.created_fields, [
            {
                "TITLE": "Alice",
                "EMAIL": "alice@example.com",
                "PHONE": "+123456789",
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_reports_missing_selected_dedup_fields_when_duplicate_search_uses_partial_match(self, get_from_jwt_token):
        account = self.create_account(
            duplicates_by_filter={
                (("EMAIL", "alice@example.com"),): [{"ID": 903}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_session(
            [
                ["Lead title", "Email", "Phone"],
                ["Alice", "alice@example.com", ""],
            ]
        )
        self.prepare_session(session, validate=True)
        session.refresh_from_db()
        session.import_settings = {
            **session.import_settings,
            "dedup": {
                "strategy": "skip",
                "fields": ["EMAIL", "PHONE"],
            },
        }
        session.save(update_fields=["import_settings", "updated_at"])

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "skipped_duplicate",
                "record_id": 903,
                "duplicate_match_fields": ["EMAIL"],
                "dedup_missing_fields": ["PHONE"],
                "error": "Duplicate matched existing record",
            }
        ])
        self.assertEqual(account.created_fields, [])
        self.assertEqual(account.list_calls, [{"filter": {"EMAIL": "alice@example.com"}, "select": ["ID"]}])
        self.assertEqual(account.updated_records, [])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_task_with_user_role_fields(self, get_from_jwt_token):
        account = self.create_task_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_task_session(
            [
                ["Task title", "Responsible", "Accomplices", "Auditors", "Deadline"],
                ["Task A", "59", "77; 78", "91\n92", "31.12.2026 18:45"],
            ]
        )
        self.prepare_task_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [801])
        self.assertEqual(account.created_fields, [
            {
                "TITLE": "Task A",
                "RESPONSIBLE_ID": 59,
                "ACCOMPLICES": [77, 78],
                "AUDITORS": [91, 92],
                "DEADLINE": "2026-12-31T18:45:00",
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_task_with_user_role_fields_resolved_from_email_login_and_xml_id(self, get_from_jwt_token):
        account = self.create_task_account(
            user_results_by_filter={
                (("EMAIL", "owner@example.com"),): [{"ID": 59}],
                (("LOGIN", "helper-login"),): [{"ID": 77}],
                (("LOGIN", "helper-two"),): [{"ID": 78}],
                (("LOGIN", "audit-ext"),): [],
                (("XML_ID", "audit-ext"),): [{"ID": 91}],
                (("LOGIN", "review-ext"),): [],
                (("XML_ID", "review-ext"),): [{"ID": 92}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_task_session(
            [
                ["Task title", "Responsible", "Accomplices", "Auditors", "Deadline"],
                ["Task A", "owner@example.com", "helper-login; helper-two", "audit-ext\nreview-ext", "31.12.2026 18:45"],
            ]
        )
        self.prepare_task_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [801])
        self.assertEqual(account.created_fields, [
            {
                "TITLE": "Task A",
                "RESPONSIBLE_ID": 59,
                "ACCOMPLICES": [77, 78],
                "AUDITORS": [91, 92],
                "DEADLINE": "2026-12-31T18:45:00",
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_subtask_with_parent_id(self, get_from_jwt_token):
        account = self.create_task_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_task_session(
            [
                ["Task title", "Parent"],
                ["Subtask A", "501"],
            ]
        )
        self.prepare_task_session(
            session,
            validate=True,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                },
                "PARENT_ID": {
                    "source_header": "Parent",
                    "column": "B",
                },
            },
        )

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(account.created_fields, [
            {
                "TITLE": "Subtask A",
                "PARENT_ID": 501,
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_subtask_with_parent_xml_id(self, get_from_jwt_token):
        account = self.create_task_account(
            task_results_by_filter={
                (("XML_ID", "task-ext-1"),): [{"ID": 501}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_task_session(
            [
                ["Task title", "Parent"],
                ["Subtask A", "task-ext-1"],
            ]
        )
        self.prepare_task_session(
            session,
            validate=True,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                },
                "PARENT_ID": {
                    "source_header": "Parent",
                    "column": "B",
                },
            },
        )

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(account.created_fields, [
            {
                "TITLE": "Subtask A",
                "PARENT_ID": 501,
            }
        ])
        self.assertEqual(account.task_lookup_calls, [
            {
                "filter": {"XML_ID": "task-ext-1"},
                "select": ["ID", "XML_ID"],
            },
            {
                "filter": {"XML_ID": "task-ext-1"},
                "select": ["ID", "XML_ID"],
            }
        ])

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_sends_task_chat_message(self, get_from_jwt_token, bitrix_api_request):
        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=lambda *, filter=None: FakeUsersRequest([]),
                )
            ),
        )
        get_from_jwt_token.return_value = account
        bitrix_api_request.return_value = SimpleNamespace(result={"result": True})

        session = self.create_uploaded_task_comment_session(
            [
                ["Task", "Message"],
                ["801", "Status update"],
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
                    "TASK_ID": {"source_header": "Task", "column": "A"},
                    "POST_MESSAGE": {"source_header": "Message", "column": "B"},
                }
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

        validation_response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(validation_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [])
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "created",
            }
        ])
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="tasks.task.chat.message.send",
            params={
                "fields": {
                    "taskId": 801,
                    "text": "Status update",
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_task_comment_uses_author_from_file_before_default(self, get_from_jwt_token, bitrix_api_request):
        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                user=SimpleNamespace(
                    get=lambda *, filter=None: FakeUsersRequest([{"ID": 73}]),
                )
            ),
        )
        get_from_jwt_token.return_value = account
        bitrix_api_request.return_value = SimpleNamespace(result=915)

        session = self.create_uploaded_task_comment_session(
            [
                ["Task", "Author", "Message"],
                ["801", "73", "Status update"],
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
                    "TASK_ID": {"source_header": "Task", "column": "A"},
                    "AUTHOR_ID": {"source_header": "Author", "column": "B"},
                    "POST_MESSAGE": {"source_header": "Message", "column": "C"},
                },
                "default_comment_author_id": "59",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

        validation_response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(validation_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [915])
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "created",
                "record_id": 915,
            }
        ])
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="task.commentitem.add",
            params={
                "TASKID": 801,
                "FIELDS": {
                    "POST_MESSAGE": "Status update",
                    "AUTHOR_ID": 73,
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_crm_activity(self, get_from_jwt_token, bitrix_api_request):
        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        get_from_jwt_token.return_value = account
        bitrix_api_request.return_value = SimpleNamespace(result=913)

        session = self.create_uploaded_crm_activity_session(
            [
                ["Тип сущности CRM", "ID записи CRM", "Тип активности", "Тема / заголовок"],
                ["1", "501", "6", "Перезвонить клиенту"],
            ]
        )
        self.prepare_custom_mapping_session(
            session,
            {
                "OWNER_TYPE_ID": {"source_header": "Тип сущности CRM", "column": "A"},
                "OWNER_ID": {"source_header": "ID записи CRM", "column": "B"},
                "TYPE_ID": {"source_header": "Тип активности", "column": "C"},
                "SUBJECT": {"source_header": "Тема / заголовок", "column": "D"},
            },
            validate=True,
        )

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [913])
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "created",
                "record_id": 913,
            }
        ])
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="crm.activity.add",
            params={
                "fields": {
                    "OWNER_TYPE_ID": 1,
                    "OWNER_ID": 501,
                    "TYPE_ID": 6,
                    "SUBJECT": "Перезвонить клиенту",
                    "COMMUNICATIONS": [
                        {
                            "ENTITY_ID": 501,
                            "ENTITY_TYPE_ID": 1,
                        }
                    ],
                }
            },
        )

    @patch("importer.services.import_execution.BitrixAPIRequest", create=True)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_crm_note(self, get_from_jwt_token, bitrix_api_request):
        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        get_from_jwt_token.return_value = account
        bitrix_api_request.return_value = SimpleNamespace(result=914)

        session = self.create_uploaded_crm_note_session(
            [
                ["Тип сущности CRM", "ID записи CRM", "Текст заметки"],
                ["contact", "701", "Комментарий по клиенту"],
            ]
        )
        self.prepare_custom_mapping_session(
            session,
            {
                "ENTITY_TYPE": {"source_header": "Тип сущности CRM", "column": "A"},
                "ENTITY_ID": {"source_header": "ID записи CRM", "column": "B"},
                "COMMENT": {"source_header": "Текст заметки", "column": "C"},
            },
            validate=True,
        )

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [914])
        self.assertEqual(self._strip_report_meta(response.json()["item"]["results"]), [
            {
                "row_number": 2,
                "status": "created",
                "record_id": 914,
            }
        ])
        bitrix_api_request.assert_called_once_with(
            bitrix_token=account,
            api_method="crm.timeline.comment.add",
            params={
                "fields": {
                    "ENTITY_TYPE": "CONTACT",
                    "ENTITY_ID": 701,
                    "COMMENT": "Комментарий по клиенту",
                }
            },
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_task_checklist_item(self, get_from_jwt_token):
        account = self.create_task_checklist_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_task_checklist_session(
            [
                ["Task", "Title", "Done"],
                ["801", "Prepare brief", "да"],
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
                    "TASK_ID": {"source_header": "Task", "column": "A"},
                    "TITLE": {"source_header": "Title", "column": "B"},
                    "IS_COMPLETE": {"source_header": "Done", "column": "C"},
                }
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

        validation_response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(validation_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [5001])
        self.assertEqual(account.checklist_calls, [
            {
                "task_id": 801,
                "fields": {
                    "TITLE": "Prepare brief",
                    "IS_COMPLETE": 1,
                },
            }
        ])

    @patch("importer.services.import_execution.attach_file_to_task", create=True)
    @patch("importer.services.import_execution.download_attachment_source", create=True)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_task_attachment(self, get_from_jwt_token, download_attachment_source, attach_file_to_task):
        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        get_from_jwt_token.return_value = account
        download_attachment_source.return_value = {
            "content": b"hello world",
            "file_name": "brief.txt",
            "content_type": "text/plain",
        }
        attach_file_to_task.return_value = {"attachment_id": 7001}

        session = self.create_uploaded_task_attachment_session(
            [
                ["Task", "URL", "Name"],
                ["801", "https://files.example.com/brief.txt", "Renamed brief.txt"],
            ]
        )
        self.prepare_task_attachment_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [7001])
        download_attachment_source.assert_called_once_with("https://files.example.com/brief.txt")
        attach_file_to_task.assert_called_once_with(
            account,
            task_id=801,
            file_name="Renamed brief.txt",
            content=b"hello world",
            content_type="text/plain",
        )

    @patch("importer.services.import_execution.attach_file_to_task", create=True)
    @patch("importer.services.import_execution.download_attachment_source", create=True)
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_task_attachment_with_task_xml_id(self, get_from_jwt_token, download_attachment_source, attach_file_to_task):
        task_lookup_calls = []

        def list_tasks(*, filter=None, select=None, order=None, start=None):
            normalized_filter = tuple(sorted((filter or {}).items()))
            task_lookup_calls.append(
                {
                    "filter": dict(filter or {}),
                    "select": list(select or []),
                }
            )
            task_results_by_filter = {
                (("XML_ID", "task-ext-1"),): [{"ID": 801}],
            }
            return FakeListRequest(task_results_by_filter.get(normalized_filter, []))

        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(
                tasks=SimpleNamespace(
                    task=SimpleNamespace(
                        list=list_tasks,
                    )
                )
            ),
        )
        get_from_jwt_token.return_value = account
        download_attachment_source.return_value = {
            "content": b"hello world",
            "file_name": "brief.txt",
            "content_type": "text/plain",
        }
        attach_file_to_task.return_value = {"attachment_id": 7001}

        session = self.create_uploaded_task_attachment_session(
            [
                ["Task", "URL", "Name"],
                ["task-ext-1", "https://files.example.com/brief.txt", "Renamed brief.txt"],
            ]
        )
        self.prepare_task_attachment_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [7001])
        self.assertEqual(task_lookup_calls, [
            {
                "filter": {"XML_ID": "task-ext-1"},
                "select": ["ID", "XML_ID"],
            },
            {
                "filter": {"XML_ID": "task-ext-1"},
                "select": ["ID", "XML_ID"],
            }
        ])
        attach_file_to_task.assert_called_once_with(
            account,
            task_id=801,
            file_name="Renamed brief.txt",
            content=b"hello world",
            content_type="text/plain",
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_task_with_richer_task_fields(self, get_from_jwt_token):
        account = self.create_task_account(
            user_results_by_filter={
                (("EMAIL", "creator@example.com"),): [{"ID": 17}],
            }
        )
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_task_session(
            [
                ["Task title", "Description", "Creator", "Project", "Priority", "Tags", "Start", "End", "Deadline"],
                ["Task B", "Long task description", "creator@example.com", "15", "2", "alpha; beta", "31.12.2026 09:00", "31.12.2026 18:00", "01.01.2027 12:00"],
            ]
        )
        self.prepare_task_session(
            session,
            validate=True,
            mapping={
                "TITLE": {
                    "source_header": "Task title",
                    "column": "A",
                },
                "DESCRIPTION": {
                    "source_header": "Description",
                    "column": "B",
                },
                "CREATED_BY": {
                    "source_header": "Creator",
                    "column": "C",
                },
                "GROUP_ID": {
                    "source_header": "Project",
                    "column": "D",
                },
                "PRIORITY": {
                    "source_header": "Priority",
                    "column": "E",
                },
                "TAGS": {
                    "source_header": "Tags",
                    "column": "F",
                },
                "START_DATE_PLAN": {
                    "source_header": "Start",
                    "column": "G",
                },
                "END_DATE_PLAN": {
                    "source_header": "End",
                    "column": "H",
                },
                "DEADLINE": {
                    "source_header": "Deadline",
                    "column": "I",
                },
            },
        )

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [801])
        self.assertEqual(account.created_fields, [
            {
                "TITLE": "Task B",
                "DESCRIPTION": "Long task description",
                "CREATED_BY": 17,
                "GROUP_ID": 15,
                "PRIORITY": 2,
                "TAGS": ["alpha", "beta"],
                "START_DATE_PLAN": "2026-12-31T09:00:00",
                "END_DATE_PLAN": "2026-12-31T18:00:00",
                "DEADLINE": "2027-01-01T12:00:00",
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_company_then_contact_and_links_them_in_linked_import(self, get_from_jwt_token):
        account = self.create_linked_company_contact_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_linked_company_contact_session(
            [
                [
                    "Название компании",
                    "Телефон компании",
                    "Имя контакта",
                    "Фамилия контакта",
                    "Email контакта",
                ],
                [
                    "ООО Альфа",
                    "+78005550101",
                    "Алиса",
                    "Иванова",
                    "alice@example.ru",
                ],
            ]
        )
        self.prepare_linked_company_contact_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [701])
        self.assertEqual(len(response.json()["item"]["results"]), 1)
        result_item = response.json()["item"]["results"][0]
        self.assertEqual(result_item["row_number"], 2)
        self.assertEqual(result_item["status"], "created")
        self.assertEqual(result_item["record_id"], 701)
        self.assertEqual(result_item["report_entity"], "Компания + Контакт")
        self.assertEqual(result_item["report_title"], "ООО Альфа / Алиса Иванова")
        self.assertEqual(result_item["report_record_id"], "Компания 601 · Контакт 701")
        self.assertTrue(result_item["report_date_time"])
        self.assertEqual(result_item["linked_records"], {
            "company": {
                "id": 601,
                "title": "ООО Альфа",
                "status": "created",
            },
            "contact": {
                "id": 701,
                "title": "Алиса Иванова",
                "status": "created",
            },
        })
        self.assertEqual(account.company_created_fields, [
            {
                "TITLE": "ООО Альфа",
                "PHONE": [{"VALUE": "+78005550101", "VALUE_TYPE": "WORK"}],
            }
        ])
        self.assertEqual(account.contact_created_fields, [
            {
                "NAME": "Алиса",
                "LAST_NAME": "Иванова",
                "EMAIL": [{"VALUE": "alice@example.ru", "VALUE_TYPE": "WORK"}],
                "COMPANY_ID": 601,
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_creates_company_then_deal_and_links_them_in_linked_import(self, get_from_jwt_token):
        account = self.create_linked_company_deal_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_linked_company_deal_session(
            [
                [
                    "Название компании",
                    "Телефон компании",
                    "Название сделки",
                    "Сумма",
                    "Валюта",
                    "Стадия",
                ],
                [
                    "ООО Альфа",
                    "+78005550101",
                    "Редизайн сайта",
                    "150000",
                    "RUB",
                    "Новая",
                ],
            ]
        )
        self.prepare_linked_company_deal_session(session, validate=True)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 1)
        self.assertEqual(response.json()["item"]["created_ids"], [801])
        self.assertEqual(len(response.json()["item"]["results"]), 1)
        result_item = response.json()["item"]["results"][0]
        self.assertEqual(result_item["row_number"], 2)
        self.assertEqual(result_item["status"], "created")
        self.assertEqual(result_item["record_id"], 801)
        self.assertEqual(result_item["report_entity"], "Компания + Сделка")
        self.assertEqual(result_item["report_title"], "ООО Альфа / Редизайн сайта")
        self.assertEqual(result_item["report_record_id"], "Компания 601 · Сделка 801")
        self.assertTrue(result_item["report_date_time"])
        self.assertEqual(result_item["linked_records"], {
            "company": {
                "id": 601,
                "title": "ООО Альфа",
                "status": "created",
            },
            "deal": {
                "id": 801,
                "title": "Редизайн сайта",
                "status": "created",
            },
        })
        self.assertEqual(account.company_created_fields, [
            {
                "TITLE": "ООО Альфа",
                "PHONE": [{"VALUE": "+78005550101", "VALUE_TYPE": "WORK"}],
            }
        ])
        self.assertEqual(account.deal_created_fields, [
            {
                "TITLE": "Редизайн сайта",
                "OPPORTUNITY": 150000.0,
                "CURRENCY_ID": "RUB",
                "STAGE_ID": "NEW",
                "COMPANY_ID": 601,
            }
        ])

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_run_linked_import_reuses_company_for_repeated_external_key(self, get_from_jwt_token):
        account = self.create_linked_company_contact_account()
        get_from_jwt_token.return_value = account

        session = self.create_uploaded_linked_company_contact_session(
            [
                [
                    "Внешний ключ",
                    "Название компании",
                    "Имя контакта",
                    "Фамилия контакта",
                ],
                [
                    "company_001",
                    "ООО Альфа",
                    "Алиса",
                    "Иванова",
                ],
                [
                    "company_001",
                    "ООО Альфа",
                    "Борис",
                    "Петров",
                ],
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
                    "COMPANY__EXTERNAL_KEY": {
                        "source_header": "Внешний ключ",
                        "column": "A",
                    },
                    "COMPANY__TITLE": {
                        "source_header": "Название компании",
                        "column": "B",
                    },
                    "CONTACT__NAME": {
                        "source_header": "Имя контакта",
                        "column": "C",
                    },
                    "CONTACT__LAST_NAME": {
                        "source_header": "Фамилия контакта",
                        "column": "D",
                    },
                },
                "dedup": {
                    "company": {
                        "strategy": "create",
                        "fields": [],
                    },
                    "contact": {
                        "strategy": "create",
                        "fields": [],
                    },
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(mapping_response.status_code, 200)

        validation_response = self.client.post(
            reverse("importer:session-validate", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(validation_response.status_code, 200)

        response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["item"]["created_rows"], 2)
        self.assertEqual(response.json()["item"]["created_ids"], [701, 702])

        # Company must be created only once despite two rows sharing the same external key
        self.assertEqual(len(account.company_created_fields), 1)
        self.assertEqual(account.company_created_fields[0]["TITLE"], "ООО Альфа")

        # Both contacts must be linked to the same company (id=601)
        self.assertEqual(len(account.contact_created_fields), 2)
        self.assertEqual(account.contact_created_fields[0]["NAME"], "Алиса")
        self.assertEqual(account.contact_created_fields[0]["COMPANY_ID"], 601)
        self.assertEqual(account.contact_created_fields[1]["NAME"], "Борис")
        self.assertEqual(account.contact_created_fields[1]["COMPANY_ID"], 601)

        results = response.json()["item"]["results"]
        self.assertEqual(results[0]["linked_records"]["company"]["status"], "created")
        self.assertEqual(results[0]["linked_records"]["company"]["id"], 601)
        self.assertEqual(results[1]["linked_records"]["company"]["status"], "existing")
        self.assertEqual(results[1]["linked_records"]["company"]["id"], 601)
