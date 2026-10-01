import unittest
from datetime import date

from discovery_gate import candidate_blockers


def complete_candidate():
    return {
        "title": "Verified scholarship 2027",
        "url": "https://apply.example.org/form",
        "application_route_status": "verified",
        "application_url_verified_at": "2026-09-11T10:00:00Z",
        "application_url_final": "https://apply.example.org/form",
        "category_slug": "scholarship",
        "host_countries": ["DE"],
        "deadline_text": "2027-01-10",
        "funding_type": "full",
        "eligibility_notes": "Bachelor students from all countries may apply.",
    }


class DiscoveryGateTests(unittest.TestCase):
    def test_complete_candidate_enters_agent_queue(self):
        self.assertEqual(
            candidate_blockers(complete_candidate(), today=date(2026, 9, 11)), [])

    def test_every_required_field_fails_closed(self):
        cases = {
            "title": "",
            "url": "not-a-url",
            "category_slug": None,
            "host_countries": [],
            "funding_type": None,
            "eligibility_notes": "short",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                record = complete_candidate()
                record[field] = value
                self.assertTrue(candidate_blockers(record, today=date(2026, 9, 11)))

    def test_deadline_and_route_are_left_to_the_agent(self):
        # Serbest metin ya da boş son tarih ve doğrulanmamış başvuru rotası
        # kaydı kuyruktan ATMAZ: ajan ikisini de sayfadan kanıtla belirliyor.
        for patch in (
            {"deadline_text": None},
            {"deadline_text": "Application deadline: 31 October 2026"},
            {"deadline_text": "Applications are accepted on a rolling basis"},
            {"application_route_status": "unverified",
             "application_url_verified_at": None,
             "application_url_final": None},
        ):
            with self.subTest(patch=patch):
                record = {**complete_candidate(), **patch}
                self.assertEqual(
                    candidate_blockers(record, today=date(2026, 9, 11)), [])

    def test_details_url_is_enough_when_url_is_missing(self):
        record = complete_candidate()
        record["url"] = None
        record["details_url"] = "https://www2.daad.de/detail?id=1"
        self.assertEqual(candidate_blockers(record, today=date(2026, 9, 11)), [])

    def test_expired_candidate_is_blocked(self):
        record = complete_candidate()
        record["deadline_text"] = "2025-01-01"
        self.assertIn(
            "son tarih geçmiş",
            candidate_blockers(record, today=date(2026, 9, 11)),
        )


if __name__ == "__main__":
    unittest.main()
