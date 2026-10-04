import json
import unittest
from datetime import date, datetime, timezone
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
        "study_level": ["bachelor"],
        "eligible_citizenships": ["all"],
        "target_fields": ["all"],
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
        "resmi_kaynak": True,
        "son_tarih_dogrulandi": True,
        "surekli_basvuru": False,
        "finansman_dogrulandi": True,
        "ulke_dogrulandi": True,
        "uygunluk_dogrulandi": True,
        "uyruk_dogrulandi": True,
        "yas_dogrulandi": True,
        "egitim_dogrulandi": True,
        "dil_dogrulandi": True,
        "bolum_dogrulandi": True,
        "dogrulanmis_filtreler": {
            "host_countries": ["DE"],
            "eligible_citizenships": ["all"],
            "age_min": None,
            "age_max": None,
            "study_level": ["bachelor"],
            "language_requirement": None,
            "required_languages": ["all"],
            "target_fields": ["all"],
            "deadline": "2099-12-31",
        },
        "gerekce": "Bütün alanlar sayfada doğrulandı.",
    }


def expected_patch(verdict):
    """Onaydan önce submission'a yazılması beklenen alanlar."""
    filters = dict(verdict["dogrulanmis_filtreler"])
    deadline = filters.pop("deadline")
    return {**filters, "deadline_text": deadline}


