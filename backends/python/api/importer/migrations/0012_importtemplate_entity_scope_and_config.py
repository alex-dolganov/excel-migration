from django.db import migrations, models


def _column_exists(schema_editor, table_name, column_name):
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, table_name)

    for column in columns:
        existing_name = getattr(column, "name", None)
        if existing_name is None and isinstance(column, (list, tuple)) and column:
            existing_name = column[0]
        if existing_name == column_name:
            return True

    return False


def _get_column_details(schema_editor, table_name, column_name):
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, table_name)

    for column in columns:
        existing_name = getattr(column, "name", None)
        if existing_name is None and isinstance(column, (list, tuple)) and column:
            existing_name = column[0]
        if existing_name == column_name:
            return column

    return None


def _add_import_template_field_if_missing(apps, schema_editor, field_name, field):
    ImportTemplate = apps.get_model("importer", "ImportTemplate")
    table_name = ImportTemplate._meta.db_table

    if _column_exists(schema_editor, table_name, field_name):
        return

    field.set_attributes_from_name(field_name)
    field.model = ImportTemplate
    schema_editor.add_field(ImportTemplate, field)


def add_entity_config_field(apps, schema_editor):
    _add_import_template_field_if_missing(
        apps,
        schema_editor,
        "entity_config",
        models.JSONField(blank=True, default=dict),
    )


def add_entity_scope_key_field(apps, schema_editor):
    ImportTemplate = apps.get_model("importer", "ImportTemplate")
    table_name = ImportTemplate._meta.db_table
    existing_column = _get_column_details(schema_editor, table_name, "entity_scope_key")
    new_field = models.CharField(blank=True, default="", max_length=128)
    new_field.set_attributes_from_name("entity_scope_key")
    new_field.model = ImportTemplate

    if existing_column is None:
        schema_editor.add_field(ImportTemplate, new_field)
        return

    current_size = getattr(existing_column, "internal_size", None)
    if isinstance(current_size, int) and current_size > 128:
        old_field = models.CharField(blank=True, default="", max_length=current_size)
        old_field.set_attributes_from_name("entity_scope_key")
        old_field.model = ImportTemplate
        schema_editor.alter_field(ImportTemplate, old_field, new_field)


def populate_import_template_scope(apps, schema_editor):
    ImportTemplate = apps.get_model("importer", "ImportTemplate")

    for template in ImportTemplate.objects.all():
        entity_config = template.entity_config if isinstance(template.entity_config, dict) else {}
        if template.entity_type == "smart_process":
            entity_type_id = 0
            raw_entity_type_id = entity_config.get("entityTypeId")
            try:
                entity_type_id = int(raw_entity_type_id)
            except (TypeError, ValueError):
                entity_type_id = 0
            scope_key = f"smart_process:{entity_type_id}" if entity_type_id > 0 else "smart_process:unknown"
        else:
            scope_key = ""

        template.entity_scope_key = scope_key
        template.save(update_fields=["entity_scope_key"])


def sync_import_template_constraints(apps, schema_editor):
    ImportTemplate = apps.get_model("importer", "ImportTemplate")
    table_name = ImportTemplate._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)

    old_constraint_name = "uniq_import_template_per_portal_entity_name"
    new_constraint_name = "uniq_import_template_per_portal_scope_name"

    if old_constraint_name in constraints:
        schema_editor.remove_constraint(
            ImportTemplate,
            models.UniqueConstraint(
                fields=("portal_member_id", "entity_type", "name"),
                name=old_constraint_name,
            ),
        )

    if new_constraint_name not in constraints:
        schema_editor.add_constraint(
            ImportTemplate,
            models.UniqueConstraint(
                fields=("portal_member_id", "entity_type", "entity_scope_key", "name"),
                name=new_constraint_name,
            ),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("importer", "0011_smart_process_entity_type"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_entity_config_field, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="importtemplate",
                    name="entity_config",
                    field=models.JSONField(blank=True, default=dict),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_entity_scope_key_field, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="importtemplate",
                    name="entity_scope_key",
                    field=models.CharField(blank=True, default="", max_length=128),
                ),
            ],
        ),
        migrations.RunPython(populate_import_template_scope, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(sync_import_template_constraints, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="importtemplate",
                    name="uniq_import_template_per_portal_entity_name",
                ),
                migrations.AddConstraint(
                    model_name="importtemplate",
                    constraint=models.UniqueConstraint(
                        fields=("portal_member_id", "entity_type", "entity_scope_key", "name"),
                        name="uniq_import_template_per_portal_scope_name",
                    ),
                ),
            ],
        ),
    ]
