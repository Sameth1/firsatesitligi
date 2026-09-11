import json
import unittest
from datetime import datetime, timezone
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
        "details_url": "https://example.org/program",
        "application_route_status": "verified",
        "application_method": "portal",
        "application_url_verified_at": datetime.now(timezone.utc).isoformat(),
        "application_url_final": "https://example.org/program/apply",
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


def verdict_with_quotes(page_text):
    verdict = high_confidence_verdict()
    verdict["kanitlar"] = {
        "guncellik": "Applications are open until 31 December 2099",
        "son_tarih": "31 December 2099",
        "kategori": "Scholarship programme",
        "finansman": "Fully funded",
        "ulke": "Hosted in Germany",
        "uygunluk": "Bachelor students may apply",
        "uyruk": "",
        "bolum": "",
    }
    return verdict


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


class RejectionMemoryTests(unittest.TestCase):
    def test_meaningful_legacy_notes_are_normalized(self):
        self.assertEqual(
            validator.normalize_legacy_human_rejection("  TR   YOK ")[0],
            "not_eligible",
        )
        self.assertEqual(
            validator.normalize_legacy_human_rejection("geçmiş tarihi")[0],
            "expired",
        )

    def test_ambiguous_legacy_notes_are_ignored(self):
        self.assertIsNone(validator.normalize_legacy_human_rejection("yok"))
        self.assertIsNone(validator.normalize_legacy_human_rejection("am"))

    def test_memory_weight_thresholds(self):
        self.assertEqual(validator._memory_weight(1), "example")
        self.assertEqual(validator._memory_weight(3), "warning")
        self.assertEqual(validator._memory_weight(5), "strong")


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

    def test_tracking_and_www_variants_are_duplicate(self):
        first = "https://www.example.org/program/?utm_source=newsletter&ref=home"
        second = "http://example.org/program"

        self.assertEqual(validator._norm_url(first), validator._norm_url(second))

    def test_generic_homepage_is_not_direct_link(self):
        submission = complete_submission()
        submission["url"] = "https://example.org/"

        self.assertTrue(validator.direct_link_blockers(submission))

    def test_evidence_quotes_must_exist_in_page(self):
        page = (
            "Applications are open until 31 December 2099. Scholarship programme. "
            "Fully funded. Hosted in Germany. Bachelor students may apply."
        )
        verdict = verdict_with_quotes(page)

        self.assertEqual(validator.evidence_quote_blockers(page, verdict), [])
        verdict["kanitlar"]["finansman"] = "Monthly stipend of 5000 euros"
        self.assertTrue(validator.evidence_quote_blockers(page, verdict))

    def test_missing_quote_object_fails_closed(self):
        blockers = validator.evidence_quote_blockers(
            "Some page text", high_confidence_verdict()
        )

        self.assertEqual(len(blockers), len(validator.EVIDENCE_QUOTE_FIELDS))


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

    @patch("validate_submissions.judge_with_llm", return_value=None)
    @patch("validate_submissions.fetch_page")
    @patch("validate_submissions.apply_decision")
    def test_llm_outage_stays_in_agent_retry_queue(
        self, apply_decision, fetch_page, _judge_with_llm
    ):
        fetch_page.return_value = (
            200,
            "https://example.org/program/apply",
            "<html><body>" + ("Current scholarship details. " * 10) + "</body></html>",
            None,
        )
        submission = complete_submission()
        submission.update({"id": "test", "source_url": submission["url"]})

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "tekrar")
        self.assertEqual(apply_decision.call_args.args[1], "tekrar")