def verdict_with_quotes(page_text):
    verdict = high_confidence_verdict()
    verdict["kanitlar"] = {
        "guncellik": "Applications are open until 31 December 2099",
        "son_tarih": "31 December 2099",
        "kategori": "Scholarship programme",
        "finansman": "Fully funded",
        "ulke": "Hosted in Germany",
        "uygunluk": "Bachelor students may apply",
        "uyruk": "All nationalities may apply",
        "yas": "No age limit applies",
        "egitim": "Bachelor students may apply",
        "dil": "No language requirement",
        "bolum": "Open to any field of study",
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

    def test_free_text_or_missing_scraper_deadline_does_not_block(self):
        # Son tarih scraper'dan değil, modelin kanıtladığı değerden gelir.
        for value in (None, "", "Application deadline: 31 October 2099"):
            with self.subTest(value=value):
                submission = complete_submission()
                submission["deadline_text"] = value
                self.assertEqual(
                    validator.auto_approval_blockers(
                        submission, high_confidence_verdict()), [])

    def test_past_iso_deadline_on_the_record_still_blocks(self):
        submission = complete_submission()
        submission["deadline_text"] = "2000-01-01"
        self.assertIn(
            "son başvuru tarihi geçmiş",
            validator.auto_approval_blockers(submission, high_confidence_verdict()),
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

    def test_verified_route_needs_a_direct_application_page(self):
        verdict = high_confidence_verdict()
        verdict["dogrudan_firsat_sayfasi"] = False

        self.assertIn(
            "doğrudan fırsat sayfası olduğu doğrulanmadı",
            validator.route_blockers(complete_submission(), verdict),
        )

    def test_guided_route_needs_an_official_page_not_a_direct_form(self):
        submission = complete_submission()
        submission.update({
            "application_route_status": "guided",
            "application_method": None,
            "application_url_verified_at": None,
            "application_url_final": None,
        })
        verdict = high_confidence_verdict()
        verdict["dogrudan_firsat_sayfasi"] = False
        self.assertEqual(validator.route_blockers(submission, verdict), [])

        verdict["resmi_kaynak"] = False
        self.assertIn(
            "bilgi sayfasının resmî kaynak olduğu doğrulanmadı",
            validator.route_blockers(submission, verdict),
        )

    def test_record_without_any_route_is_blocked(self):
        submission = complete_submission()
        submission["application_route_status"] = "unverified"
        self.assertTrue(
            validator.route_blockers(submission, high_confidence_verdict()))

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
            "Fully funded. Hosted in Germany. Bachelor students may apply. "
            "All nationalities may apply. No age limit applies. "
            "No language requirement. Open to any field of study."
        )
        verdict = verdict_with_quotes(page)

        self.assertEqual(validator.evidence_quote_blockers(page, verdict), [])
        verdict["kanitlar"]["finansman"] = "Monthly stipend of 5000 euros"
        self.assertTrue(validator.evidence_quote_blockers(page, verdict))

    def test_missing_quote_object_fails_closed(self):
        # Her zaman alıntı isteyen altı alan + kısıt yazılmış tek filtre
        # (study_level=["bachelor"]) raporlanır; kısıtsız filtreler raporlanmaz.
        blockers = validator.evidence_quote_blockers(
            "Some page text", high_confidence_verdict()
        )

        self.assertEqual(
            len(blockers), len(validator.ALWAYS_QUOTED_EVIDENCE) + 1, blockers)
        self.assertIn("eğitim kademesi filtresi alıntısı eksik", blockers)


class StrictFilterGateTests(unittest.TestCase):
    def test_each_filter_flag_is_required(self):
        for field in validator.STRICT_FILTER_FLAGS:
            with self.subTest(field=field):
                verdict = high_confidence_verdict()
                verdict[field] = False
                self.assertTrue(validator.strict_filter_blockers(verdict))

    def test_invalid_filter_values_fail_closed(self):
        verdict = high_confidence_verdict()
        verdict["dogrulanmis_filtreler"].update({
            "host_countries": ["ZZ"],
            "eligible_citizenships": ["all", "TR"],
            "study_level": ["any", "master"],
            "required_languages": ["xx"],
            "target_fields": ["uydurma_bolum"],
            "age_min": 40,
            "age_max": 20,
        })
        parsed = validator._parse_verdict(json.dumps(verdict))
        self.assertTrue(validator.strict_filter_blockers(parsed))

    def test_two_passes_must_agree_on_every_filter(self):
        first = high_confidence_verdict()
        second = high_confidence_verdict()
        self.assertEqual(validator.filter_consensus_blockers(first, second), [])
        second["dogrulanmis_filtreler"]["age_max"] = 29
        self.assertTrue(validator.filter_consensus_blockers(first, second))

    def test_language_codes_are_canonical(self):
        verdict = high_confidence_verdict()
        verdict["dogrulanmis_filtreler"]["required_languages"] = ["DE", "en", "en"]
        parsed = validator._parse_verdict(json.dumps(verdict))
        self.assertEqual(
            parsed["dogrulanmis_filtreler"]["required_languages"], ["de", "en"])


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
    def test_future_deadline_cannot_be_called_closed_without_closed_quote(self):
        submission = complete_submission()
        submission["deadline_text"] = "2026-09-12"
        verdict = verdict_with_quotes("")
        verdict.update({"durum": "kapali", "guven": "yuksek"})
        verdict["kanitlar"]["guncellik"] = "Deadline: 12 September 2026"

        blockers = validator.verdict_date_consistency_blockers(
            submission, verdict, today=date(2026, 9, 11)
        )

        self.assertTrue(blockers)

    def test_explicit_closed_quote_can_override_future_recorded_deadline(self):
        submission = complete_submission()
        submission["deadline_text"] = "2026-09-12"
        verdict = verdict_with_quotes("")
        verdict.update({"durum": "kapali", "guven": "yuksek"})
        verdict["kanitlar"]["guncellik"] = "Applications are closed"

        blockers = validator.verdict_date_consistency_blockers(
            submission, verdict, today=date(2026, 9, 11)
        )

        self.assertEqual(blockers, [])

    @patch("validate_submissions.apply_decision")
    def test_incomplete_record_is_rejected_not_queued(self, apply_decision):
        submission = complete_submission()
        submission.update({"id": "test", "funding_type": None})

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

    @patch("validate_submissions.judge_with_llm")
    @patch("validate_submissions.fetch_page")
    @patch("validate_submissions.apply_decision")
    def test_login_required_application_link_is_rejected_before_llm(
        self, apply_decision, fetch_page, judge_with_llm
    ):
        fetch_page.side_effect = [
            (401, "https://docs.google.com/forms/d/e/example/viewform", "", None),
            (200, "https://source.example/program", "<p>Programme details</p>", None),
        ]
        submission = complete_submission()
        submission.update({
            "id": "test",
            "url": "https://docs.google.com/forms/d/e/example/viewform",
            "application_url_final": "https://docs.google.com/forms/d/e/example/viewform",
            "source_url": "https://source.example/program",
        })

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "llm_red")
        self.assertEqual(apply_decision.call_args.args[1], "reddet")
        self.assertIn("HTTP 401", apply_decision.call_args.args[2])
        judge_with_llm.assert_not_called()


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
        verdict['dogrulanmis_filtreler']['eligible_citizenships'] = ['CN']
        verdict['kanitlar']['uyruk'] = ""

        self.assertIn(
            "uyruk filtresi alıntısı eksik",
            validator.evidence_quote_blockers(page, verdict),
        )
        verdict['kanitlar']['uyruk'] = "Only citizens of China may apply"
        self.assertNotIn(
            "uyruk filtresi alıntısı eksik",
            validator.evidence_quote_blockers(page, verdict),
        )

    def test_verdict_carries_citizenship_restriction(self):
        verdict = high_confidence_verdict()
        verdict['dogrulanmis_filtreler']['eligible_citizenships'] = ['CN']
        parsed = validator._parse_verdict(json.dumps(verdict))
        self.assertEqual(
            parsed['dogrulanmis_filtreler']['eligible_citizenships'], ['CN'])

    def test_verdict_without_the_field_blocks_approval(self):
        verdict = high_confidence_verdict()
        verdict['dogrulanmis_filtreler'].pop('eligible_citizenships')
        parsed = validator._parse_verdict(json.dumps(verdict))
        self.assertTrue(validator.strict_filter_blockers(parsed))

    @patch('validate_submissions.requests.post')
    @patch('validate_submissions.requests.patch')
    def test_restriction_is_written_before_the_approval_rpc(self, http_patch, http_post):
        http_post.return_value.status_code = 200
        http_post.return_value.json.return_value = {'opportunity_id': 'opp-1'}
        verdict = high_confidence_verdict()
        verdict['dogrulanmis_filtreler']['eligible_citizenships'] = ['CN']

        ok, _ = validator.approve_submission({'id': 'sub-1'}, verdict, dry_run=False)

        self.assertTrue(ok)
        self.assertEqual(
            http_patch.call_args.kwargs['json'], expected_patch(verdict))
        http_post.assert_called_once()

    @patch('validate_submissions.requests.post')
    @patch('validate_submissions.requests.patch')
    def test_approval_is_abandoned_if_the_restriction_cannot_be_written(self, http_patch, http_post):
        # Uyruk yazılamadıysa kayıt {all} ile yayına girmemeli.
        http_patch.side_effect = validator.requests.exceptions.RequestException('boom')
        verdict = high_confidence_verdict()
        verdict['dogrulanmis_filtreler']['eligible_citizenships'] = ['PS']

        ok, detay = validator.approve_submission({'id': 'sub-1'}, verdict, dry_run=False)

        self.assertFalse(ok)
        self.assertIn('yazılamadı', detay)
        http_post.assert_not_called()

    @patch('validate_submissions.requests.post')
    @patch('validate_submissions.requests.patch')
    def test_unrestricted_values_are_explicitly_written(self, http_patch, http_post):
        http_post.return_value.status_code = 200
        http_post.return_value.json.return_value = {'opportunity_id': 'opp-1'}

        ok, _ = validator.approve_submission({'id': 'sub-1'}, high_confidence_verdict(),
                                             dry_run=False)

        self.assertTrue(ok)
        self.assertEqual(
            http_patch.call_args.kwargs['json'],
            expected_patch(high_confidence_verdict()),
        )

    def test_field_restriction_is_written_too(self):
        with patch('validate_submissions.requests.post') as http_post, \
             patch('validate_submissions.requests.patch') as http_patch:
            http_post.return_value.status_code = 200
            http_post.return_value.json.return_value = {'opportunity_id': 'opp-1'}
            verdict = high_confidence_verdict()
            verdict['dogrulanmis_filtreler']['eligible_citizenships'] = ['CN']
            verdict['dogrulanmis_filtreler']['target_fields'] = ['medicine', 'nursing']

            validator.approve_submission({'id': 'sub-1'}, verdict, dry_run=False)

            self.assertEqual(
                http_patch.call_args.kwargs['json'], expected_patch(verdict))

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


