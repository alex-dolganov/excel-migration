from django.test import SimpleTestCase

from importer.services.value_normalization import build_discrete_value_keys


class ValueNormalizationServiceTest(SimpleTestCase):
    def test_build_discrete_value_keys_matches_common_boolean_currency_phone_date_and_semantic_aliases(self):
        normalization_pairs = [
            ("yes", "Да"),
            ("1", "Да"),
            ("RUR", "Рубли"),
            ("+7 (999) 123-45-67", "79991234567"),
            ("31.12.2026", "2026-12-31"),
            ("ads", "Реклама"),
        ]

        for left, right in normalization_pairs:
            with self.subTest(left=left, right=right):
                self.assertTrue(
                    build_discrete_value_keys(left).intersection(build_discrete_value_keys(right)),
                )
