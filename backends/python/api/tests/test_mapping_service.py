from django.test import SimpleTestCase

from importer.services.mapping import build_candidate_mapping_bundle


class ImportMappingServiceTest(SimpleTestCase):
    def test_candidate_mapping_auto_matches_russian_task_headers_to_english_task_fields(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Название задачи", "Ответственный", "Крайний срок"],
            columns=["A", "B", "C"],
            fields=[
                {"id": "TITLE", "title": "Title"},
                {"id": "RESPONSIBLE_ID", "title": "Responsible"},
                {"id": "DEADLINE", "title": "Deadline"},
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping,
            {
                "TITLE": {
                    "source_header": "Название задачи",
                    "column": "A",
                    "target_field": "TITLE",
                    "match_type": "fuzzy",
                },
                "RESPONSIBLE_ID": {
                    "source_header": "Ответственный",
                    "column": "B",
                    "target_field": "RESPONSIBLE_ID",
                    "match_type": "fuzzy",
                },
                "DEADLINE": {
                    "source_header": "Крайний срок",
                    "column": "C",
                    "target_field": "DEADLINE",
                    "match_type": "fuzzy",
                },
            },
        )

    def test_candidate_mapping_auto_matches_short_linked_contact_last_name_header(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Фамилия"],
            columns=["A"],
            fields=[
                {
                    "id": "CONTACT__LAST_NAME",
                    "title": "Контакт / Фамилия контакта",
                    "linked_entity": "contact",
                },
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping["CONTACT__LAST_NAME"],
            {
                "source_header": "Фамилия",
                "column": "A",
                "target_field": "CONTACT__LAST_NAME",
                "match_type": "fuzzy",
            },
        )

    def test_candidate_mapping_auto_matches_linked_contact_last_name_when_header_uses_entity_suffix(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Фамилия контакта"],
            columns=["A"],
            fields=[
                {
                    "id": "CONTACT__LAST_NAME",
                    "title": "Контакт / Фамилия",
                    "linked_entity": "contact",
                },
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping["CONTACT__LAST_NAME"],
            {
                "source_header": "Фамилия контакта",
                "column": "A",
                "target_field": "CONTACT__LAST_NAME",
                "match_type": "fuzzy",
            },
        )

    def test_candidate_mapping_auto_matches_short_linked_deal_stage_header(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Стадия"],
            columns=["A"],
            fields=[
                {
                    "id": "DEAL__STAGE_ID",
                    "title": "Сделка / Стадия сделки",
                    "linked_entity": "deal",
                },
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping["DEAL__STAGE_ID"],
            {
                "source_header": "Стадия",
                "column": "A",
                "target_field": "DEAL__STAGE_ID",
                "match_type": "fuzzy",
            },
        )

    def test_candidate_mapping_auto_matches_linked_deal_stage_when_header_uses_entity_suffix(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Стадия сделки"],
            columns=["A"],
            fields=[
                {
                    "id": "DEAL__STAGE_ID",
                    "title": "Сделка / Стадия",
                    "linked_entity": "deal",
                },
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping["DEAL__STAGE_ID"],
            {
                "source_header": "Стадия сделки",
                "column": "A",
                "target_field": "DEAL__STAGE_ID",
                "match_type": "fuzzy",
            },
        )

    def test_candidate_mapping_auto_matches_russian_deal_title_header_to_generic_title_field(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Название сделки"],
            columns=["A"],
            fields=[
                {"id": "TITLE", "title": "Title"},
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping["TITLE"],
            {
                "source_header": "Название сделки",
                "column": "A",
                "target_field": "TITLE",
                "match_type": "fuzzy",
            },
        )

    def test_candidate_mapping_auto_matches_russian_company_title_header_to_generic_title_field(self):
        candidate_mapping = build_candidate_mapping_bundle(
            headers=["Название компании"],
            columns=["A"],
            fields=[
                {"id": "TITLE", "title": "Title"},
            ],
        )["mapping"]

        self.assertEqual(
            candidate_mapping["TITLE"],
            {
                "source_header": "Название компании",
                "column": "A",
                "target_field": "TITLE",
                "match_type": "fuzzy",
            },
        )