class SsrfGuardTests(unittest.TestCase):
    """Ajan servis anahtarıyla çalışıyor ve indireceği URL'i yabancı belirliyor."""

    def test_internal_addresses_are_blocked(self):
        for url in (
            "http://169.254.169.254/latest/meta-data/",   # bulut metadata
            "http://127.0.0.1/",
            "http://localhost:8080/x",
            "http://[::1]/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://metadata.google.internal/",
            "http://kayit.internal/",
            "file:///etc/passwd",
        ):
            with self.subTest(url=url):
                ok, _ = validator.is_public_http_url(url)
                self.assertFalse(ok)

    def test_real_public_urls_pass(self):
        for url in ("https://www.daad.de/en/", "https://erasmus-plus.ec.europa.eu/"):
            with self.subTest(url=url):
                ok, sebep = validator.is_public_http_url(url)
                self.assertTrue(ok, sebep)

    def test_redirect_into_internal_network_is_not_followed(self):
        """attacker.com → 302 → 169.254.169.254 açığı: yönlendirme de süzülmeli."""
        class Cevap:
            def __init__(self, code, loc=None, text="ok"):
                self.status_code = code
                self.headers = {"location": loc} if loc else {}
                self.text = text

        cevaplar = [Cevap(302, "http://169.254.169.254/latest/meta-data/"),
                    Cevap(200, None, "SIZAN-GIZLI-VERI")]
        with patch.object(validator.requests, "get", side_effect=cevaplar):
            status, _final, html, err = validator.fetch_page("https://www.daad.de/tuzak")

        self.assertIsNone(status)
        self.assertIsNone(html)
        self.assertIn("engellendi", err)


if __name__ == "__main__":
    unittest.main()


class ReligionPolicyTests(unittest.TestCase):
    """Başvuranın dinine göre ayrım yapan fırsatlar yayınlanmaz.

    Bu bir kalite kuralı değil, platform politikası: fırsat her açıdan
    kusursuz olsa bile reddedilir.
    """

    def test_din_sarti_rejects_regardless_of_confidence(self):
        for guven in ("yuksek", "orta", "dusuk"):
            with self.subTest(guven=guven):
                verdict = high_confidence_verdict()
                verdict["guven"] = guven
                verdict["din_sarti"] = True
                eylem, gerekce = validator.decide(verdict)
                self.assertEqual(eylem, "reddet")
                self.assertIn("din", gerekce.lower())

    def test_clean_verdict_still_approves(self):
        verdict = high_confidence_verdict()
        verdict["din_sarti"] = False
        self.assertEqual(validator.decide(verdict)[0], "onayla")

    def test_religion_word_blocks_auto_approval_even_if_llm_says_no(self):
        """Model 'şart yok' dese bile metinde din geçiyorsa kayıt reddedilir."""
        sub = complete_submission()
        sub["eligibility_notes"] = "Open to protestant students of all disciplines."
        verdict = high_confidence_verdict()
        verdict["din_sarti"] = False
        blockers = validator.auto_approval_blockers(sub, verdict)
        self.assertTrue(any("din" in b for b in blockers), blockers)

    def test_religion_as_a_field_of_study_is_not_blocked(self):
        """İlahiyat bursu engellenmemeli: konuyu ÇALIŞMAK ≠ o dine MENSUP OLMAK."""
        sub = complete_submission()
        sub["eligibility_notes"] = "Lisans öğrencileri programa başvurabilir."
        sub["title"] = "Karşılaştırmalı din sosyolojisi doktora bursu"
        verdict = high_confidence_verdict()
        verdict["din_sarti"] = False
        self.assertEqual(validator.auto_approval_blockers(sub, verdict), [])


class FieldDictionaryTests(unittest.TestCase):
    """Bölüm sözlüğü tek kaynaktan (src/lib/fields.ts) okunuyor."""

    def test_slugs_loaded_from_shared_file(self):
        self.assertGreater(len(validator.FIELD_SLUGS), 100)
        self.assertIn("mechatronics", validator.VALID_FIELDS)
        self.assertIn("computer_science", validator.VALID_FIELDS)

    def test_prompt_lists_every_slug(self):
        for slug in ("mechatronics", "social_work", "archaeology"):
            self.assertIn(slug, validator.SYSTEM_PROMPT)

    def test_unknown_slug_is_dropped(self):
        self.assertEqual(validator.clean_fields(["mechatronics", "uydurma"]),
                         ["mechatronics"])


# ─── Filtre politikası (Eylül 2026) ──────────────────────────────────────────
# Tek ölçüt doğruluk: sayfa kısıt koyuyorsa kısıt kanıtıyla yazılır, koymuyorsa
# kısıtsız yazılır. Uyruk ve yaşta "kısıt yok" kararı ayrıca tam sayfa
# taramasıyla sınanır. Son tarih birebir alıntıdan deterministik doğrulanır.

SILENT_PAGE = (
    "Scholarship programme for graduates. Fully funded. Hosted in Germany. "
    "Bachelor students may apply. Application deadline: 15 November 2099. "
    "Applications are open now."
)


