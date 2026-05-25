ROLE_NONE = "none"
ROLE_PORTAL_ADMIN = "portal_admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ASSIGNABLE_ROLES = {ROLE_OPERATOR, ROLE_VIEWER}
PERMISSION_CODES = {
    ROLE_NONE: set(),
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
    # Temporary rollback: keep importer fully available regardless of Bitrix24
    # portal admin status or assigned local importer role.
    return True


def resolve_role(account):
    return ROLE_PORTAL_ADMIN


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
