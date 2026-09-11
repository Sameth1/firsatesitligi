"""
extract_age_range regresyon testleri.

NEDEN VAR: DAAD sayfalarındaki "awarded for a period of between 10 and 24
months" ifadesi yaş aralığı sanılıyordu ve 5 fırsata age_min=10 yazılmıştı.
Yaş bir HARD filtre olduğu için (RPC'de age_min <= p_age), yanlış aralık
kullanıcıyı sessizce yanlış eliyor: 25 yaşındaki biri bu burslara uygun
olmasına rağmen sonuçlarda göremiyordu.

`between` artık tek başına yaş sinyali sayılmıyor — arkasından bir yaş
ibaresi gelmesi gerekiyor. Bu dosya hem o hatanın dönmediğini hem de gerçek
yaş ifadelerinin bozulmadığını doğruluyor.
"""

import sys
import types
import unittest

# agent_reach_url_scraper, scrapling'i modül düzeyinde import ediyor; bu paket
# projede bildirilmiş bir bağımlılık değil (requirements dosyası yok) ve test
# edilen fonksiyon saf regex. Ağır bağımlılığı stub'layıp modülü alıyoruz.
if "scrapling.fetchers" not in sys.modules:
    _scrapling = types.ModuleType("scrapling")
    _fetchers = types.ModuleType("scrapling.fetchers")
    _fetchers.Fetcher = object
    _fetchers.StealthyFetcher = object
    _scrapling.fetchers = _fetchers
    sys.modules.setdefault("scrapling", _scrapling)
    sys.modules.setdefault("scrapling.fetchers", _fetchers)

import agent_reach_url_scraper as reach  # noqa: E402


class ExtractAgeRangeTest(unittest.TestCase):
    def assert_age(self, text, expected):
        self.assertEqual(reach.extract_age_range(text), expected, msg=text)

    # ─── Süre ifadeleri yaş sanılmamalı (asıl hata) ────────────────────
    def test_daad_burs_suresi_yas_sanilmaz(self):
        self.assert_age(
            "The scholarship is awarded for a period of between 10 and 24 months.",
            (None, None),
        )

    def test_fonlama_suresi_yas_sanilmaz(self):
        self.assert_age("Funding is granted for between 12 and 24 months.", (None, None))

    def test_hafta_ve_donem_yas_sanilmaz(self):
        self.assert_age("The programme lasts between 6 and 12 weeks.", (None, None))
        self.assert_age("a stay of between 10 and 24 semesters", (None, None))

    def test_deneyim_yili_yas_sanilmaz(self):
        self.assert_age(
            "Requires between 3 and 5 years of professional experience.", (None, None)
        )

    # ─── Gerçek yaş ifadeleri bozulmamalı ──────────────────────────────
    def test_aged_araligi(self):
        self.assert_age("Open to applicants aged 18 to 30 years old.", (18, 30))

    def test_ages_kisa_bicim(self):
        self.assert_age("ages 18-35 are eligible", (18, 35))

    def test_between_ancak_yas_ibaresiyle(self):
        self.assert_age("for young people between 13 and 30 years of age", (13, 30))

    def test_turkce_yas_araligi(self):
        self.assert_age("18-30 yaş arası gençler başvurabilir.", (18, 30))

    def test_ust_sinir_haric_tutan(self):
        # "under 28" → 28 dahil değil, üst sınır 27.
        self.assert_age(
            "Only applicants who were under 28 at the time of obtaining the degree.",
            (None, 27),
        )

    def test_yas_ifadesi_yoksa_bos(self):
        self.assert_age("Open to students of all backgrounds.", (None, None))


if __name__ == "__main__":
    unittest.main()
