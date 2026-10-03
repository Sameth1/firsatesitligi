"""Yeni bulunan kayıtlar için LLM öncesi ucuz ve kapalı kalite kapısı.

Bu kapı YALNIZ kaydı hiç değerlendirilemez kılan eksikleri eler: başlık,
bağlantı, kategori, ülke, finansman ve uygunluk metni. Bunlar olmadan ajanın
doğrulayacağı bir şey yoktur.

Son tarih ve doğrudan başvuru adımı BURADA ELENMİYOR, ajana bırakılıyor:

* Son tarih: kaynaklar tarihi çoğu zaman serbest metin veriyor ("Application
  deadline: 31 October 2026", "rolling basis"). Eskiden tam ISO tarih yoksa
  kayıt ajana hiç ulaşmıyordu; DAAD'ın 151 bursundan yalnız 40'ında genel
  son tarih var ve geri kalanı sessizce düşüyordu. Ajan tarihi sayfadan
  birebir alıntıyla çıkarıyor, alıntıyı deterministik olarak ayrıştırıp
  karşılaştırıyor; "sürekli başvuru" da ancak sayfada açıkça yazıyorsa kabul.
  Burada yalnız kesin ISO olup GEÇMİŞ olan tarih eleniyor.

* Doğrudan başvuru adımı: ajan kaynaktan formu/portalı en fazla iki adımda
  arıyor; bulamazsa kurumun resmî program sayfası "Koşullar ve Başvuru"
  olarak yayınlanabiliyor (application_route_status='guided'). Kapı bunu
  önceden bilemez.
"""

import re
from datetime import date, timedelta
from urllib.parse import urlparse


VALID_CATEGORIES = {
    "scholarship", "volunteering", "youth_project",
    "internship", "summer_school", "exchange",
}
VALID_FUNDING = {"full", "partial", "free", "stipend"}

# Yalnız çevrim içi etkinlik yurt dışı fırsatı değildir (platformun konusu
# yurt dışına gitmek). Başlıkta ya da etkinlik türünde bu kalıplar varsa kayıt
# kapsam dışıdır. "online" tek başına değil, belirli kalıplar aranıyor:
# "online başvuru" gibi ifadeler yanlış alarm vermesin.
ONLINE_ONLY_RE = re.compile(
    r"\b(?:webinars?|e-?learning|online\s+(?:course|training|activity|seminar|"
    r"workshop|series|event|edition|programme|program)|virtual\s+(?:exchange|"
    r"training|event|mobility))\b",
    re.IGNORECASE,
)

# Scraper'ların "bu fırsatı daha önce gördük mü?" sorusu için bakılacak
# kolonlar. Yalnız submissions.url'e bakmak yetmiyordu: scraper kaynak yazının
# adresini (source_url) soruyor, ama başvuru formu bulununca submissions.url'e
# FORMUN adresi yazılıyor. Aynı nasilgitmis yazısı bu yüzden her hafta yeniden
# ekleniyor, ajan da her seferinde "kopya" diye reddediyordu (Eylül 2026:
# "Almanya'da Erasmus+ Gençlik Değişimi" üç ayrı hafta eklendi).
KNOWN_URL_COLUMNS = (
    ("opportunities", "official_url"),
    ("opportunities", "details_url"),
    ("opportunities", "source_url"),
    ("submissions", "url"),
    ("submissions", "source_url"),
    ("submissions", "details_url"),
)


def _is_http_url(value):
    parsed = urlparse(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def candidate_blockers(record, today=None):
    """Agent kuyruğuna bile alınmayacak açık eksikleri döndürür."""
    today = today or date.today()
    blockers = []
    if len(str(record.get("title") or "").strip()) < 8:
        blockers.append("başlık eksik")
    if not any(_is_http_url(record.get(key))
               for key in ("url", "details_url", "source_url")):
        blockers.append("geçerli URL yok")
    if record.get("category_slug") not in VALID_CATEGORIES:
        blockers.append("kategori eksik/geçersiz")
    if not record.get("host_countries"):
        blockers.append("ülke/global bilgisi eksik")
    deadline = str(record.get("deadline_text") or "").strip()
    try:
        parsed_deadline = date.fromisoformat(deadline)
    except ValueError:
        pass                       # serbest metin / boş → ajan sayfadan belirler
    else:
        if parsed_deadline < today:
            blockers.append("son tarih geçmiş")
        elif parsed_deadline > today + timedelta(days=730):
            # Kaynaktaki yazım hatası ("2926") ya da yer tutucu tarih.
            blockers.append("son tarih makul değil")
    if record.get("funding_type") not in VALID_FUNDING:
        blockers.append("finansman eksik/geçersiz")
    if len(str(record.get("eligibility_notes") or "").strip()) < 20:
        blockers.append("uygunluk koşulları eksik")
    return blockers
