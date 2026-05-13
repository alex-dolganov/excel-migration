from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class ImportSmartProcessesApiTest(TestCase):
    @patch("importer.views.fetch_smart_process_types")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_returns_portal_smart_processes(self, get_from_jwt_token, fetch_smart_process_types):
        account = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
            client=SimpleNamespace(),
        )
        get_from_jwt_token.return_value = account
        fetch_smart_process_types.return_value = [
            {
                "entityTypeId": 128,
                "title": "Согласования",
                "isCategoriesEnabled": False,
                "isStagesEnabled": True,
                "isClientEnabled": True,
            },
            {
                "entityTypeId": 144,
                "title": "Выезды",
                "isCategoriesEnabled": True,
                "isStagesEnabled": True,
                "isClientEnabled": False,
            },
        ]

        response = self.client.get(
            reverse("importer:smart-processes"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["items"],
            [
                {
                    "entityTypeId": 128,
                    "title": "Согласования",
                    "isCategoriesEnabled": False,
                    "isStagesEnabled": True,
                    "isClientEnabled": True,
                },
                {
                    "entityTypeId": 144,
                    "title": "Выезды",
                    "isCategoriesEnabled": True,
                    "isStagesEnabled": True,
                    "isClientEnabled": False,
                },
            ],
        )
        fetch_smart_process_types.assert_called_once_with(account)
