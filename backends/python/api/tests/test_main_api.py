import importlib
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse


class HealthApiTest(TestCase):
    def test_public_healthz_is_available_without_auth(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertEqual(response.json()["backend"], "python")

    def test_authenticated_api_health_remains_protected(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class OpenTelemetrySetupTest(TestCase):
    def test_setup_otel_is_disabled_by_default_in_dev_even_with_endpoint(self):
        with patch.dict(
            os.environ,
            {
                "BUILD_TARGET": "dev",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://host.docker.internal:4318",
                "OTEL_SERVICE_NAME": "b24-app",
            },
            clear=True,
        ):
            import config as config_module
            import otel as otel_module

            importlib.reload(config_module)
            importlib.reload(otel_module)
            otel_module._INITIALIZED = False

            with patch.object(otel_module.logging, "getLogger") as get_logger:
                otel_module.setup_otel()

            get_logger.assert_not_called()


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
