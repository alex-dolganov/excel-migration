from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from b24pysdk.error import BitrixRequestTimeout
import requests

from importer.services.import_execution import _bitrix_retry, _flush_crm_batch, _flush_crm_batch_with_fallback


class FakeBitrixInvitationLimitError(Exception):
    def __init__(self):
        super().__init__("Unknown error.")
        self.json_response = {
            "error": "ERROR_USER_INVITATION_LIMIT",
            "error_description": "Unknown error.",
        }


class FakeBitrixUnknownUserInviteError(Exception):
    def __init__(self):
        super().__init__("Unknown error.")


class ImportExecutionBatchTest(SimpleTestCase):
    @patch("importer.services.import_execution.time.sleep")
    def test_bitrix_retry_waits_and_retries_when_bitrix_blocks_method_by_operation_time(self, sleep):
        attempts = {"count": 0}

        def flaky_call():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("Method is blocked due to operation time limit.")
            return 907

        result = _bitrix_retry(flaky_call)

        self.assertEqual(result, 907)
        self.assertEqual(attempts["count"], 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [30, 60])

    @patch("importer.services.import_execution.time.sleep")
    def test_bitrix_retry_does_not_sleep_for_daily_invitation_limit_error(self, sleep):
        def broken_call():
            raise FakeBitrixInvitationLimitError()

        with self.assertRaises(FakeBitrixInvitationLimitError):
            _bitrix_retry(broken_call)

        sleep.assert_not_called()

    @patch("importer.services.import_execution.time.sleep")
    def test_bitrix_retry_does_not_sleep_for_unknown_error_when_unknown_retry_is_disabled(self, sleep):
        def broken_call():
            raise FakeBitrixUnknownUserInviteError()

        with self.assertRaises(FakeBitrixUnknownUserInviteError):
            _bitrix_retry(broken_call, allow_unknown_error_as_operation_time_limit=False)

        sleep.assert_not_called()

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

    @patch("importer.services.import_execution.time.sleep")
    @patch("importer.services.import_execution._flush_crm_batch")
    def test_flush_crm_batch_with_fallback_raises_immediately_on_operation_time_limit(self, flush_crm_batch, sleep):
        """OTL is a server-side block — splitting does not help, must raise without recursion."""
        call_count = {"n": 0}

        def fake_flush(_account, _entity_type, pending_batch):
            call_count["n"] += 1
            raise RuntimeError("Method is blocked due to operation time limit.")

        flush_crm_batch.side_effect = fake_flush

        with self.assertRaises(RuntimeError):
            _flush_crm_batch_with_fallback(
                SimpleNamespace(),
                "deal",
                [
                    (2, {"TITLE": "Сделка 2"}),
                    (3, {"TITLE": "Сделка 3"}),
                    (4, {"TITLE": "Сделка 4"}),
                ],
            )

        # _bitrix_retry with _OPERATION_TIME_LIMIT_RETRY_WAITS=[30,60,120,300] makes
        # 5 calls total (initial + 4 retries). _flush_crm_batch_with_fallback must NOT
        # recurse into split sub-batches after that — call count stays at 5.
        self.assertEqual(call_count["n"], 5)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [30, 60, 120, 300])

    @patch("importer.services.import_execution._flush_crm_batch")
    def test_flush_crm_batch_with_fallback_splits_timeout_batch_until_rows_succeed(self, flush_crm_batch):
        def fake_flush(_account, _entity_type, pending_batch):
            if len(pending_batch) > 1:
                raise BitrixRequestTimeout(
                    requests.exceptions.ReadTimeout("Read timed out. (read timeout=10)"),
                    timeout=10,
                )

            row_number, payload = pending_batch[0]
            record_id = 900 + row_number
            return (
                [
                    {
                        "row_number": row_number,
                        "status": "created",
                        "record_id": record_id,
                        "report_entity": "Сделка",
                        "report_title": payload["TITLE"],
                    }
                ],
                1,
                0,
                [record_id],
            )

        flush_crm_batch.side_effect = fake_flush

        results, created_count, failed_count, created_ids = _flush_crm_batch_with_fallback(
            SimpleNamespace(),
            "deal",
            [
                (2, {"TITLE": "Сделка 2"}),
                (3, {"TITLE": "Сделка 3"}),
                (4, {"TITLE": "Сделка 4"}),
                (5, {"TITLE": "Сделка 5"}),
            ],
        )

        self.assertEqual(created_count, 4)
        self.assertEqual(failed_count, 0)
        self.assertEqual(created_ids, [902, 903, 904, 905])
        self.assertEqual([item["row_number"] for item in results], [2, 3, 4, 5])
        self.assertTrue(flush_crm_batch.call_count > 1)
