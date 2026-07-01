from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from importer.models import ImportAliasRule, ImportTemplate


def create_account(member_id="member-1", domain_url="test.bitrix24.ru"):
    """Minimal Bitrix24Account stand-in accepted by has_permission / view helpers."""
    return SimpleNamespace(
        member_id=member_id,
        domain_url=domain_url,
        b24_user_id=7,
    )


class DeleteImportTemplateApiTest(TestCase):
    def make_template(self, *, member_id="member-1", domain_url="test.bitrix24.ru", name="Lead default"):
        return ImportTemplate.objects.create(
            portal_member_id=member_id,
            portal_domain=domain_url,
            entity_type=ImportTemplate.EntityType.LEAD,
            name=name,
            mapping_schema={"TITLE": {"target_field": "TITLE"}},
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_template_removes_it(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()
        template = self.make_template()

        response = self.client.delete(
            f"{reverse('importer:templates')}?id={template.id}",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"deleted": 1})
        self.assertFalse(ImportTemplate.objects.filter(id=template.id).exists())

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_template_cross_portal_isolation(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()
        foreign = self.make_template(member_id="member-2", domain_url="other.bitrix24.ru", name="Foreign")

        response = self.client.delete(
            f"{reverse('importer:templates')}?id={foreign.id}",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"deleted": 0})
        self.assertTrue(ImportTemplate.objects.filter(id=foreign.id).exists())

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_template_invalid_id_returns_400(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()

        response = self.client.delete(
            f"{reverse('importer:templates')}?id=not-a-uuid",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid template id")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_template_missing_id_returns_400(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()

        response = self.client.delete(
            reverse("importer:templates"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "id is required")


class DeleteImportAliasRuleApiTest(TestCase):
    def make_rule(
        self,
        *,
        member_id="member-1",
        domain_url="test.bitrix24.ru",
        source_label="Телефон",
        normalized_source_label="телефон",
        target_field_id="PHONE",
    ):
        return ImportAliasRule.objects.create(
            portal_member_id=member_id,
            portal_domain=domain_url,
            entity_type=ImportAliasRule.EntityType.LEAD,
            source_label=source_label,
            normalized_source_label=normalized_source_label,
            target_field_id=target_field_id,
            created_by_b24_user_id=7,
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_alias_rule_removes_it(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()
        rule = self.make_rule()

        response = self.client.delete(
            f"{reverse('importer:alias-rules')}?id={rule.id}",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"deleted": 1})
        self.assertFalse(ImportAliasRule.objects.filter(id=rule.id).exists())

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_alias_rule_cross_portal_isolation(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()
        foreign = self.make_rule(member_id="member-2", domain_url="other.bitrix24.ru")

        response = self.client.delete(
            f"{reverse('importer:alias-rules')}?id={foreign.id}",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"deleted": 0})
        self.assertTrue(ImportAliasRule.objects.filter(id=foreign.id).exists())

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_alias_rule_invalid_id_returns_400(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()

        response = self.client.delete(
            f"{reverse('importer:alias-rules')}?id=not-a-uuid",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid rule id")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_delete_alias_rule_missing_id_returns_400(self, get_from_jwt_token):
        get_from_jwt_token.return_value = create_account()

        response = self.client.delete(
            reverse("importer:alias-rules"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "id is required")
