from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from importer.services.import_execution import _flush_crm_batch


class ImportExecutionBatchTest(SimpleTestCase):
    @patch("importer.services.import_execution.BitrixAPIBatchRequest")
    def test_flush_crm_batch_reads_record_ids_from_list_result(self, bitrix_api_batch_request):
        bitrix_api_batch_request.return_value = SimpleNamespace(
            result=SimpleNamespace(
                result=[901, 902],
                result_error=[],
            )
        )

        results, created_count, failed_count, created_ids = _flush_crm_batch(
            SimpleNamespace(),
            "deal",
            [
                (2, {"TITLE": "Редизайн сайта"}),
                (3, {"TITLE": "Подключение телефонии"}),
            ],
        )

        self.assertEqual(created_count, 2)
        self.assertEqual(failed_count, 0)
        self.assertEqual(created_ids, [901, 902])
        self.assertEqual(results[0]["status"], "created")
        self.assertEqual(results[0]["record_id"], 901)
        self.assertEqual(results[1]["status"], "created")
        self.assertEqual(results[1]["record_id"], 902)

    @patch("importer.services.import_execution.BitrixAPIBatchRequest")
    def test_flush_crm_batch_marks_row_failed_when_batch_response_has_no_record_id(self, bitrix_api_batch_request):
        bitrix_api_batch_request.return_value = SimpleNamespace(
            result=SimpleNamespace(
                result={"0": {}},
                result_error={},
            )
        )

        results, created_count, failed_count, created_ids = _flush_crm_batch(
            SimpleNamespace(),
            "deal",
            [(2, {"TITLE": "Редизайн сайта"})],
        )

        self.assertEqual(created_count, 0)
        self.assertEqual(failed_count, 1)
        self.assertEqual(created_ids, [])
        self.assertEqual(results[0]["row_number"], 2)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["error"], "Bitrix24 не подтвердил создание записи: ID не получен.")
        self.assertEqual(results[0]["report_entity"], "Сделка")
        self.assertEqual(results[0]["report_title"], "Редизайн сайта")
