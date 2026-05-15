from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("importer", "0013_linked_company_deal_entity_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportAliasRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("portal_member_id", models.CharField(db_index=True, max_length=255)),
                ("portal_domain", models.CharField(max_length=255)),
                ("entity_type", models.CharField(choices=[
                    ("lead", "Lead"),
                    ("contact", "Contact"),
                    ("company", "Company"),
                    ("deal", "Deal"),
                    ("smart_process", "Smart process"),
                    ("linked_company_contact", "Linked company + contact"),
                    ("linked_company_deal", "Linked company + deal"),
                    ("task", "Task"),
                    ("task_comment", "Task comment"),
                    ("task_checklist_item", "Task checklist item"),
                    ("task_attachment", "Task attachment"),
                    ("crm_files_lead", "CRM files: Lead"),
                    ("crm_files_contact", "CRM files: Contact"),
                    ("crm_files_company", "CRM files: Company"),
                    ("crm_files_deal", "CRM files: Deal"),
                    ("user", "User"),
                    ("department", "Department"),
                ], max_length=32)),
                ("entity_scope_key", models.CharField(blank=True, default="", max_length=128)),
                ("source_label", models.CharField(max_length=255)),
                ("normalized_source_label", models.CharField(max_length=255)),
                ("target_field_id", models.CharField(max_length=128)),
                ("created_by_b24_user_id", models.IntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "import_alias_rule",
                "ordering": ["source_label", "target_field_id"],
            },
        ),
        migrations.AddConstraint(
            model_name="importaliasrule",
            constraint=models.UniqueConstraint(
                fields=("portal_member_id", "entity_type", "entity_scope_key", "normalized_source_label"),
                name="uniq_import_alias_rule_per_portal_scope_label",
            ),
        ),
    ]
