# Generated for task child entity types (task_comment, task_checklist_item)

from django.db import migrations, models


ENTITY_TYPE_CHOICES = [
    ("lead", "Lead"),
    ("contact", "Contact"),
    ("company", "Company"),
    ("deal", "Deal"),
    ("task", "Task"),
    ("task_comment", "Task comment"),
    ("task_checklist_item", "Task checklist item"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("importer", "0005_importeruserrole"),
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