class AgentRevisionTests(unittest.TestCase):
    @patch("validate_submissions.requests.get")
    def test_fetch_pending_routes_only_valid_agent_and_revision_rows(self, get):
        get.return_value.json.return_value = [
            {"id": "agent", "submission_origin": "agent", "review_stage": "agent_queue", "admin_note": None},
            {"id": "revision", "submission_origin": "human", "review_stage": "agent_revision", "admin_note": "[insan] REVİZE İSTENDİ: tarih"},
            {"id": "human", "submission_origin": "human", "review_stage": "human_review", "admin_note": None},
            {"id": "wrong", "submission_origin": "agent", "review_stage": "agent_revision", "admin_note": None},
        ]

        rows = validator.fetch_pending()

        self.assertEqual([row["id"] for row in rows], ["agent", "revision"])
        self.assertEqual(
            get.call_args.kwargs["params"]["review_stage"],
            "in.(agent_queue,agent_revision)",
        )

    def test_revision_fills_only_blank_fields_with_exact_evidence(self):
        submission = complete_submission()
        submission.update({
            "title": "Mevcut başlık değişmemeli",
            "language_requirement": None,
            "funding_notes": None,
        })
        page = "Applications require English B2. A monthly allowance is provided."
        result = {
            "fields": {
                "title": "Agent başlığı",
                "language_requirement": "İngilizce B2",
                "funding_notes": "Aylık harçlık sağlanır.",
            },
            "evidence": {
                "title": "A monthly allowance is provided",
                "language_requirement": "Applications require English B2",
                "funding_notes": "A monthly allowance is provided",
            },
        }

        result_patch = validator.build_agent_revision_patch(submission, result, page)

        self.assertNotIn("title", result_patch)
        self.assertEqual(result_patch["language_requirement"], "İngilizce B2")
        self.assertEqual(result_patch["funding_notes"], "Aylık harçlık sağlanır.")

    def test_revision_rejects_invalid_or_expired_suggestions(self):
        submission = complete_submission()
        submission.update({
            "category_slug": None,
            "deadline_text": None,
            "funding_type": None,
            "age_min": None,
            "age_max": None,
        })
        page = "Old deadline 2000-01-01. Category unknown. Ages 70 to 20."
        result = {
            "fields": {
                "category_slug": "anything",
                "deadline_text": "2000-01-01",
                "funding_type": "paid",
                "age_min": 70,
                "age_max": 20,
            },
            "evidence": {
                "category_slug": "Category unknown",
                "deadline_text": "Old deadline 2000-01-01",
                "funding_type": "Category unknown",
                "age_min": "Ages 70 to 20",
                "age_max": "Ages 70 to 20",
            },
        }

        result_patch = validator.build_agent_revision_patch(submission, result, page)

        self.assertEqual(result_patch, {})

    def test_revision_treats_whitespace_as_blank_and_rejects_decimal_age(self):
        submission = complete_submission()
        submission.update({"language_requirement": "   ", "age_min": None})
        page = "English B2 is required. Applicants must be at least 20 years old."
        result = {
            "fields": {"language_requirement": "English B2", "age_min": 20.5},
            "evidence": {
                "language_requirement": "English B2 is required",
                "age_min": "Applicants must be at least 20 years old",
            },
        }

        result_patch = validator.build_agent_revision_patch(submission, result, page)

        self.assertEqual(result_patch, {"language_requirement": "English B2"})

    @patch("validate_submissions.requests.patch")
    def test_finished_revision_returns_to_human_without_status_decision(self, patch):
        submission = {
            "id": "test",
            "admin_note": "[insan] REVİZE İSTENDİ: Son tarihi tamamla",
        }
        patch.return_value.raise_for_status.return_value = None

        payload = validator.finish_agent_revision(
            submission, {"deadline_text": "2099-12-31"}, "Tarih doğrulandı.", False,
        )

        self.assertNotIn("status", payload)
        self.assertEqual(payload["review_stage"], "human_review")
        self.assertIn("Son tarihi tamamla", payload["admin_note"])
        self.assertIn("deadline_text", payload["admin_note"])
        self.assertEqual(
            patch.call_args.kwargs["params"]["review_stage"], "eq.agent_revision"
        )

    @patch("validate_submissions.finish_agent_revision")
    @patch("validate_submissions.suggest_revision_with_llm", return_value=None)
    @patch("validate_submissions.fetch_page")
    def test_revision_llm_outage_stays_in_revision_queue(
        self, fetch_page, _suggest, finish
    ):
        fetch_page.return_value = (
            200,
            "https://example.org/program",
            "<html><body>" + ("Current scholarship details. " * 10) + "</body></html>",
            None,
        )
        submission = complete_submission()
        submission.update({
            "id": "test",
            "review_stage": "agent_revision",
            "source_url": submission["url"],
            "admin_note": "[insan] REVİZE İSTENDİ: Eksikleri tamamla",
        })

        outcome = validator.process_agent_revision(
            submission, True, {"llm_calls": 0}
        )

        self.assertEqual(outcome, "revision_retry")
        finish.assert_not_called()


