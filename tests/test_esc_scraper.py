import unittest
from datetime import date

import esc_scraper as esc

TODAY = date(2026, 10, 3)


def opportunity(**overrides):
    op = {
        "id": 41835, "status": "open", "strand": ["volunteering"],
        "title": "Your time, your impact: Special School",
        "country": "PL", "town": "Kwidzyn",
        "volunteer_countries": ["DE", "TR", "UA"],
        "has_no_deadline": False, "date_application_end": "2026-11-15T12:00:00",
        "participant_profile": "<p>Open to young people <b>18-30</b> who speak English.</p>",
        "description": "<p>Support teachers.</p>",
        "boarding_arrangements": "Accommodation, food and pocket money are covered.",
        "organisation_name": "Akwedukt",
    }
    op.update(overrides)
    return op


class ScopeTests(unittest.TestCase):
    def test_open_abroad_placement_for_turkiye_is_in_scope(self):
        self.assertEqual(esc.scope_reason(opportunity(), TODAY), "")
        self.assertEqual(esc.scope_reason(opportunity(volunteer_countries=["all"]), TODAY), "")
        self.assertEqual(esc.scope_reason(opportunity(strand=["humanitarian"]), TODAY), "")

    def test_out_of_scope_reasons(self):
        cases = {
            "açık değil": {"status": "full"},
            "Türkiye'den gönüllü kabul etmiyor": {"volunteer_countries": ["DE", "FR"]},
            "yurt dışı değil": {"country": "TR"},
            "geçmiş": {"date_application_end": "2026-09-01T12:00:00"},
            "gönüllülük dışı": {"strand": ["occupational"]},
            "çevrim içi": {"title": "Online training course for volunteers"},
        }
        for expected, patch in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, esc.scope_reason(opportunity(**patch), TODAY))

    def test_no_deadline_placement_is_in_scope(self):
        op = opportunity(has_no_deadline=True, date_application_end=None)
        self.assertEqual(esc.scope_reason(op, TODAY), "")


class RecordTests(unittest.TestCase):
    def test_record_points_to_the_official_placement_page(self):
        record = esc.build_record(opportunity())
        url = "https://youth.europa.eu/solidarity/placement/41835_en"
        self.assertEqual((record["url"], record["details_url"], record["source_url"]),
                         (url, url, url))
        self.assertEqual(record["category_slug"], "volunteering")
        self.assertEqual(record["deadline_text"], "2026-11-15")
        self.assertEqual(record["host_countries"], ["PL"])
        self.assertEqual(record["eligibility_notes"],
                         "Open to young people 18-30 who speak English.")
        for key in ("age_min", "age_max", "study_level", "language_requirement"):
            self.assertIsNone(record[key])

    def test_rolling_placement_has_empty_deadline(self):
        record = esc.build_record(opportunity(has_no_deadline=True))
        self.assertIsNone(record["deadline_text"])

    def test_eu_country_codes_become_iso(self):
        self.assertEqual(esc.build_record(opportunity(country="EL"))["host_countries"], ["GR"])


if __name__ == "__main__":
    unittest.main()
