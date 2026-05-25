from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from importer.models import ImportSession, ImporterUserRole
from importer.services.permissions import (
    PERMISSION_CODES,
    ROLE_OPERATOR,
    ROLE_PORTAL_ADMIN,
    ROLE_VIEWER,
    has_permission,
    is_session_owner,
    resolve_role,
)


class ImportPermissionsApiTest(TestCase):
    def create_account(self, *, user_id=7, is_admin=False, member_id="member-1", domain_url="test.bitrix24.ru"):
        return SimpleNamespace(
            member_id=member_id,
            domain_url=domain_url,
            b24_user_id=user_id,
            is_b24_user_admin=is_admin,
        )

    def create_role(self, *, user_id=7, role=ROLE_VIEWER, granted_by=1, member_id="member-1", domain_url="test.bitrix24.ru"):
        return ImporterUserRole.objects.create(
            portal_member_id=member_id,
            portal_domain=domain_url,
            b24_user_id=user_id,
            role=role,
            granted_by_b24_user_id=granted_by,
        )

    def create_session(self, *, created_by=7, member_id="member-1", domain_url="test.bitrix24.ru"):
        return ImportSession.objects.create(
            portal_member_id=member_id,
            portal_domain=domain_url,
            created_by_b24_user_id=created_by,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="leads.xlsx",
        )

    def test_permission_service_grants_full_access_regardless_of_admin_flag_or_local_role(self):
        admin_account = self.create_account(user_id=11, is_admin=True)
        operator_account = self.create_account(user_id=12, is_admin=False)
        viewer_account = self.create_account(user_id=13, is_admin=False)
        unknown_account = self.create_account(user_id=14, is_admin=False)
        owned_session = self.create_session(created_by=12)

        self.create_role(user_id=12, role=ROLE_OPERATOR)
        self.create_role(user_id=13, role=ROLE_VIEWER)

        self.assertEqual(resolve_role(admin_account), ROLE_PORTAL_ADMIN)
        self.assertEqual(resolve_role(operator_account), ROLE_PORTAL_ADMIN)
        self.assertEqual(resolve_role(viewer_account), ROLE_PORTAL_ADMIN)
        self.assertEqual(resolve_role(unknown_account), ROLE_PORTAL_ADMIN)
        self.assertTrue(has_permission(admin_account, "roles.manage"))
        self.assertTrue(has_permission(operator_account, "sessions.run"))
        self.assertTrue(has_permission(viewer_account, "sessions.run"))
        self.assertTrue(has_permission(unknown_account, "roles.manage"))
        self.assertTrue(has_permission(unknown_account, "sessions.run"))
        self.assertTrue(is_session_owner(operator_account, owned_session))
        self.assertFalse(is_session_owner(viewer_account, owned_session))

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_permissions_me_returns_portal_admin_payload(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account(is_admin=True)

        response = self.client.get(
            reverse("importer:permissions-me"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["role"], ROLE_PORTAL_ADMIN)
        self.assertEqual(response.json()["item"]["user_id"], 7)
        self.assertEqual(response.json()["item"]["is_portal_admin"], True)
        self.assertEqual(response.json()["item"]["permissions"], sorted(PERMISSION_CODES[ROLE_PORTAL_ADMIN]))

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_permissions_me_ignores_local_viewer_role_and_returns_full_access_payload(self, get_from_jwt_token):
        self.create_role(user_id=7, role="viewer")
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            reverse("importer:permissions-me"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["role"], ROLE_PORTAL_ADMIN)
        self.assertEqual(response.json()["item"]["is_portal_admin"], True)
        self.assertEqual(response.json()["item"]["permissions"], sorted(PERMISSION_CODES[ROLE_PORTAL_ADMIN]))

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_permissions_me_returns_full_access_for_user_without_local_role(self, get_from_jwt_token):
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        response = self.client.get(
            reverse("importer:permissions-me"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["role"], ROLE_PORTAL_ADMIN)
        self.assertEqual(response.json()["item"]["is_portal_admin"], True)
        self.assertEqual(response.json()["item"]["permissions"], sorted(PERMISSION_CODES[ROLE_PORTAL_ADMIN]))

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_portal_admin_can_list_and_assign_roles(self, get_from_jwt_token):
        self.create_role(user_id=21, role=ROLE_VIEWER, granted_by=7)
        get_from_jwt_token.return_value = self.create_account(is_admin=True)

        create_response = self.client.post(
            reverse("importer:roles"),
            data={
                "b24_user_id": 22,
                "role": ROLE_OPERATOR,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["item"]["role"], ROLE_OPERATOR)

        list_response = self.client.get(
            reverse("importer:roles"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [(item["b24_user_id"], item["role"]) for item in list_response.json()["items"]],
            [(21, ROLE_VIEWER), (22, ROLE_OPERATOR)],
        )

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_non_admin_can_manage_roles_when_import_access_is_open(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        list_response = self.client.get(
            reverse("importer:roles"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        create_response = self.client.post(
            reverse("importer:roles"),
            data={
                "b24_user_id": 22,
                "role": ROLE_VIEWER,
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["item"]["role"], "viewer")

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_any_user_can_view_and_mutate_importer_state_when_import_access_is_open(self, get_from_jwt_token):
        self.create_role(user_id=7, role="viewer")
        session = self.create_session(created_by=12)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        list_response = self.client.get(
            reverse("importer:sessions"),
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        create_response = self.client.post(
            reverse("importer:sessions"),
            data={
                "entity_type": "lead",
                "source_format": "xlsx",
                "original_filename": "leads.xlsx",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        mapping_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": session.id}),
            data={"mapping": {}},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        run_response = self.client.post(
            reverse("importer:session-run", kwargs={"session_id": session.id}),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertNotEqual(create_response.status_code, 403)
        self.assertNotEqual(mapping_response.status_code, 403)
        self.assertNotEqual(run_response.status_code, 403)

    @patch("main.utils.decorators.auth_required.Bitrix24Account.get_from_jwt_token")
    def test_any_user_can_edit_foreign_session_when_import_access_is_open(self, get_from_jwt_token):
        self.create_role(user_id=7, role=ROLE_OPERATOR)
        own_session = self.create_session(created_by=7)
        foreign_session = self.create_session(created_by=21)
        get_from_jwt_token.return_value = self.create_account(is_admin=False)

        own_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": own_session.id}),
            data={"mapping": {}},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        foreign_response = self.client.patch(
            reverse("importer:session-mapping", kwargs={"session_id": foreign_session.id}),
            data={"mapping": {}},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertNotEqual(own_response.status_code, 403)
        self.assertNotEqual(foreign_response.status_code, 403)
