from datetime import datetime, timezone as dt_timezone

from django.test import SimpleTestCase, override_settings

from importer.services.b24_fields import SMART_PROCESS_ENTITY_TYPE
from importer.services.report_metadata import build_import_result_report_meta
from importer.views import build_import_report_csv


class ImportReportMetadataTest(SimpleTestCase):
    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_universal_fields_for_supported_entities(self):
        timestamp = datetime(2026, 5, 14, 9, 30, 45, tzinfo=dt_timezone.utc)
        cases = [
            ("deal", {"TITLE": "Сделка Альфа"}, 501, None, None, "Сделка", "Сделка Альфа", "501"),
            ("contact", {"NAME": "Анна", "LAST_NAME": "Иванова"}, 701, None, None, "Контакт", "Анна Иванова", "701"),
            ("task", {"TITLE": "Подготовить КП"}, 801, None, None, "Задача", "Подготовить КП", "801"),
            ("task_comment", {"POST_MESSAGE": "Готово к согласованию"}, 901, None, None, "Комментарий задачи", "Готово к согласованию", "901"),
            ("task_attachment", {"FILE_NAME": "brief.pdf"}, 902, None, None, "Вложение задачи", "brief.pdf", "902"),
            ("crm_activity", {"SUBJECT": "Звонок по клиенту"}, 903, None, None, "Активность CRM", "Звонок по клиенту", "903"),
            ("crm_note", {"COMMENT": "Клиент просит перезвонить"}, 904, None, None, "Заметка CRM", "Клиент просит перезвонить", "904"),
            ("user", {"NAME": "Иван", "LAST_NAME": "Петров"}, 905, None, None, "Пользователь", "Иван Петров", "905"),
            ("department", {"NAME": "Отдел продаж"}, 906, None, None, "Подразделение", "Отдел продаж", "906"),
            (SMART_PROCESS_ENTITY_TYPE, {"TITLE": "Заявка 42"}, 907, None, {"title": "Заявки"}, "Смарт-процесс: Заявки", "Заявка 42", "907"),
        ]

        for entity_type, row_payload, record_id, linked_records, entity_config, expected_entity, expected_title, expected_record_id in cases:
            with self.subTest(entity_type=entity_type):
                meta = build_import_result_report_meta(
                    entity_type,
                    row_payload=row_payload,
                    record_id=record_id,
                    linked_records=linked_records,
                    entity_config=entity_config,
                    timestamp=timestamp,
                )

                self.assertEqual(
                    meta,
                    {
                        "report_date_time": "14.05.2026 09:30:45",
                        "report_entity": expected_entity,
                        "report_title": expected_title,
                        "report_record_id": expected_record_id,
                    },
                )

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_linked_import_summary(self):
        meta = build_import_result_report_meta(
            "linked_company_contact",
            record_id=73,
            linked_records={
                "company": {"id": 71, "title": "ООО Альфа"},
                "contact": {"id": 73, "title": "Алиса Иванова"},
            },
            timestamp=datetime(2026, 5, 14, 10, 5, 0, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            meta,
            {
                "report_date_time": "14.05.2026 10:05:00",
                "report_entity": "Компания + Контакт",
                "report_title": "ООО Альфа / Алиса Иванова",
                "report_record_id": "Компания 71 · Контакт 73",
            },
        )

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_linked_company_deal_summary(self):
        meta = build_import_result_report_meta(
            "linked_company_deal",
            record_id=81,
            linked_records={
                "company": {"id": 71, "title": "ООО Альфа"},
                "deal": {"id": 81, "title": "Редизайн сайта"},
            },
            timestamp=datetime(2026, 5, 14, 10, 6, 0, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            meta,
            {
                "report_date_time": "14.05.2026 10:06:00",
                "report_entity": "Компания + Сделка",
                "report_title": "ООО Альфа / Редизайн сайта",
                "report_record_id": "Компания 71 · Сделка 81",
            },
        )

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_linked_contact_deal_summary(self):
        meta = build_import_result_report_meta(
            "linked_contact_deal",
            record_id=81,
            linked_records={
                "contact": {"id": 71, "title": "Алиса Иванова"},
                "deal": {"id": 81, "title": "Редизайн сайта"},
            },
            timestamp=datetime(2026, 5, 14, 10, 7, 0, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            meta,
            {
                "report_date_time": "14.05.2026 10:07:00",
                "report_entity": "Контакт + Сделка",
                "report_title": "Алиса Иванова / Редизайн сайта",
                "report_record_id": "Контакт 71 · Сделка 81",
            },
        )

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_linked_contact_company_summary(self):
        meta = build_import_result_report_meta(
            "linked_contact_company",
            record_id=91,
            linked_records={
                "contact": {"id": 71, "title": "Алиса Иванова"},
                "company": {"id": 91, "title": "ООО Альфа"},
            },
            timestamp=datetime(2026, 5, 14, 10, 7, 30, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            meta,
            {
                "report_date_time": "14.05.2026 10:07:30",
                "report_entity": "Контакт + Компания",
                "report_title": "Алиса Иванова / ООО Альфа",
                "report_record_id": "Контакт 71 · Компания 91",
            },
        )

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_linked_deal_contact_summary(self):
        meta = build_import_result_report_meta(
            "linked_deal_contact",
            record_id=71,
            linked_records={
                "deal": {"id": 81, "title": "Редизайн сайта"},
                "contact": {"id": 71, "title": "Алиса Иванова"},
            },
            timestamp=datetime(2026, 5, 14, 10, 8, 0, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            meta,
            {
                "report_date_time": "14.05.2026 10:08:00",
                "report_entity": "Сделка + Контакт",
                "report_title": "Редизайн сайта / Алиса Иванова",
                "report_record_id": "Сделка 81 · Контакт 71",
            },
        )

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_build_import_result_report_meta_formats_linked_deal_company_summary(self):
        meta = build_import_result_report_meta(
            "linked_deal_company",
            record_id=91,
            linked_records={
                "deal": {"id": 81, "title": "Редизайн сайта"},
                "company": {"id": 91, "title": "ООО Альфа"},
            },
            timestamp=datetime(2026, 5, 14, 10, 8, 30, tzinfo=dt_timezone.utc),
        )

        self.assertEqual(
            meta,
            {
                "report_date_time": "14.05.2026 10:08:30",
                "report_entity": "Сделка + Компания",
                "report_title": "Редизайн сайта / ООО Альфа",
                "report_record_id": "Сделка 81 · Компания 91",
            },
        )

    def test_build_import_report_csv_returns_human_readable_russian_csv(self):
        csv_text = build_import_report_csv(
            {
                "results": [
                    {
                        "row_number": 2,
                        "status": "created",
                        "report_date_time": "14.05.2026 09:30:45",
                        "report_entity": "Контакт",
                        "report_title": "Анна Иванова",
                        "report_record_id": "701",
                        "record_id": 701,
                    },
                    {
                        "row_number": 3,
                        "status": "failed",
                        "report_date_time": "14.05.2026 09:31:10",
                        "report_entity": "Сделка",
                        "report_title": "Сделка Бета",
                        "report_record_id": "",
                        "error": "Bitrix create failed for \"Бета\"",
                    },
                ]
            }
        )

        self.assertIn(
            "Строка;Статус;Дата и время;Сущность;Название;ID в Bitrix24;Обновлённые поля;Ошибка",
            csv_text,
        )
        self.assertIn("2;Создано;14.05.2026 09:30:45;Контакт;Анна Иванова;701;;", csv_text)
        self.assertIn('3;Ошибка;14.05.2026 09:31:10;Сделка;Сделка Бета;;;"Bitrix create failed for ""Бета"""', csv_text)
