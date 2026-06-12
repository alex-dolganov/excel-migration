import requests
import urllib3
from django.test import SimpleTestCase

from importer.services.error_messages import (
    BITRIX_DAILY_INVITATION_LIMIT_ERROR,
    BITRIX_UNREACHABLE_ERROR,
    format_import_error,
    get_import_error_text,
    normalize_import_language,
    set_import_error_language,
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


class ErrorMessageLocalizationTest(SimpleTestCase):
    def tearDown(self):
        set_import_error_language("ru")

    def test_normalize_import_language_maps_browser_and_portal_tags(self):
        self.assertEqual(normalize_import_language("pt-BR"), "br")
        self.assertEqual(normalize_import_language("pt"), "br")
        self.assertEqual(normalize_import_language("br"), "br")
        self.assertEqual(normalize_import_language("en-US"), "en")
        self.assertEqual(normalize_import_language("en"), "en")
        self.assertEqual(normalize_import_language("de"), "ru")
        self.assertEqual(normalize_import_language(None), "ru")

    def test_format_import_error_localizes_operation_time_limit_to_english(self):
        set_import_error_language("en")
        self.assertEqual(
            format_import_error("Method is blocked due to operation time limit."),
            "Bitrix24 temporarily blocked the method due to the operation time limit. Wait 10 minutes and retry the import.",
        )

    def test_format_import_error_localizes_operation_time_limit_to_portuguese(self):
        set_import_error_language("pt-BR")
        self.assertEqual(
            format_import_error("Method is blocked due to operation time limit."),
            "O Bitrix24 bloqueou temporariamente o método devido ao limite de tempo de execução. Aguarde 10 minutos e repita a importação.",
        )

    def test_format_import_error_defaults_to_russian_without_language(self):
        self.assertEqual(
            format_import_error("Method is blocked due to operation time limit."),
            "Bitrix24 временно заблокировал метод из-за лимита времени выполнения. Подождите 10 минут и повторите импорт.",
        )

    def test_get_import_error_text_falls_back_to_russian_for_unknown_language(self):
        set_import_error_language("de")
        self.assertEqual(
            get_import_error_text("no_description"),
            "Без описания",
        )
