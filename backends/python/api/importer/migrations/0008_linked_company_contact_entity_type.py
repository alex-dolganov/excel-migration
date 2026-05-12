# Generated for linked company + contact entity type

from django.db import migrations, models


ENTITY_TYPE_CHOICES = [
    ("lead", "Lead"),
    ("contact", "Contact"),
    ("company", "Company"),
    ("deal", "Deal"),
    ("linked_company_contact", "Linked company + contact"),
    ("task", "Task"),
    ("task_comment", "Task comment"),
    ("task_checklist_item", "Task checklist item"),
    ("task_attachment", "Task attachment"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("importer", "0007_task_attachment_entity_type"),
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
    ]
