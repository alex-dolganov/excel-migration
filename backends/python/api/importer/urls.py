from django.urls import path

from .views import (
    import_departments,
    import_example_template_xlsx,
    import_fields,
    import_permissions_me,
    import_roles,
    import_session_mapping,
    import_session_apply_template,
    import_session_cancel,
    import_session_detail,
    import_session_dry_run,
    import_session_preview,
    import_session_report_csv,
    import_session_retry_failed,
    import_session_run,
    import_session_upload,
    import_session_validate,
    import_sessions,
    import_templates,
)

app_name = "importer"

urlpatterns = [
    path("api/import-example-template.xlsx", import_example_template_xlsx, name="example-template-xlsx"),
    path("api/import-sessions", import_sessions, name="sessions"),
    path("api/import-sessions/<uuid:session_id>", import_session_detail, name="session-detail"),
    path("api/import-sessions/<uuid:session_id>/upload", import_session_upload, name="session-upload"),
    path("api/import-sessions/<uuid:session_id>/preview", import_session_preview, name="session-preview"),
    path("api/import-sessions/<uuid:session_id>/mapping", import_session_mapping, name="session-mapping"),
    path("api/import-sessions/<uuid:session_id>/apply-template", import_session_apply_template, name="session-apply-template"),
    path("api/import-sessions/<uuid:session_id>/dry-run", import_session_dry_run, name="session-dry-run"),
    path("api/import-sessions/<uuid:session_id>/validate", import_session_validate, name="session-validate"),
    path("api/import-sessions/<uuid:session_id>/run", import_session_run, name="session-run"),
    path("api/import-sessions/<uuid:session_id>/cancel", import_session_cancel, name="session-cancel"),
    path("api/import-sessions/<uuid:session_id>/report.csv", import_session_report_csv, name="session-report-csv"),
    path("api/import-sessions/<uuid:session_id>/retry-failed", import_session_retry_failed, name="session-retry-failed"),
    path("api/import-fields", import_fields, name="fields"),
    path("api/import-departments", import_departments, name="departments"),
    path("api/import-templates", import_templates, name="templates"),
    path("api/import-permissions/me", import_permissions_me, name="permissions-me"),
    path("api/import-roles", import_roles, name="roles"),
]
