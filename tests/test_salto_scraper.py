import unittest
from unittest.mock import patch

import salto_scraper as salto


def page(venue="Brussels, Belgium - FL", activity="Training Course",
         participants_from=('Erasmus+ Youth Programme countries <img class="info-tooltip-icon" '
                            'title="Austria, Belgium - FL, Germany, Türkiye"/>'),
         deadline="29 November 2099", fee="There is no participation fee.",
         lodging="The hosting NA will organise the accommodation and covers the costs.",
         travel="Please contact your NA."):
    return f"""
    <html><body>
    <div class="tool-item-data training-data main-col">
      <h1>Co-create space with and for youth </h1>
      <div class="tool-item-category-container"><p>{activity}</p>
        <p>14-18 December 2099 | {venue}</p></div>
      <div class="training-summary">How do we design spaces for young people?</div>
      <div class="training-description"><p>A training for youth workers.</p></div>
    </div>
    <a href="https://www.salto-youth.net/tools/european-training-calendar/application-procedure/1/">
      <span>Apply now!</span>
      <span>Application deadline <span>(24h UTC)</span>: {deadline}</span></a>
    <div>
      <p class="microcopy microcopy-light">This Training Course is</p>
      <p><span>for</span> 25 participants</p>
      <p class="mrgn-btm-22"><span>from</span> {participants_from}</p>
      <p class="microcopy microcopy-light">and recommended for</p>
      <p>Youth workers</p>
      <p class="microcopy microcopy-light">Working language(s):</p>
      <p>English</p>
    </div>
    <div><h3>Costs</h3>
      <h4>Participation fee</h4><div><p>{fee}</p></div>
      <h4>Accommodation and food</h4><div><p>{lodging}</p></div>
      <h4>Travel reimbursement</h4><div><p>{travel}</p></div>
    </div>
    </body></html>"""


URL = "https://www.salto-youth.net/tools/european-training-calendar/training/co-create.15244/"


class FakeRoute:
    def submission_fields(self):
        return {"url": URL, "details_url": URL, "application_route_status": "unverified",
                "application_method": None, "application_url_check_status": None,
                "application_url_final": None, "application_url_evidence": None}


class FakeVerifiedRoute:
    FORM = "https://docs.google.com/forms/d/e/abc/viewform"

    def submission_fields(self):
        return {"url": self.FORM, "details_url": URL, "application_route_status": "verified",
                "application_method": "online_form", "application_url_check_status": 200,
                "application_url_final": self.FORM, "application_url_evidence": "Apply"}


class VerifiedRouteTests(unittest.TestCase):
    @patch("salto_scraper.resolve_application_route", return_value=FakeVerifiedRoute())
    def test_verified_route_carries_its_verification_time(self, _route):
        # DB kısıtı: verified rota doğrulama zamanı olmadan eklenemez.
        record, _ = salto.parse_training(page(), URL)
        self.assertEqual(record["application_route_status"], "verified")
        self.assertTrue(record["application_url_verified_at"])
        self.assertEqual(record["url"], FakeVerifiedRoute.FORM)
        self.assertEqual(record["details_url"], URL)

    @patch("salto_scraper.resolve_application_route", return_value=FakeRoute())
    def test_unverified_route_has_no_verification_time(self, _route):
        record, _ = salto.parse_training(page(), URL)
        self.assertNotIn("application_url_verified_at", record)


@patch("salto_scraper.resolve_application_route", return_value=FakeRoute())
class ParseTrainingTests(unittest.TestCase):
    def test_complete_training_becomes_a_submission(self, _route):
        record, reason = salto.parse_training(page(), URL)
        self.assertEqual(reason, "")
        self.assertEqual(record["host_countries"], ["BE"])
        self.assertEqual(record["deadline_text"], "2099-11-29")
        self.assertEqual(record["category_slug"], "youth_project")
        self.assertEqual(record["funding_type"], "partial")
        self.assertIn("Erasmus+ Youth Programme countries", record["eligibility_notes"])
        self.assertIn("Working language(s): English", record["eligibility_notes"])
        self.assertEqual(record["submission_origin"], "agent")
        # Kullanıcı filtreleri tahmin edilmez; ajan sayfadan kanıtla belirler.
        for key in ("age_min", "age_max", "study_level", "language_requirement"):
            self.assertIsNone(record[key])

    def test_online_activity_is_out_of_scope(self, _route):
        for kwargs in ({"venue": "Online"}, {"activity": "Online Training Course"}):
            with self.subTest(**kwargs):
                record, reason = salto.parse_training(page(**kwargs), URL)
                self.assertIsNone(record)
                self.assertIn("çevrim içi", reason)

    def test_training_in_turkiye_is_not_abroad(self, _route):
        record, reason = salto.parse_training(page(venue="Ankara, Türkiye"), URL)
        self.assertIsNone(record)
        self.assertIn("yurt dışı değil", reason)

    def test_turkiye_must_be_among_participant_countries(self, _route):
        only_belgium = ('Belgium <img class="info-tooltip-icon" title="Belgium - FL, Belgium - FR"/>')
        record, reason = salto.parse_training(page(participants_from=only_belgium), URL)
        self.assertIsNone(record)
        self.assertIn("Türkiye yok", reason)

    def test_explicit_country_list_with_turkiye_is_accepted(self, _route):
        record, _ = salto.parse_training(
            page(participants_from="Germany, Poland, Türkiye"), URL)
        self.assertIsNotNone(record)

    def test_full_funding_only_when_every_cost_is_covered(self, _route):
        record, _ = salto.parse_training(
            page(travel="Travel costs will be reimbursed after the activity."), URL)
        self.assertEqual(record["funding_type"], "full")

    def test_unknown_venue_country_is_skipped_not_guessed(self, _route):
        record, reason = salto.parse_training(page(venue="Atlantis, Neverland"), URL)
        self.assertIsNone(record)
        self.assertIn("tanınmadı", reason)


class HelperTests(unittest.TestCase):
    def test_venue_country_handles_salto_names(self):
        cases = {
            "Brussels, Belgium - FL": "BE",
            "Skopje, Republic of North Macedonia": "MK",
            "Pristina, KOSOVO * UN RESOLUTION": "XK",
            "Bratislava, Slovak Republic": "SK",
            "Online": None,
        }
        for venue, code in cases.items():
            with self.subTest(venue=venue):
                self.assertEqual(salto.venue_country(venue), code)

    def test_deadline_parse(self):
        self.assertEqual(
            salto.parse_deadline("Apply now! Application deadline (24h UTC) : 1 October 2026"),
            "2026-10-01")
        self.assertIsNone(salto.parse_deadline("Application deadline: soon"))


if __name__ == "__main__":
    unittest.main()