def silent_page_verdict():
    """Sayfa uyruk, yaş, dil ve bölümden hiç bahsetmiyor."""
    verdict = high_confidence_verdict()
    verdict["dogrulanmis_filtreler"]["deadline"] = "2099-11-15"
    verdict["kanitlar"] = {
        "guncellik": "Applications are open now",
        "son_tarih": "Application deadline: 15 November 2099",
        "kategori": "Scholarship programme for graduates",
        "finansman": "Fully funded",
        "ulke": "Hosted in Germany",
        "uygunluk": "Bachelor students may apply",
        "uyruk": "",
        "yas": "",
        "egitim": "Bachelor students may apply",
        "dil": "",
        "bolum": "",
    }
    return verdict


class SilentPagePolicyTests(unittest.TestCase):
    def test_silence_is_no_restriction_and_needs_no_quote(self):
        verdict = silent_page_verdict()
        self.assertEqual(
            validator.page_evidence_blockers(
                SILENT_PAGE, SILENT_PAGE, verdict, today=date(2099, 9, 29)),
            [],
        )
        self.assertEqual(validator.strict_filter_blockers(verdict), [])

    def test_restriction_still_needs_a_verbatim_quote(self):
        verdict = silent_page_verdict()
        verdict["dogrulanmis_filtreler"]["age_min"] = 18
        verdict["dogrulanmis_filtreler"]["age_max"] = 30
        self.assertIn(
            "yaş filtresi alıntısı eksik",
            validator.evidence_quote_blockers(SILENT_PAGE, verdict),
        )
        verdict["kanitlar"]["yas"] = "aged 18 to 30"
        self.assertIn(
            'yaş filtresi alıntısı sayfa metninde bulunamadı ("aged 18 to 30")',
            validator.evidence_quote_blockers(SILENT_PAGE, verdict),
        )

    def test_unverified_openness_quote_is_dropped_not_stored(self):
        verdict = silent_page_verdict()
        verdict["kanitlar"]["uyruk"] = "Open to all nationalities"   # sayfada yok
        self.assertEqual(validator.evidence_quote_blockers(SILENT_PAGE, verdict), [])
        self.assertEqual(verdict["kanitlar"]["uyruk"], "")

    def test_flag_false_means_ambiguous_and_blocks(self):
        verdict = silent_page_verdict()
        verdict["uyruk_dogrulandi"] = False
        self.assertIn(
            "uyruk filtresi kesin doğrulanmadı",
            validator.strict_filter_blockers(verdict),
        )


class StrictSilenceScanTests(unittest.TestCase):
    """Uyruk/yaş (ve dil sertifikası) kısıtını modelin kaçırmasına karşı ağ."""

    def scan(self, page, **filters):
        verdict = silent_page_verdict()
        verdict["dogrulanmis_filtreler"].update(filters)
        return validator.strict_silence_blockers(page, verdict)

    def test_missed_citizenship_condition_is_caught(self):
        for page in (
            "Only citizens of EU member states are eligible.",
            "Applicants must hold the nationality of a DAC country.",
            "Başvuru için T.C. vatandaşı olmak gerekir.",
            "Adayların Alman vatandaşı olması gerekir.",
            "Uyruk şartı: yalnız AB ülkeleri.",
        ):
            with self.subTest(page=page):
                blockers = self.scan(page)
                self.assertTrue(any("uyruk" in b for b in blockers), blockers)

    def test_missed_age_condition_is_caught(self):
        for page in (
            "Participants must be aged 18-30.",
            "Applicants under the age of 35 may apply.",
            "18-30 yaş arası gençler başvurabilir.",
            "Yaş sınırı 30'dur.",
        ):
            with self.subTest(page=page):
                blockers = self.scan(page)
                self.assertTrue(any("yaş" in b for b in blockers), blockers)

    def test_missed_language_certificate_is_caught(self):
        blockers = self.scan("An IELTS score of 6.5 is required.")
        self.assertTrue(any("dil" in b for b in blockers), blockers)

    def test_topic_words_are_not_conditions(self):
        # Gençlik projelerinde "vatandaşlık" konu, "yaşayan" yaş değil.
        for page in (
            "A training course on active citizenship and digital citizenship.",
            "Aktif vatandaşlık temalı gençlik değişimi.",
            "Türkiye'de yaşayan gençler için yaşam becerileri atölyesi.",
            "Web pages and images of the programme. English | Deutsch",
        ):
            with self.subTest(page=page):
                self.assertEqual(self.scan(page), [])

    def test_recorded_restriction_skips_the_scan(self):
        # Kısıt yazıldıysa tarama değil alıntı kapısı devrede.
        self.assertEqual(
            self.scan("Only citizens of China may apply.",
                      eligible_citizenships=["CN"]),
            [],
        )

    def test_verified_openness_quote_skips_the_scan(self):
        page = SILENT_PAGE + " Open to all nationalities."
        verdict = silent_page_verdict()
        verdict["kanitlar"]["uyruk"] = "Open to all nationalities"
        self.assertEqual(validator.evidence_quote_blockers(page, verdict), [])
        self.assertEqual(validator.strict_silence_blockers(page, verdict), [])

    def test_restriction_quoted_as_openness_does_not_skip_the_scan(self):
        # Model kısıtsız yazıp kanıt olarak kısıt cümlesini verdi: çelişki.
        page = SILENT_PAGE + " Applicants must be citizens of Germany."
        verdict = silent_page_verdict()
        verdict["kanitlar"]["uyruk"] = "Applicants must be citizens of Germany"
        self.assertEqual(validator.evidence_quote_blockers(page, verdict), [])
        self.assertTrue(validator.strict_silence_blockers(page, verdict))

    def test_openness_quote_does_not_hide_another_condition(self):
        page = (SILENT_PAGE + " Open to all nationalities. "
                "Only nationals of EU member states receive the travel grant.")
        verdict = silent_page_verdict()
        verdict["kanitlar"]["uyruk"] = "Open to all nationalities"
        self.assertTrue(validator.strict_silence_blockers(page, verdict))

    def test_scan_sees_text_beyond_the_llm_truncation(self):
        verdict = silent_page_verdict()
        truncated = SILENT_PAGE
        full = SILENT_PAGE + (" filler" * 5000) + " Only nationals of Norway may apply."
        self.assertEqual(
            validator.page_evidence_blockers(
                truncated, truncated, verdict, today=date(2099, 9, 29)), [])
        self.assertTrue(
            validator.page_evidence_blockers(
                truncated, full, verdict, today=date(2099, 9, 29)))


