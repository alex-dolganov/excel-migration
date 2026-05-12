from importer.models import ImporterUserRole


ROLE_PORTAL_ADMIN = "portal_admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ASSIGNABLE_ROLES = {ROLE_OPERATOR, ROLE_VIEWER}
PERMISSION_CODES = {
    ROLE_PORTAL_ADMIN: {
        "roles.manage",
        "templates.manage",
        "sessions.create",
        "sessions.edit_own",
        "sessions.view",
        "sessions.run",
        "sessions.cancel",
        "reports.view",
    },
    ROLE_OPERATOR: {
        "templates.manage",
        "sessions.create",
        "sessions.edit_own",
        "sessions.view",
        "sessions.run",
        "sessions.cancel",
        "reports.view",
    },
    ROLE_VIEWER: {
        "sessions.view",
        "reports.view",
    },
}


def is_portal_admin(account) -> bool:
    admin_flag = getattr(account, "is_b24_user_admin", None)
    if admin_flag is None:
        return True
    return bool(admin_flag)


def resolve_role(account):
    if is_portal_admin(account):
        return ROLE_PORTAL_ADMIN

    assignment = ImporterUserRole.objects.filter(
        portal_member_id=str(getattr(account, "member_id", "")),
        b24_user_id=int(getattr(account, "b24_user_id", 0) or 0),
    ).only("role").first()

    if assignment is None:
        return ROLE_PORTAL_ADMIN

    return str(assignment.role)


def get_permissions(role) -> list[str]:
    return sorted(PERMISSION_CODES.get(str(role or ""), set()))


def has_permission(account, permission_code: str) -> bool:
    role = resolve_role(account)
    return permission_code in PERMISSION_CODES.get(str(role or ""), set())


def is_session_owner(account, session) -> bool:
    return int(getattr(account, "b24_user_id", 0) or 0) == int(getattr(session, "created_by_b24_user_id", 0) or 0)


def can_edit_session(account, session) -> bool:
    return has_permission(account, "sessions.edit_own") and (is_portal_admin(account) or is_session_owner(account, session))


def can_run_session(account, session) -> bool:
    return has_permission(account, "sessions.run") and (is_portal_admin(account) or is_session_owner(account, session))


def can_cancel_session(account, session) -> bool:
    return has_permission(account, "sessions.cancel") and (is_portal_admin(account) or is_session_owner(account, session))


def normalize_assignable_role(role_value: str) -> str:
    normalized_role = str(role_value or "").strip().lower()
    if normalized_role not in ASSIGNABLE_ROLES:
        raise ValueError("Unsupported role")
    return normalized_role
