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

    def test_finished_activity_is_out_of_scope_even_without_deadline(self):
        # Portal "ESC Volunteering Team in Portugal – August 2026" ilanını Ekim'de
        # hâlâ open + son tarihsiz gösteriyordu.
        op = opportunity(has_no_deadline=True, date_application_end=None,
                         date_start="2026-08-10T12:00:00", date_end="2026-09-09T12:00:00",
                         date_flexibility="precise")
        self.assertIn("bitmiş", esc.scope_reason(op, TODAY))

    def test_started_fixed_date_activity_is_out_of_scope(self):
        op = opportunity(date_start="2025-10-01T12:00:00", date_end="2026-12-30T12:00:00",
                         date_flexibility="precise")
        self.assertIn("başlangıç", esc.scope_reason(op, TODAY))

    def test_started_flexible_placement_stays_in_scope(self):
        op = opportunity(date_start="2025-09-01T12:00:00", date_end="2027-08-31T12:00:00",
                         date_flexibility="flexible")
        self.assertEqual(esc.scope_reason(op, TODAY), "")


class SyncTests(unittest.TestCase):
    def test_sync_flags_closed_and_finished_listings_only(self):
        open_by_id = {
            "41835": opportunity(),
            "53041": opportunity(id=53041, has_no_deadline=True,
                                 date_end="2026-09-09T12:00:00"),
        }
        rows = [
            {"id": "a", "official_url": "https://youth.europa.eu/solidarity/placement/41835_en"},
            {"id": "b", "official_url": "https://youth.europa.eu/solidarity/placement/53041_en"},
            {"id": "c", "official_url": "https://youth.europa.eu/solidarity/placement/99999_en"},
            {"id": "d", "official_url": "https://example.org/other"},
        ]
        decisions = esc.sync_decisions(rows, open_by_id, TODAY,
                                       ("official_url", "details_url", "source_url"))
        self.assertEqual({row["id"]: reason for row, reason in decisions},
                         {"b": "faaliyet bitmiş", "c": "ilan portalda artık açık değil"})


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
