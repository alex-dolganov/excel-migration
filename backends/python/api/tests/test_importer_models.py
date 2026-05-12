from django.test import TestCase

from importer.models import ImportSession, ImportTemplate


class ImportSessionModelTest(TestCase):
    def test_create_draft_session(self):
        session = ImportSession.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            created_by_b24_user_id=7,
            entity_type=ImportSession.EntityType.LEAD,
            source_format=ImportSession.SourceFormat.XLSX,
            status=ImportSession.Status.DRAFT,
            original_filename="leads.xlsx",
        )

        self.assertEqual(session.status, ImportSession.Status.DRAFT)
        self.assertEqual(session.original_filename, "leads.xlsx")


class ImportTemplateModelTest(TestCase):
    def test_template_defaults_to_active(self):
        template = ImportTemplate.objects.create(
            portal_member_id="member-1",
            portal_domain="test.bitrix24.ru",
            entity_type=ImportTemplate.EntityType.LEAD,
            name="Lead import default",
            mapping_schema={"TITLE": "title"},
        )

        self.assertTrue(template.is_active)
