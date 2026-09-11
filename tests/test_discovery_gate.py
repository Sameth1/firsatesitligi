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
            "application_route_status": "unverified",
            "application_url_verified_at": None,
            "application_url_final": None,
            "category_slug": None,
            "host_countries": [],
            "deadline_text": None,
            "funding_type": None,
            "eligibility_notes": "short",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                record = complete_candidate()
                record[field] = value
                self.assertTrue(candidate_blockers(record, today=date(2026, 9, 11)))

    def test_expired_candidate_is_blocked(self):
        record = complete_candidate()
        record["deadline_text"] = "2025-01-01"
        self.assertIn(
            "son tarih geçmiş",
            candidate_blockers(record, today=date(2026, 9, 11)),
        )


if __name__ == "__main__":
    unittest.main()