class DeadlineEvidenceTests(unittest.TestCase):
    TODAY = date(2099, 9, 29)

    def verdict(self, quote, deadline, rolling=False):
        verdict = silent_page_verdict()
        verdict["kanitlar"]["son_tarih"] = quote
        verdict["dogrulanmis_filtreler"]["deadline"] = deadline
        verdict["surekli_basvuru"] = rolling
        return verdict

    def test_declared_date_must_appear_in_the_quote(self):
        ok = self.verdict("Application deadline: 15 November 2099", "2099-11-15")
        self.assertEqual(validator.deadline_verification_blockers(ok, self.TODAY), [])
        wrong = self.verdict("Application deadline: 15 November 2099", "2099-11-30")
        self.assertTrue(validator.deadline_verification_blockers(wrong, self.TODAY))

    def test_month_only_is_not_a_deadline(self):
        verdict = self.verdict("Deadline: November 2099", "2099-11-30")
        self.assertTrue(validator.deadline_verification_blockers(verdict, self.TODAY))

    def test_past_deadline_blocks(self):
        verdict = self.verdict("Deadline: 1 March 2026", "2026-03-01")
        self.assertIn(
            "son tarih geçmiş (2026-03-01)",
            validator.deadline_verification_blockers(verdict, self.TODAY),
        )

    def test_rolling_needs_an_explicit_rolling_quote(self):
        for quote in (
            "Applications are accepted on a rolling basis.",
            "Applications may be submitted at any time.",
            "There is no deadline to apply.",
            "Başvurular yıl boyunca sürekli alınır.",
        ):
            with self.subTest(quote=quote):
                verdict = self.verdict(quote, None, rolling=True)
                self.assertEqual(
                    validator.deadline_verification_blockers(verdict, self.TODAY), [])
        for quote in (
            "The deadline varies by university.",
            "Please see the university website for deadlines.",
        ):
            with self.subTest(quote=quote):
                verdict = self.verdict(quote, None, rolling=True)
                self.assertTrue(
                    validator.deadline_verification_blockers(verdict, self.TODAY))

    def test_rolling_and_a_date_together_is_contradictory(self):
        verdict = self.verdict("rolling basis", "2099-01-01", rolling=True)
        self.assertTrue(validator.deadline_verification_blockers(verdict, self.TODAY))

    def test_no_date_and_no_rolling_blocks(self):
        verdict = self.verdict("See website", None, rolling=False)
        self.assertTrue(validator.deadline_verification_blockers(verdict, self.TODAY))

    def test_missing_deadline_key_blocks(self):
        verdict = silent_page_verdict()
        verdict["dogrulanmis_filtreler"].pop("deadline")
        self.assertIn(
            "kanıtlanmış deadline değeri yok/geçersiz",
            validator.strict_filter_blockers(verdict),
        )

    def test_extract_dates_reads_every_supported_format(self):
        text = ("15.11.2099 / 15 Kasım 2099 / November 15th, 2099 / "
                "the 15th of November 2099 / 2099-11-15 / 1 December 2099")
        self.assertEqual(
            validator.extract_dates(text), [date(2099, 11, 15), date(2099, 12, 1)])
        self.assertEqual(validator.extract_dates("November 2099"), [])

    def test_recheck_order_puts_waiting_rows_first_and_rotates_the_rest(self):
        rows = [{"id": f"j{i}", "admin_note": "[ajan] BELİRSİZ: elle bak — x"}
                for i in range(20)]
        rows.insert(5, {"id": "fresh", "admin_note": None})
        rows.insert(9, {"id": "retry", "admin_note": "[ajan] TEKRAR: teknik"})
        first = validator.recheck_order(rows, "2099-10-04T09")
        second = validator.recheck_order(rows, "2099-10-04T13")
        self.assertEqual([r["id"] for r in first[:2]], ["fresh", "retry"])
        self.assertEqual(sorted(r["id"] for r in first), sorted(r["id"] for r in rows))
        self.assertNotEqual([r["id"] for r in first[2:7]], [r["id"] for r in second[2:7]])
        self.assertEqual(first, validator.recheck_order(rows, "2099-10-04T09"))

    def test_extract_dates_reads_european_slash_dates(self):
        # Avrupa Gençlik Portalı biçimi; belirsizse GG/AA, ikinci sayı >12 ise AA/GG.
        self.assertEqual(
            validator.extract_dates("Application deadline: 10/01/2099 12:00"),
            [date(2099, 1, 10)])
        self.assertEqual(validator.extract_dates("25/11/2099"), [date(2099, 11, 25)])
        self.assertEqual(validator.extract_dates("11/25/2099"), [date(2099, 11, 25)])
        self.assertEqual(validator.extract_dates("1/2/20991"), [])

    def test_free_text_scraper_deadline_is_not_trusted_without_llm(self):
        self.assertIsNone(validator.strict_iso_date("15 January 2020; 15 January 2099"))
        self.assertEqual(validator.strict_iso_date(" 2099-01-15 "), date(2099, 1, 15))

    def test_date_consistency_uses_the_verified_deadline(self):
        # deadline_text'teki ilk tarih geçmiş ama kanıtlanmış tarih gelecekte:
        # model "açık" dediğinde tutarsızlık sayılmamalı.
        submission = complete_submission()
        submission["deadline_text"] = "15 January 2020; for the next intake 15 November 2099"
        verdict = self.verdict("next intake 15 November 2099", "2099-11-15")
        self.assertEqual(
            validator.verdict_date_consistency_blockers(
                submission, verdict, today=self.TODAY), [])

    def test_parsed_verdict_keeps_iso_or_null_deadline(self):
        for raw, expected in (("2099-11-15", "2099-11-15"), (None, None)):
            with self.subTest(raw=raw):
                verdict = high_confidence_verdict()
                verdict["dogrulanmis_filtreler"]["deadline"] = raw
                parsed = validator._parse_verdict(json.dumps(verdict))
                self.assertEqual(parsed["dogrulanmis_filtreler"]["deadline"], expected)
        verdict = high_confidence_verdict()
        verdict["dogrulanmis_filtreler"]["deadline"] = "15 Nov 2099"
        parsed = validator._parse_verdict(json.dumps(verdict))
        self.assertNotIn("deadline", parsed["dogrulanmis_filtreler"])

    def test_both_passes_must_agree_on_rolling(self):
        first = self.verdict("rolling basis", None, rolling=True)
        second = self.verdict("rolling basis", None, rolling=False)
        self.assertIn(
            "iki denetim sürekli başvuru konusunda uzlaşmadı",
            validator.filter_consensus_blockers(first, second),
        )