class AgentEvaluationTests(unittest.TestCase):
    def test_snapshot_is_blind_to_old_decisions(self):
        submission = complete_submission()
        submission.update({
            "status": "rejected",
            "admin_note": "eski karar",
            "_agent_eval_decision": {"eylem": "reddet", "gerekce": "x"},
        })

        snapshot = validator._evaluation_snapshot(submission)

        self.assertNotIn("status", snapshot)
        self.assertNotIn("admin_note", snapshot)
        self.assertNotIn("_agent_eval_decision", snapshot)

    def test_agent_actions_map_to_eval_labels(self):
        self.assertEqual(validator._evaluation_decision("onayla"), "approve")
        self.assertEqual(validator._evaluation_decision("reddet"), "reject")
        self.assertEqual(validator._evaluation_decision("belirsiz"), "uncertain")
        self.assertEqual(validator._evaluation_decision("tekrar"), "retry")

    def test_dry_run_decision_is_captured_without_database_write(self):
        submission = {"id": "test"}

        note = validator.apply_decision(submission, "reddet", "Eksik tarih", True)

        self.assertIn("RED", note)
        self.assertEqual(
            submission["_agent_eval_decision"],
            {"eylem": "reddet", "gerekce": "Eksik tarih"},
        )


class CitizenshipTests(unittest.TestCase):
    """106/107: uyruk şartı — yanlış daraltmak hiç daraltmamaktan zararlı."""

    def test_valid_codes_are_kept_uppercased_and_deduped(self):
        self.assertEqual(validator.clean_citizenships(['cn', 'CN', 'ps']), ['CN', 'PS'])

    def test_no_restriction_markers_mean_none(self):
        for value in (None, ['all'], ['worldwide'], ['ANY'], []):
            with self.subTest(value=value):
                self.assertIsNone(validator.clean_citizenships(value))

    def test_country_names_are_not_accepted_as_codes(self):
        self.assertIsNone(validator.clean_citizenships(['China', 'Türkiye']))

    def test_unknown_two_letter_code_is_not_accepted(self):
        self.assertIsNone(validator.clean_citizenships(['ZZ']))

    def test_restriction_requires_a_verbatim_quote(self):
        page = "Only citizens of China may apply. Scholarship programme."
        verdict = verdict_with_quotes(page)
        verdict['uyruk_kisiti'] = ['CN']

        self.assertIn(
            "uyruk kısıtı alıntısı eksik",
            validator.evidence_quote_blockers(page, verdict),
        )
        verdict['kanitlar']['uyruk'] = "Only citizens of China may apply"
        self.assertNotIn(
            "uyruk kısıtı alıntısı eksik",
            validator.evidence_quote_blockers(page, verdict),
        )

    def test_verdict_carries_citizenship_restriction(self):
        verdict = high_confidence_verdict()
        verdict['uyruk_kisiti'] = ['CN']
        self.assertEqual(validator._parse_verdict(json.dumps(verdict))['uyruk_kisiti'], ['CN'])

    def test_verdict_without_the_field_is_unrestricted(self):
        self.assertIsNone(
            validator._parse_verdict(json.dumps(high_confidence_verdict()))['uyruk_kisiti'])

    @patch('validate_submissions.requests.post')
    @patch('validate_submissions.requests.patch')
    def test_restriction_is_written_before_the_approval_rpc(self, http_patch, http_post):
        http_post.return_value.status_code = 200
        http_post.return_value.json.return_value = {'opportunity_id': 'opp-1'}
        verdict = high_confidence_verdict()
        verdict['uyruk_kisiti'] = ['CN']

        ok, _ = validator.approve_submission({'id': 'sub-1'}, verdict, dry_run=False)

        self.assertTrue(ok)
        self.assertEqual(http_patch.call_args.kwargs['json'],
                         {'eligible_citizenships': ['CN']})
        http_post.assert_called_once()

    @patch('validate_submissions.requests.post')
    @patch('validate_submissions.requests.patch')
    def test_approval_is_abandoned_if_the_restriction_cannot_be_written(self, http_patch, http_post):
        # Uyruk yazılamadıysa kayıt {all} ile yayına girmemeli.
        http_patch.side_effect = validator.requests.exceptions.RequestException('boom')
        verdict = high_confidence_verdict()
        verdict['uyruk_kisiti'] = ['PS']

        ok, detay = validator.approve_submission({'id': 'sub-1'}, verdict, dry_run=False)

        self.assertFalse(ok)
        self.assertIn('yazılamadı', detay)
        http_post.assert_not_called()

    @patch('validate_submissions.requests.post')
    @patch('validate_submissions.requests.patch')
    def test_unrestricted_record_is_approved_without_extra_write(self, http_patch, http_post):
        http_post.return_value.status_code = 200
        http_post.return_value.json.return_value = {'opportunity_id': 'opp-1'}

        ok, _ = validator.approve_submission({'id': 'sub-1'}, high_confidence_verdict(),
                                             dry_run=False)

        self.assertTrue(ok)
        http_patch.assert_not_called()

    def test_field_restriction_is_written_too(self):
        with patch('validate_submissions.requests.post') as http_post, \
             patch('validate_submissions.requests.patch') as http_patch:
            http_post.return_value.status_code = 200
            http_post.return_value.json.return_value = {'opportunity_id': 'opp-1'}
            verdict = high_confidence_verdict()
            verdict['uyruk_kisiti'] = ['CN']
            verdict['bolum_kisiti'] = ['medicine', 'nursing']

            validator.approve_submission({'id': 'sub-1'}, verdict, dry_run=False)

            self.assertEqual(http_patch.call_args.kwargs['json'], {
                'eligible_citizenships': ['CN'],
                'target_fields': ['medicine', 'nursing'],
            })

    def test_unknown_field_slugs_are_dropped(self):
        # UI'da olmayan bir slug yazmak kaydı o bölümü seçenden gizlerdi.
        self.assertEqual(validator.clean_fields(['medicine', 'uydurma_bolum']), ['medicine'])
        self.assertIsNone(validator.clean_fields(['all']))
        self.assertIsNone(validator.clean_fields(['hepsi', 'xyz']))

    def test_revision_fills_filters_only_when_empty(self):
        """Revize akışı boş uyruk/bölümü doldurabilir, doluyu ASLA ezmez."""
        sayfa = "Only citizens of China may apply. Open to medicine students."
        sonuc = {
            "fields": {"eligible_citizenships": ["cn"], "target_fields": ["medicine"]},
            "evidence": {
                "eligible_citizenships": "Only citizens of China may apply.",
                "target_fields": "Open to medicine students.",
            },
        }

        bos = {"eligible_citizenships": [], "target_fields": []}
        patch = validator.build_agent_revision_patch(bos, sonuc, sayfa)
        self.assertEqual(patch["eligible_citizenships"], ["CN"])
        self.assertEqual(patch["target_fields"], ["medicine"])

        dolu = {"eligible_citizenships": ["TR"], "target_fields": ["law"]}
        patch = validator.build_agent_revision_patch(dolu, sonuc, sayfa)
        self.assertNotIn("eligible_citizenships", patch)
        self.assertNotIn("target_fields", patch)

    def test_revision_drops_filter_values_without_page_evidence(self):
        # Kanıt alıntısı sayfada geçmiyorsa öneri düşer — uydurulmuş bir uyruk
        # kısıtı, uygun bir adayı sonuçlardan silerdi.
        patch = validator.build_agent_revision_patch(
            {"eligible_citizenships": []},
            {"fields": {"eligible_citizenships": ["CN"]},
             "evidence": {"eligible_citizenships": "sayfada olmayan cumle"}},
            "Bu sayfada uyruk sarti yok.",
        )
        self.assertEqual(patch, {})


if __name__ == "__main__":
    unittest.main()
