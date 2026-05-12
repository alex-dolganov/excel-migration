from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse


class GetTokenApiTest(TestCase):
    @patch("main.utils.decorators.auth_required.Bitrix24Account.update_or_create_from_oauth_placement_data")
    @patch("main.utils.decorators.auth_required.OAuthPlacementData.from_dict")
    def test_get_token_persists_portal_admin_flag_from_request(self, oauth_from_dict, update_or_create):
        oauth_from_dict.return_value = SimpleNamespace()

        account = MagicMock()
        account.is_b24_user_admin = False
        account.create_jwt_token.return_value = "jwt-token"
        update_or_create.return_value = (account, False)

        response = self.client.post(
            reverse("get_token"),
            data={
                "DOMAIN": "example.bitrix24.ru",
                "AUTH_ID": "access-token",
                "REFRESH_ID": "refresh-token",
                "member_id": "member-1",
                "user_id": 7,
                "status": "L",
                "IS_ADMIN": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"token": "jwt-token"})
        self.assertIs(account.is_b24_user_admin, True)
        account.save.assert_called_once_with(update_fields=["is_b24_user_admin"])