class QuoteMatchingTests(unittest.TestCase):
    def test_typographic_differences_do_not_fail_a_real_quote(self):
        page = "Applicants must be under 30 \u2013 see \u201cEligibility\u201d.\u00a0It\u2019s free."
        haystack = validator._normalize_evidence_text(page)
        self.assertTrue(validator._quote_in_page(
            'Applicants must be under 30 - see "Eligibility". It\'s free.', haystack))

    def test_ellipsis_parts_must_appear_in_order(self):
        haystack = validator._normalize_evidence_text(
            "Applications are open. The programme lasts ten months. Deadline 1 May 2099.")
        self.assertTrue(validator._quote_in_page(
            "Applications are open... Deadline 1 May 2099", haystack))
        self.assertFalse(validator._quote_in_page(
            "Deadline 1 May 2099... Applications are open", haystack))
        self.assertFalse(validator._quote_in_page(
            "Applications are open... fully funded", haystack))


class DecisionOutcomeTests(unittest.TestCase):
    # Örnek sayfadaki son tarih 2099; "bugün" de ona göre sabitleniyor ki
    # son tarih makullük kapısı (en fazla 2 yıl ileri) testi bozmasın.
    def setUp(self):
        patcher = patch("validate_submissions.platform_today", return_value=date(2099, 9, 29))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_listing_page_is_rejected(self):
        verdict = high_confidence_verdict()
        verdict["tek_firsat"] = False
        self.assertEqual(validator.decide(verdict)[0], "reddet")

    @patch("validate_submissions.judge_with_llm")
    @patch("validate_submissions.fetch_page")
    @patch("validate_submissions.apply_decision")
    def test_unverifiable_field_goes_to_a_human_not_to_rejection(
        self, apply_decision, fetch_page, judge_with_llm
    ):
        fetch_page.return_value = (
            200, "https://example.org/program/apply",
            f"<html><body><p>{SILENT_PAGE}</p></body></html>", None)
        verdict = silent_page_verdict()
        verdict["finansman_dogrulandi"] = False
        judge_with_llm.return_value = verdict
        submission = complete_submission()
        submission.update({"id": "t", "source_url": submission["url"]})

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "belirsiz")
        self.assertEqual(apply_decision.call_args.args[1], "belirsiz")

    @patch("validate_submissions.judge_with_llm")
    @patch("validate_submissions.fetch_page")
    @patch("validate_submissions.apply_decision")
    def test_missed_age_limit_on_the_page_goes_to_a_human(
        self, apply_decision, fetch_page, judge_with_llm
    ):
        page = SILENT_PAGE + " Participants must be aged 18-30."
        fetch_page.return_value = (
            200, "https://example.org/program/apply",
            f"<html><body><p>{page}</p></body></html>", None)
        judge_with_llm.return_value = silent_page_verdict()   # yaşı kaçırdı
        submission = complete_submission()
        submission.update({"id": "t", "source_url": submission["url"]})

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "belirsiz")
        self.assertIn("aged", apply_decision.call_args.args[2])

    @patch("validate_submissions.judge_with_llm")
    @patch("validate_submissions.fetch_page")
    @patch("validate_submissions.apply_decision")
    def test_silent_page_with_verified_fields_is_approved(
        self, apply_decision, fetch_page, judge_with_llm
    ):
        fetch_page.return_value = (
            200, "https://example.org/program/apply",
            f"<html><body><p>{SILENT_PAGE}</p></body></html>", None)
        judge_with_llm.side_effect = [silent_page_verdict(), silent_page_verdict()]
        submission = complete_submission()
        submission.update({"id": "t", "source_url": submission["url"]})

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "onaylandi")
        self.assertEqual(judge_with_llm.call_count, 2)


class GuidedRouteTests(unittest.TestCase):
    def test_official_detail_page_can_be_guided(self):
        submission = {
            "details_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135739",
            "source_url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135739",
            "url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135739",
        }
        self.assertEqual(validator.guided_info_url(submission), submission["details_url"])

    def test_aggregator_or_generic_page_is_never_guided(self):
        for submission in (
            {"url": "https://www.nasilgitmis.com/firsat", "source_url": "https://nasilgitmis.com/firsat"},
            {"url": "https://www.youthop.com/post"},
            {"url": "https://example.org/"},
            {"url": "https://instagram.com/p/abc"},
        ):
            with self.subTest(submission=submission):
                self.assertIsNone(validator.guided_info_url(submission))

    @patch("validate_submissions.resolve_application_route")
    def test_missing_direct_form_falls_back_to_official_page(self, resolve):
        resolve.return_value.verified = False
        resolve.return_value.application_url = None
        resolve.return_value.reason = "form bulunamadı"
        detail = "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=1"
        submission = {"id": "t", "url": detail, "source_url": detail, "details_url": detail,
                      "application_route_status": "unverified"}

        ok, note = validator.verify_and_store_application_route(submission, dry_run=True)

        self.assertTrue(ok, note)
        self.assertEqual(submission["application_route_status"], "guided")
        self.assertEqual(submission["url"], detail)
        self.assertIsNone(submission["application_url_final"])

    @patch("validate_submissions.resolve_application_route")
    def test_aggregator_without_direct_form_is_still_rejected(self, resolve):
        resolve.return_value.verified = False
        resolve.return_value.application_url = None
        resolve.return_value.reason = "form bulunamadı"
        submission = {"id": "t", "url": "https://nasilgitmis.com/x",
                      "source_url": "https://nasilgitmis.com/x",
                      "application_route_status": "unverified"}

        ok, _ = validator.verify_and_store_application_route(submission, dry_run=True)

        self.assertFalse(ok)


