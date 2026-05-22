import requests
import urllib3
from django.test import SimpleTestCase

from importer.services.error_messages import (
    BITRIX_DAILY_INVITATION_LIMIT_ERROR,
    BITRIX_UNREACHABLE_ERROR,
    format_import_error,
)


class FakeBitrixInvitationLimitError(Exception):
    def __init__(self):
        super().__init__("Unknown error.")
        self.json_response = {
            "error": "ERROR_USER_INVITATION_LIMIT",
            "error_description": "Unknown error.",
        }


class ErrorMessagesTest(SimpleTestCase):
    def test_format_import_error_explains_operation_time_limit_in_russian(self):
        self.assertEqual(
            format_import_error("Method is blocked due to operation time limit."),
            "Bitrix24 временно заблокировал метод из-за лимита времени выполнения. Подождите 10 минут и повторите импорт.",
        )

    def test_format_import_error_uses_error_description_from_dict(self):
        self.assertEqual(
            format_import_error(
                {
                    "error": "",
                    "error_description": 'Неверное значение поля "Валюта"',
                }
            ),
            'Неверное значение поля "Валюта"',
        )

    def test_format_import_error_uses_error_description_from_dict_string(self):
        self.assertEqual(
            format_import_error(
                """{'error': '', 'error_description': 'Неверное значение поля "Валюта"'}"""
            ),
            'Неверное значение поля "Валюта"',
        )

    def test_format_import_error_hides_portal_domain_for_dns_resolution_errors(self):
        error = requests.exceptions.ConnectionError(
            urllib3.exceptions.NameResolutionError(
                "mp24.bitrix24.ru",
                "/rest/crm.deal.fields.json",
                OSError(-5, "No address associated with hostname"),
            )
        )

        self.assertEqual(format_import_error(error), BITRIX_UNREACHABLE_ERROR)

    def test_format_import_error_detects_daily_invitation_limit_from_bitrix_json_response(self):
        self.assertEqual(
            format_import_error(FakeBitrixInvitationLimitError()),
            BITRIX_DAILY_INVITATION_LIMIT_ERROR,
        )
