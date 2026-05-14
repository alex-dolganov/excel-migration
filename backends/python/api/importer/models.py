import uuid

from django.db import models


class EntityType(models.TextChoices):
    LEAD = "lead", "Lead"
    CONTACT = "contact", "Contact"
    COMPANY = "company", "Company"
    DEAL = "deal", "Deal"
    SMART_PROCESS = "smart_process", "Smart process"
    LINKED_COMPANY_CONTACT = "linked_company_contact", "Linked company + contact"
    LINKED_COMPANY_DEAL = "linked_company_deal", "Linked company + deal"
    TASK = "task", "Task"
    TASK_COMMENT = "task_comment", "Task comment"
    TASK_CHECKLIST_ITEM = "task_checklist_item", "Task checklist item"
    TASK_ATTACHMENT = "task_attachment", "Task attachment"
    CRM_FILES_LEAD = "crm_files_lead", "CRM files: Lead"
    CRM_FILES_CONTACT = "crm_files_contact", "CRM files: Contact"
    CRM_FILES_COMPANY = "crm_files_company", "CRM files: Company"
    CRM_FILES_DEAL = "crm_files_deal", "CRM files: Deal"
    USER = "user", "User"
    DEPARTMENT = "department", "Department"


def import_session_upload_to(instance, filename):
    return f"import-sessions/{instance.portal_member_id}/{instance.id}/{filename}"


class ImportSession(models.Model):
    class SourceFormat(models.TextChoices):
        XLSX = "xlsx", "XLSX"
        XLS = "xls", "XLS"
        CSV = "csv", "CSV"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        UPLOADED = "uploaded", "Uploaded"
        VALIDATED = "validated", "Validated"
        READY = "ready", "Ready"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    EntityType = EntityType

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portal_member_id = models.CharField(max_length=255, db_index=True)
    portal_domain = models.CharField(max_length=255)
    created_by_b24_user_id = models.IntegerField()
    entity_type = models.CharField(max_length=32, choices=EntityType.choices)
    source_format = models.CharField(max_length=16, choices=SourceFormat.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    original_filename = models.CharField(max_length=255)
    stored_file = models.FileField(upload_to=import_session_upload_to, blank=True)
    file_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    upload_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    source_sheet_name = models.CharField(max_length=255, blank=True)
    data_start_row = models.PositiveIntegerField(default=2)
    header_row = models.PositiveIntegerField(default=1)
    total_rows = models.PositiveIntegerField(null=True, blank=True)
    processed_rows = models.PositiveIntegerField(default=0)
    successful_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    preview_data = models.JSONField(default=dict, blank=True)
    import_settings = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_session"
        ordering = ["-created_at"]


class ImportTemplate(models.Model):
    EntityType = EntityType

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portal_member_id = models.CharField(max_length=255, db_index=True)
    portal_domain = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=32, choices=EntityType.choices)
    entity_scope_key = models.CharField(max_length=128, default="", blank=True)
    entity_config = models.JSONField(default=dict, blank=True)
    name = models.CharField(max_length=255)
    mapping_schema = models.JSONField(default=dict)
    column_settings = models.JSONField(default=dict, blank=True)
    dedup_settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "import_template"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["portal_member_id", "entity_type", "entity_scope_key", "name"],
                name="uniq_import_template_per_portal_scope_name",
            ),
        ]


class ImporterUserRole(models.Model):
    class Role(models.TextChoices):
        OPERATOR = "operator", "Operator"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portal_member_id = models.CharField(max_length=255, db_index=True)
    portal_domain = models.CharField(max_length=255)
    b24_user_id = models.IntegerField()
    role = models.CharField(max_length=32, choices=Role.choices)
    granted_by_b24_user_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "importer_user_role"
        ordering = ["b24_user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["portal_member_id", "b24_user_id"],
                name="uniq_importer_role_per_portal_user",
            ),
        ]