class PromptContractTests(unittest.TestCase):
    def test_prompt_treats_silence_as_no_restriction(self):
        self.assertIn("Bahsetmemek kısıt yok demektir", validator.SYSTEM_PROMPT)
        self.assertNotIn("kısıt yok demek\n  DEĞİLDİR", validator.SYSTEM_PROMPT)
        self.assertIn("ÖZELLİKLE UYRUK VE YAŞ", validator.SYSTEM_PROMPT)
        self.assertIn('"deadline"', validator.SYSTEM_PROMPT)
        self.assertIn('"resmi_kaynak"', validator.SYSTEM_PROMPT)


class ClosedFormTests(unittest.TestCase):
    @patch("validate_submissions.apply_decision")
    def test_closed_google_form_is_rejected_as_closed(self, apply_decision):
        submission = complete_submission()
        closed = "https://docs.google.com/forms/d/e/1FAIpQLSer5Za/closedform"
        submission.update({"id": "t", "url": closed, "application_url_final": closed})

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "sure_gecti")
        self.assertEqual(apply_decision.call_args.args[1], "reddet")
        self.assertIn("kapanmış", apply_decision.call_args.args[2])

    @patch("validate_submissions.resolve_application_route")
    @patch("validate_submissions.apply_decision")
    def test_unverifiable_route_without_official_page_goes_to_a_human(
        self, apply_decision, resolve
    ):
        resolve.return_value.verified = False
        resolve.return_value.application_url = None
        resolve.return_value.reason = "aday başvuru hedefi teknik olarak doğrulanamadı"
        submission = complete_submission()
        submission.update({
            "id": "t", "url": "https://nasilgitmis.com/x",
            "source_url": "https://nasilgitmis.com/x", "details_url": None,
            "application_route_status": "unverified",
            "application_url_verified_at": None, "application_url_final": None,
        })

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "belirsiz")
        self.assertEqual(apply_decision.call_args.args[1], "belirsiz")

    @patch("validate_submissions.resolve_application_route")
    @patch("validate_submissions.apply_decision")
    def test_resolver_closed_form_reason_rejects(self, apply_decision, resolve):
        from application_links import CLOSED_FORM_REASON
        resolve.return_value.verified = False
        resolve.return_value.application_url = None
        resolve.return_value.reason = CLOSED_FORM_REASON
        submission = complete_submission()
        submission.update({
            "id": "t", "url": "https://nasilgitmis.com/x",
            "source_url": "https://nasilgitmis.com/x", "details_url": None,
            "application_route_status": "unverified",
            "application_url_verified_at": None, "application_url_final": None,
        })

        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})

        self.assertEqual(result, "sure_gecti")
        self.assertEqual(apply_decision.call_args.args[1], "reddet")


class DeadlinePlausibilityTests(unittest.TestCase):
    def test_far_future_deadline_from_a_typo_is_not_trusted(self):
        for quote, iso in (("Application deadline (24h UTC) : 1 June 2926", "2926-06-01"),
                           ("Application deadline (24h UTC) : 30 September 2032", "2032-09-30")):
            with self.subTest(iso=iso):
                verdict = silent_page_verdict()
                verdict["kanitlar"]["son_tarih"] = quote
                verdict["dogrulanmis_filtreler"]["deadline"] = iso
                blockers = validator.deadline_verification_blockers(verdict, date(2026, 10, 3))
                self.assertTrue(any("makul değil" in b for b in blockers), blockers)

    def test_failed_quote_is_shown_in_the_reason(self):
        verdict = silent_page_verdict()
        verdict["kanitlar"]["finansman"] = "All costs are covered by the organisers"
        blockers = validator.evidence_quote_blockers(SILENT_PAGE, verdict)
        self.assertTrue(any("All costs are covered" in b for b in blockers), blockers)


class ModelFallbackTests(unittest.TestCase):
    """3 Ekim 2026: birincil model 410 Gone döndü, ajan tamamen durdu."""

    def setUp(self):
        validator._ACTIVE_LLM_MODEL = None
        self.addCleanup(setattr, validator, "_ACTIVE_LLM_MODEL", None)

    @staticmethod
    def response(status, text="{}"):
        class R:
            pass
        r = R()
        r.status_code, r.text = status, text
        r.json = lambda: {"choices": [{"message": {"content": '{"ok": true}'},
                                       "finish_reason": "stop"}]}
        return r

    @patch("validate_submissions._post_chat_once")
    def test_retired_model_falls_back_and_is_remembered(self, post):
        gone = self.response(410, '{"detail":"reached its end of life"}')
        post.side_effect = [gone, self.response(200), self.response(200)]

        first = validator.post_chat([{"role": "user", "content": "x"}])
        second = validator.post_chat([{"role": "user", "content": "x"}])

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        models = [call.args[0]["model"] for call in post.call_args_list]
        self.assertEqual(models, [validator.LLM_MODELS[0], validator.LLM_MODELS[1],
                                  validator.LLM_MODELS[1]])
        self.assertEqual(validator.active_llm_model(), validator.LLM_MODELS[1])

    @patch("validate_submissions._post_chat_once")
    def test_unsupported_reasoning_parameter_is_dropped(self, post):
        post.side_effect = [self.response(400, "unknown parameter reasoning_effort"),
                            self.response(200)]

        res = validator.post_chat([{"role": "user", "content": "x"}])

        self.assertEqual(res.status_code, 200)
        self.assertIn("reasoning_effort", post.call_args_list[0].args[0])
        self.assertNotIn("reasoning_effort", post.call_args_list[1].args[0])

    @patch("validate_submissions._post_chat_once")
    def test_ordinary_error_does_not_switch_models(self, post):
        post.return_value = self.response(500, "server error")

        res = validator.post_chat([{"role": "user", "content": "x"}])

        self.assertEqual(res.status_code, 500)
        self.assertEqual(post.call_count, 1)

    def test_retired_model_is_not_the_default(self):
        self.assertNotIn("nvidia/nemotron-3-super-120b-a12b", validator.LLM_MODELS)


