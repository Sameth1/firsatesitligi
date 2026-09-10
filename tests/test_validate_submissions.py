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


def revision_submission(**overrides):
    """Admin'in revize istediği bir insan gönderisi (105 akışı)."""
    sub = complete_submission()
    sub.update({
        "id": "rev-1",
        "submission_origin": "human",
        "review_stage": "agent_revision",
        "admin_note": "[insan] REVİZE İSTENDİ: Son başvuru tarihi doğru mu, kontrol et.",
    })
    sub.update(overrides)
    return sub


class RevisionQueueTests(unittest.TestCase):
    def test_admin_request_is_read_without_the_marker(self):
        self.assertEqual(
            validator.admin_revision_request(revision_submission()),
            "Son başvuru tarihi doğru mu, kontrol et.",
        )

    def test_only_agent_revision_stage_counts_as_revision(self):
        self.assertTrue(validator.is_revision(revision_submission()))
        self.assertFalse(validator.is_revision(complete_submission()))

    def test_empty_fields_lists_only_blank_ones(self):
        sub = revision_submission(funding_type=None, host_countries=[],
                                  language_requirement="   ")
        blanks = validator.empty_fields(sub)

        self.assertIn("funding_type", blanks)
        self.assertIn("host_countries", blanks)
        self.assertIn("language_requirement", blanks)
        self.assertNotIn("category_slug", blanks)      # zaten dolu

    @patch("validate_submissions.process_revision", return_value="revize")
    def test_revision_skips_the_approval_pipeline(self, process_revision):
        result = validator.process(revision_submission(), True, set(), set(),
                                   {"llm_calls": 0})

        self.assertEqual(result, "revize")
        process_revision.assert_called_once()


class RevisionSuggestionTests(unittest.TestCase):
    def test_filled_fields_are_never_overwritten(self):
        sub = revision_submission()          # kategori ve ülke dolu
        patch_data, labels = validator.sanitize_suggestions(sub, {
            "category_slug": "internship",
            "host_countries": ["FR"],
        })

        self.assertEqual(patch_data, {})
        self.assertEqual(labels, [])

    def test_empty_fields_are_filled_from_suggestions(self):
        sub = revision_submission(category_slug=None, funding_type=None,
                                  host_countries=[], study_level=[])
        patch_data, labels = validator.sanitize_suggestions(sub, {
            "category_slug": "internship",
            "funding_type": "stipend",
            "host_countries": ["de", "fr"],
            "study_level": ["master", "uydurma"],
        })

        self.assertEqual(patch_data["category_slug"], "internship")
        self.assertEqual(patch_data["funding_type"], "stipend")
        self.assertEqual(patch_data["host_countries"], ["DE", "FR"])
        self.assertEqual(patch_data["study_level"], ["master"])
        self.assertIn("kategori", labels)

    def test_invalid_values_are_dropped(self):
        sub = revision_submission(category_slug=None, funding_type=None,
                                  host_countries=[], eligibility_notes="")
        patch_data, _ = validator.sanitize_suggestions(sub, {
            "category_slug": "uydurma_kategori",
            "funding_type": "ücretli",
            "host_countries": ["Almanya"],
            "eligibility_notes": "kısa",       # 20 karakter eşiğinin altında
        })

        self.assertEqual(patch_data, {})

    def test_global_program_becomes_star(self):
        sub = revision_submission(host_countries=[])
        patch_data, _ = validator.sanitize_suggestions(sub, {"host_countries": ["worldwide"]})

        self.assertEqual(patch_data["host_countries"], ["*"])

    def test_unparseable_or_past_deadline_is_not_written(self):
        sub = revision_submission(deadline_text=None)
        for value in ("yakında", "1 Ocak 2020"):
            with self.subTest(value=value):
                patch_data, _ = validator.sanitize_suggestions(sub, {"deadline_text": value})
                self.assertNotIn("deadline_text", patch_data)

    def test_inconsistent_age_range_is_dropped_entirely(self):
        sub = revision_submission(age_min=None, age_max=None)
        patch_data, _ = validator.sanitize_suggestions(sub, {"age_min": 30, "age_max": 18})

        self.assertNotIn("age_min", patch_data)
        self.assertNotIn("age_max", patch_data)

    def test_unknown_verdict_falls_back_to_belirsiz(self):
        parsed = validator._parse_revision(json.dumps({
            "karar": "harika", "gerekce": "x", "alan_onerileri": "metin",
        }))

        self.assertEqual(parsed["karar"], "belirsiz")
        self.assertEqual(parsed["alan_onerileri"], {})


class RevisionWriteTests(unittest.TestCase):
    """Ajanın revize kaydına yazdıkları — status'a asla dokunulmaz."""

    @patch("validate_submissions.requests.patch")
    def test_result_returns_record_to_human_without_deciding(self, http_patch):
        validator.apply_revision_result(revision_submission(), "uygun",
                                        "Tarih sayfada doğrulandı.", {"funding_type": "full"},
                                        dry_run=False)

        payload = http_patch.call_args.kwargs["json"]
        self.assertEqual(payload["review_stage"], "human_review")
        self.assertEqual(payload["funding_type"], "full")
        self.assertNotIn("status", payload)
        self.assertTrue(payload["admin_note"].startswith(validator.AGENT_MARKER))
        self.assertIn("UYGUN GÖRÜNÜYOR", payload["admin_note"])

    @patch("validate_submissions.requests.patch")
    def test_heuristic_rejection_on_revision_does_not_reject_the_record(self, http_patch):
        validator.apply_decision(revision_submission(), "reddet",
                                 "Ölü bağlantı (HTTP 404)", dry_run=False)

        payload = http_patch.call_args.kwargs["json"]
        self.assertEqual(payload["review_stage"], "human_review")
        self.assertNotIn("status", payload)
        self.assertIn("SORUNLU", payload["admin_note"])

    @patch("validate_submissions.approve_submission")
    @patch("validate_submissions.apply_revision_result")
    @patch("validate_submissions.review_revision_with_llm")
    @patch("validate_submissions.fetch_target_and_source")
    def test_positive_review_still_leaves_approval_to_the_human(
        self, fetch_pages, review, apply_result, approve
    ):
        fetch_pages.return_value = (200, None, None, "sayfa metni " * 30, "")
        review.return_value = {
            "karar": "uygun",
            "cevap": "Son başvuru tarihi sayfada 15 Eylül 2026 olarak yazıyor.",
            "gerekce": "Sayfada açık başvuru dönemi var.",
            "alan_onerileri": {},
        }

        result = validator.process_revision(revision_submission(), True, set(),
                                            {"llm_calls": 0})

        self.assertEqual(result, "revize")
        approve.assert_not_called()
        self.assertEqual(apply_result.call_args.args[1], "uygun")


if __name__ == "__main__":
    unittest.main()
