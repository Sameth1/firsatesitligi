import unittest
from datetime import date

from scripts.audit_opportunities import has_stale_title_year


class StaleTitleYearTests(unittest.TestCase):
    def test_old_named_cycle_is_stale(self):
        self.assertTrue(
            has_stale_title_year("Data Journalism Grants 2023", date(2026, 9, 11))
        )

    def test_cycle_containing_current_year_is_not_stale(self):
        self.assertFalse(
            has_stale_title_year("TEV Bursu 2025-2026", date(2026, 9, 11))
        )

    def test_rolling_program_without_year_is_not_guessed(self):
        self.assertFalse(
            has_stale_title_year("Sürekli Açık Gönüllülük", date(2026, 9, 11))
        )


if __name__ == "__main__":
    unittest.main()
