"""Yeni bulunan kayıtlar için LLM öncesi ucuz ve kapalı kalite kapısı."""

from datetime import date
from urllib.parse import urlparse


VALID_CATEGORIES = {
    "scholarship", "volunteering", "youth_project",
    "internship", "summer_school", "exchange",
}
VALID_FUNDING = {"full", "partial", "free", "stipend"}


def candidate_blockers(record, today=None):
    """Agent kuyruğuna bile alınmayacak açık eksikleri döndürür."""
    today = today or date.today()
    blockers = []
    if len(str(record.get("title") or "").strip()) < 8:
        blockers.append("başlık eksik")
    parsed_url = urlparse(str(record.get("url") or ""))
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        blockers.append("geçerli başvuru URL'i yok")
    if record.get("application_route_status") != "verified":
        blockers.append("doğrudan başvuru adımı doğrulanmadı")
    if not record.get("application_url_verified_at") or not record.get("application_url_final"):
        blockers.append("başvuru URL'i teknik kanıtı eksik")
    if record.get("category_slug") not in VALID_CATEGORIES:
        blockers.append("kategori eksik/geçersiz")
    if not record.get("host_countries"):
        blockers.append("ülke/global bilgisi eksik")
    deadline = str(record.get("deadline_text") or "").strip()
    try:
        parsed_deadline = date.fromisoformat(deadline)
    except ValueError:
        blockers.append("tam ISO son tarih yok")
    else:
        if parsed_deadline < today:
            blockers.append("son tarih geçmiş")
    if record.get("funding_type") not in VALID_FUNDING:
        blockers.append("finansman eksik/geçersiz")
    if len(str(record.get("eligibility_notes") or "").strip()) < 20:
        blockers.append("uygunluk koşulları eksik")
    return blockers

