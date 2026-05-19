from django.db import migrations, models


ENTITY_TYPE_CHOICES = [
    ("lead", "Lead"),
    ("contact", "Contact"),
    ("company", "Company"),
    ("deal", "Deal"),
    ("smart_process", "Smart process"),
    ("crm_activity", "CRM activity"),
    ("crm_note", "CRM note"),
    ("linked_company_contact", "Linked company + contact"),
    ("linked_company_deal", "Linked company + deal"),
    ("linked_contact_company", "Linked contact + company"),
    ("linked_contact_deal", "Linked contact + deal"),
    ("linked_deal_company", "Linked deal + company"),
    ("linked_deal_contact", "Linked deal + contact"),
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
]


class Migration(migrations.Migration):

    dependencies = [
        ("importer", "0017_linked_deal_contact_entity_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="importsession",
            name="entity_type",
            field=models.CharField(choices=ENTITY_TYPE_CHOICES, max_length=32),
        ),
        migrations.AlterField(
            model_name="importtemplate",
            name="entity_type",
            field=models.CharField(choices=ENTITY_TYPE_CHOICES, max_length=32),
        ),
        migrations.AlterField(
            model_name="importaliasrule",
            name="entity_type",
            field=models.CharField(choices=ENTITY_TYPE_CHOICES, max_length=32),
        ),
    ]
