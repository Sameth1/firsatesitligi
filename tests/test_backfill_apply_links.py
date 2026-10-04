import unittest

import backfill_apply_links as backfill
from application_links import ApplicationRoute


def route(verified, status):
    return ApplicationRoute(None, "https://example.org", "portal", verified, status,
                            "https://example.org", None, "r", details_status_code=status)


class TransientFailureTests(unittest.TestCase):
    def test_unreachable_page_is_left_untouched(self):
        # Zaman aşımı, güvenlik duvarı ve sunucu hatası "başvuru linki yok"
        # kanıtı değil.
        for status in (None, 403, 429, 503):
            with self.subTest(status=status):
                self.assertTrue(backfill.transient_failure(route(False, status)))

    def test_definitive_results_are_applied(self):
        self.assertFalse(backfill.transient_failure(route(False, 200)))
        self.assertFalse(backfill.transient_failure(route(False, 404)))
        self.assertFalse(backfill.transient_failure(route(True, None)))


class RestoreMissingTests(unittest.TestCase):
    DAAD = "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=10000220"

    def test_wrongly_hidden_official_page_is_restorable(self):
        row = {"application_route_status": "missing", "review_flag": "application_link_missing",
               "details_url": self.DAAD}
        self.assertTrue(backfill.restorable_missing(row))

    def test_other_states_are_not_touched(self):
        for row in (
            {"application_route_status": "guided", "review_flag": "application_link_missing",
             "details_url": self.DAAD},
            {"application_route_status": "missing", "review_flag": None, "details_url": self.DAAD},
            {"application_route_status": "missing", "review_flag": "application_link_missing",
             "details_url": "https://www.nasilgitmis.com/blog/x"},
        ):
            with self.subTest(row=row):
                self.assertFalse(backfill.restorable_missing(row))
