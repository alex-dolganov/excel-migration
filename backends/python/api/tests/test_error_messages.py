from django.test import SimpleTestCase

from importer.services.error_messages import format_import_error


class ErrorMessagesTest(SimpleTestCase):
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