class TokenQuoteMatchingTests(unittest.TestCase):
    """Ekim 2026: gerçek alıntılar başlık, ":" ve madde işaretleri yüzünden
    "sayfada yok" sayılıyordu. Sözcük düzeyinde eşleşme bunları kurtarmalı,
    uydurma sözcükleri ise yakalamalı."""

    PAGE = ("Profile of participants\n✔ The call is open for youth leaders and youth "
            "workers who fit the following criteria:\n- representatives of youth work "
            "organisations\nThis project is financed by the Hellenic National Agency "
            "of Erasmus+/ Youth and European Solidarity Corps.")

    def match(self, quote):
        return validator._quote_in_page(quote, validator._normalize_evidence_text(self.PAGE))

    def test_heading_colon_and_bullet_do_not_break_a_real_quote(self):
        self.assertTrue(self.match(
            "Profile of participants: The call is open for youth leaders and youth workers"))
        self.assertTrue(self.match(
            "financed by the Hellenic National Agency of Erasmus+/Youth and European "
            "Solidarity Corps"))

    def test_invented_words_are_still_caught(self):
        self.assertFalse(self.match(
            "This project is financed by the National Agencies of the Erasmus+ Youth in Action Programme"))
        self.assertFalse(self.match("The call is open for youth leaders and teachers who"))

    def test_short_quotes_must_be_contiguous(self):
        self.assertTrue(self.match("youth leaders and youth workers"))
        self.assertFalse(self.match("youth leaders youth workers"))

    def test_tooltip_list_goes_to_the_end_not_mid_sentence(self):
        html = ('<p>for 25 participants</p><p>from Erasmus+ Youth Programme countries '
                '<img title="Austria, Belgium, Türkiye"/> and recommended for</p><p>Youth workers</p>')
        text = validator.page_to_text(html)
        self.assertTrue(validator._quote_in_page(
            "for 25 participants from Erasmus+ Youth Programme countries and recommended for Youth workers",
            validator._normalize_evidence_text(text)))
        self.assertTrue(text.rstrip().endswith("Ek bilgi (ipucu): Austria, Belgium, Türkiye"))


class QuoteRepairTests(unittest.TestCase):
    def test_only_failing_required_fields_are_listed(self):
        verdict = silent_page_verdict()
        verdict["kanitlar"]["finansman"] = "All costs covered"          # sayfada yok
        verdict["dogrulanmis_filtreler"]["age_min"] = 18                 # kısıt, alıntısız
        self.assertEqual(
            validator.failing_quote_fields(SILENT_PAGE, verdict), ["finansman", "yas"])

    @patch("validate_submissions.time.sleep")
    @patch("validate_submissions.request_llm_json")
    def test_repaired_quote_is_kept_only_if_it_is_on_the_page(self, llm, _sleep):
        verdict = silent_page_verdict()
        verdict["kanitlar"]["finansman"] = ""
        verdict["kanitlar"]["uygunluk"] = ""
        llm.return_value = {"kanitlar": {
            "finansman": "Fully funded",                          # sayfada var
            "uygunluk": "Open to students of every country",      # uydurma
        }}

        repaired = validator.repair_quotes(SILENT_PAGE, verdict, ["finansman", "uygunluk"])

        self.assertEqual(repaired, 1)
        self.assertEqual(verdict["kanitlar"]["finansman"], "Fully funded")
        self.assertEqual(verdict["kanitlar"]["uygunluk"], "")
        # Filtre değerleri ve kararlar onarımda değişmez.
        self.assertEqual(verdict["dogrulanmis_filtreler"], silent_page_verdict()["dogrulanmis_filtreler"])

    @patch("validate_submissions.request_llm_json")
    def test_no_repair_call_when_all_quotes_verify(self, llm):
        validator._repair_failing_quotes(SILENT_PAGE, silent_page_verdict(), {"llm_calls": 0})
        llm.assert_not_called()


class OnlineOnlyTests(unittest.TestCase):
    @patch("validate_submissions.apply_decision")
    def test_webinar_series_is_rejected_before_llm(self, apply_decision):
        submission = complete_submission()
        submission.update({"id": "t", "title": "Wellness Navigators - Webinar Series"})
        result = validator.process(submission, True, set(), set(), {"llm_calls": 0})
        self.assertEqual(result, "llm_red")
        self.assertIn("çevrim içi", apply_decision.call_args.args[2])

    def test_ordinary_titles_are_not_flagged(self):
        from discovery_gate import ONLINE_ONLY_RE
        for title in ("Online başvurulu Almanya ESC projesi", "Training Course in Malta",
                      "Youth Exchange: Digital Citizenship"):
            with self.subTest(title=title):
                self.assertIsNone(ONLINE_ONLY_RE.search(title))
        for title in ("E-learning for youth workers", "Online training course on inclusion",
                      "Virtual exchange developments"):
            with self.subTest(title=title):
                self.assertIsNotNone(ONLINE_ONLY_RE.search(title))
