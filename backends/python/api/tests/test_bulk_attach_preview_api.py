from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class BulkAttachPreviewApiTest(TestCase):
    @patch("importer.services.bulk_attach.fetch_crm_entities_page")
    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_preview_returns_only_five_sample_entities_even_when_more_are_available(
        self,
        get_from_jwt_token,
        fetch_crm_entities_page,
    ):
        get_from_jwt_token.return_value = SimpleNamespace(
            member_id="member-1",
            domain_url="test.bitrix24.ru",
            b24_user_id=7,
        )
        fetch_crm_entities_page.return_value = {
            "items": [
                {"ID": 101, "TITLE": "Сделка 101"},
                {"ID": 102, "TITLE": "Сделка 102"},
                {"ID": 103, "TITLE": "Сделка 103"},
                {"ID": 104, "TITLE": "Сделка 104"},
                {"ID": 105, "TITLE": "Сделка 105"},
                {"ID": 106, "TITLE": "Сделка 106"},
                {"ID": 107, "TITLE": "Сделка 107"},
            ],
            "total": 2048,
            "next": 50,
        }

        response = self.client.post(
            reverse("importer:crm-filter-preview"),
            data={
                "entity_type": "deal",
                "filter": {},
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total"], 2048)
        self.assertEqual(response.json()["has_more"], True)
        self.assertEqual(
            response.json()["sample"],
            [
                {"id": 101, "title": "Сделка 101"},
                {"id": 102, "title": "Сделка 102"},
                {"id": 103, "title": "Сделка 103"},
                {"id": 104, "title": "Сделка 104"},
                {"id": 105, "title": "Сделка 105"},
            ],
        )
