import json
import unittest
from unittest.mock import patch

import validate_submissions as validator


def complete_submission():
    return {
        "title": "Eksiksiz örnek burs programı",
        "url": "https://example.org/program/apply",
        "category_slug": "scholarship",
        "host_countries": ["DE"],
        "deadline_text": "2099-12-31",
        "funding_type": "full",
        "eligibility_notes": "Lisans öğrencileri programa başvurabilir.",
        "study_level": ["undergraduate"],
    }


def high_confidence_verdict():
    return {
        "durum": "acik",
        "kategori_uygun": True,
        "guven": "yuksek",
        "tek_firsat": True,
        "dogrudan_firsat_sayfasi": True,
        "son_tarih_dogrulandi": True,
        "finansman_dogrulandi": True,
        "ulke_dogrulandi": True,
        "uygunluk_dogrulandi": True,
        "gerekce": "Bütün alanlar sayfada doğrulandı.",
    }


class VerdictParsingTests(unittest.TestCase):
    def test_string_true_does_not_pass_boolean_gate(self):
        verdict = high_confidence_verdict()
        verdict["finansman_dogrulandi"] = "true"

        parsed = validator._parse_verdict(json.dumps(verdict))

        self.assertIs(parsed["finansman_dogrulandi"], False)

    def test_missing_evidence_flags_default_to_false(self):
        parsed = validator._parse_verdict(json.dumps({
            "durum": "acik",
            "kategori_uygun": True,
            "guven": "yuksek",
            "gerekce": "Eksik model çıktısı",
        }))

        self.assertIs(parsed["tek_firsat"], False)
        self.assertIs(parsed["son_tarih_dogrulandi"], False)


class ApprovalGateTests(unittest.TestCase):
    def test_complete_record_and_all_evidence_can_pass(self):
        self.assertEqual(
            validator.auto_approval_blockers(
                complete_submission(), high_confidence_verdict()
            ),
            [],
        )

    def test_every_required_submission_field_blocks_approval(self):
        cases = {
            "title": "",
            "url": "",
            "category_slug": None,
            "host_countries": [],
            "deadline_text": None,
            "funding_type": None,
            "eligibility_notes": "",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                submission = complete_submission()
                submission[field] = value
                self.assertTrue(
                    validator.auto_approval_blockers(
                        submission, high_confidence_verdict()
                    )
                )

    def test_medium_confidence_blocks_approval(self):
        verdict = high_confidence_verdict()
        verdict["guven"] = "orta"

        blockers = validator.auto_approval_blockers(complete_submission(), verdict)

        self.assertIn("LLM güveni yüksek değil", blockers)
        self.assertEqual(validator.decide(verdict)[0], "belirsiz")

    def test_each_missing_evidence_flag_blocks_approval(self):
        fields = (
            "tek_firsat", "dogrudan_firsat_sayfasi",
            "son_tarih_dogrulandi", "finansman_dogrulandi",
            "ulke_dogrulandi", "uygunluk_dogrulandi",
        )
        for field in fields:
            with self.subTest(field=field):
                verdict = high_confidence_verdict()
                verdict[field] = False
                self.assertTrue(
                    validator.auto_approval_blockers(complete_submission(), verdict)
                )

    def test_missing_reason_blocks_approval(self):
        verdict = high_confidence_verdict()
        verdict["gerekce"] = "(gerekçe yok)"

        blockers = validator.auto_approval_blockers(complete_submission(), verdict)

        self.assertIn("kanıta dayalı gerekçe eksik", blockers)

    def test_failed_evidence_becomes_rejection_reason(self):
        verdict = high_confidence_verdict()
        verdict["dogrudan_firsat_sayfasi"] = False

        reasons = validator.evidence_rejection_reasons(verdict)

        self.assertIn("link doğrudan başvuru/resmî fırsat sayfası değil", reasons)

    def test_aggregator_url_is_not_a_direct_link(self):
        submission = complete_submission()
        submission["url"] = "https://www.youthop.com/example-post"
        submission["source_url"] = submission["url"]

        self.assertTrue(validator.direct_link_blockers(submission))

    def test_external_apply_url_with_separate_source_can_continue(self):
        submission = complete_submission()
        submission["source_url"] = "https://www.youthop.com/example-post"

        self.assertEqual(validator.direct_link_blockers(submission), [])


class HistoricApprovalClassificationTests(unittest.TestCase):
    def test_active_expired_record_should_close(self):
        opportunity = {
            "is_active": True,
            "deadline": "2020-01-01",
            "deadline_notes": None,
            "last_verified_at": None,
        }
        classification, _ = validator.classify_historic_approval(
            complete_submission(), opportunity
        )
        self.assertEqual(classification, "kapatilmali")

    def test_incomplete_active_record_needs_admin(self):
        submission = complete_submission()
        submission["funding_type"] = None
        opportunity = {
            "is_active": True,
            "deadline": "2099-12-31",
            "deadline_notes": None,
            "last_verified_at": "2099-01-01T00:00:00Z",
        }
        classification, reasons = validator.classify_historic_approval(
            submission, opportunity
        )
        self.assertEqual(classification, "admin_kontrolu")
        self.assertTrue(reasons)


class DecisionFlowTests(unittest.TestCase):
    @patch("validate_submissions.apply_decision")
    def test_incomplete_record_is_rejected_not_queued(self, apply_decision):
        submission = complete_submission()
        submission.update({"id": "test", "deadline_text": None})

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "llm_red")
        self.assertEqual(apply_decision.call_args.args[1], "reddet")

    @patch("validate_submissions.apply_decision")
    def test_aggregator_source_link_is_rejected_not_queued(self, apply_decision):
        submission = complete_submission()
        submission.update({
            "id": "test",
            "url": "https://www.nasilgitmis.com/firsat-yazisi",
            "source_url": "https://www.nasilgitmis.com/firsat-yazisi",
        })

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "llm_red")
        self.assertEqual(apply_decision.call_args.args[1], "reddet")


if __name__ == "__main__":
    unittest.main()
