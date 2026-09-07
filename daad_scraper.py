"""
DAAD Burs Veritabanı Scraper (lokal, tek-seferlik)
==================================================
DAAD scholarship database'i (164 burs) Supabase 'submissions' tablosuna pending
yazar. youthop_scraper kalıbında; farkı: DAAD liste/detayı JS ile yüklediği için
sayfa crawl etmek yerine site'ın STATİK VERİ DOSYALARINI kullanır:

  • scholarships.js  → var scholarships = TAFFY([... 164 nesne ...])
  • deadlines.js     → var listDeadlines = TAFFY([{id:<sapProgid>, general:{en}, ...}])

Detay URL: .../21148-scholarship-database/?detail=<sapProgid>
Her detay sayfası reach.extract_fields ile parse edilir (funding/eligibility/
study_level/description). deadline detay sayfasında olmadığından deadlines.js'ten
alınır (serbest metin; çoğu DAAD programında deadline programa/üniversiteye göre
değişken).

NOT: DAAD, datacenter IP'lerini (droplet) bloklar → bu spider LOKAL çalıştırılmalı.

Kullanım:
  python daad_scraper.py --dry-run --limit 5
  python daad_scraper.py                  # canlı — submissions'a yaz

.env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import os
import re
import sys
import html
import json
import time
import argparse

import requests
from dotenv import load_dotenv

import agent_reach_url_scraper as reach

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BASE = "https://www2.daad.de"
DATA = BASE + "/bundles/daadstipendiendatenbanklsh/data/a/js/"
SCHOLARSHIPS_JS = DATA + "scholarships.js"
DEADLINES_JS = DATA + "deadlines.js"
DETAIL_BASE = BASE + "/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail="
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CRAWL_DELAY = 1.0
INTENTION_INTERNSHIP = 4   # intentions.js: 4 = Internship

# ─── Supabase yardımcıları (youthop ile aynı kalıp) ───────────────────────────

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def url_exists(url):
    """URL zaten yayında (opportunities.official_url) ya da pending/işlenmiş
    (submissions.url) mı? STATUS filtresi yok → tekrar scrape/validate etmez."""
    for table, col in (("opportunities", "official_url"), ("submissions", "url")):
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(),
                           params={col: f"eq.{url}", "select": "id", "limit": 1}, timeout=15)
        if res.ok and res.json():
            return True
    return False


def insert(record):
    res = requests.post(f"{SUPABASE_URL}/rest/v1/submissions",
                        headers={**sb_headers(), "Prefer": "return=minimal"},
                        json=record, timeout=15)
    ok = res.status_code in (200, 201, 204)
    return ok, ("" if ok else f"HTTP {res.status_code}: {res.text[:160]}")

# ─── DAAD veri dosyaları ──────────────────────────────────────────────────────

def _parse_taffy(js_text):
    """`var X = TAFFY([...]);` sarmalını atıp JSON diziyi döndürür."""
    start = js_text.index("TAFFY(") + len("TAFFY(")
    end = js_text.rindex(")")
    return json.loads(js_text[start:end])


def fetch_taffy(url):
    r = requests.get(url, headers=HTTP_HEADERS, timeout=30)
    r.raise_for_status()
    return _parse_taffy(r.text)


def build_deadline_map():
    """deadlines.js → {sapProgid: deadline_text}. general.en boş olanlar atlanır.
    HTML etiketleri temizlenir, kısaltılır (serbest metin; tarih garantisi yok)."""
    out = {}
    for d in fetch_taffy(DEADLINES_JS):
        gen = ((d.get("general") or {}).get("en") or "").strip()
        if not gen:
            continue
        txt = html.unescape(re.sub(r"<[^>]+>", " ", gen))
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            out[d["id"]] = txt[:300]
    return out


def _intention_ids(sch):
    """scholarship.intentions'tan id listesi (int ya da {'id':..} olabilir)."""
    ids = []
    for it in (sch.get("intentions") or []):
        if isinstance(it, int):
            ids.append(it)
        elif isinstance(it, dict) and "id" in it:
            ids.append(it["id"])
    return ids

# ─── Kayıt oluşturma ──────────────────────────────────────────────────────────

# DAAD JS-liste UI talimatlarının eligibility metnine sızan kalıpları. Bunlar
# fırsata özgü değil, sitenin "sol sütundan ülke/durum seç" arayüz yönergesi.
_DAAD_NOISE_RES = [
    re.compile(r"(?:to ensure that only[^.]*?,\s*)?please select your status and "
               r"your country[^.]*?\.", re.I),
    re.compile(r'^\s*[“"]?application requirements[”"]?\)\.\s*', re.I),
]


def _clean_eligibility(text):
    """DAAD UI boilerplate'ini eligibility_notes'tan temizler."""
    if not text:
        return text
    for rx in _DAAD_NOISE_RES:
        text = rx.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def build_record(sch, base, detail_url, category, deadline_text):
    """JS metadata (sch) + detay sayfası çıkarımı (base) → submission dict."""
    return {
        "title":                (sch.get("nameEn") or sch.get("programmnameEn") or "").strip()
                                or base.get("title"),
        "url":                  detail_url,
        "source_url":           detail_url,
        "category_slug":        category,
        "deadline_text":        deadline_text,    # deadlines.js'ten (serbest metin) ya da None
        "host_countries":       ["DE"],           # DAAD → Almanya
        "age_min":              base.get("age_min"),
        "age_max":              base.get("age_max"),
        "study_level":          base.get("study_level"),
        "language_requirement": "İngilizce / Almanca (programa göre)",
        "eligibility_notes":    _clean_eligibility(base.get("eligibility_notes")),
        "description":          base.get("description"),
        "funding_type":         base.get("funding_type") or "stipend",  # DAAD = aylık ödenek
        "funding_notes":        f"DAAD burs veritabanından çekildi — kaynak: {detail_url}",
        "submitter_nickname":   "daad-bot",
        "status":               "pending",
        "submission_origin":    "agent",
        "review_stage":         "agent_queue",
    }


def process_scholarship(sch, deadline_map, dry_run, stats):
    stats["processed"] += 1
    sapprogid = sch.get("sapProgid")
    if not sapprogid:
        stats["errors"] += 1
        return
    detail_url = DETAIL_BASE + str(sapprogid)
    category = "internship" if INTENTION_INTERNSHIP in _intention_ids(sch) else "scholarship"
    deadline_text = deadline_map.get(sapprogid)

    # Kopya elemesini FETCH'ten önce yap (dry_run'da DB'ye bakma).
    if not dry_run and url_exists(detail_url):
        stats["skipped"] += 1
        print(f"  ⏭ kopya: {detail_url}")
        return

    page = reach.fetch_page(detail_url)
    if page is None:
        stats["errors"] += 1
        print(f"  ❌ çekilemedi: {detail_url}")
        return
    base = reach.extract_fields(page, detail_url, category) or {}
    record = build_record(sch, base, detail_url, category, deadline_text)

    if dry_run:
        stats["previewed"] += 1
        print(f"  🧪 [{category}] {record['title'][:55]}")
        print(f"     funding={record['funding_type']}  study_level={record['study_level']}  "
              f"deadline={(deadline_text or 'None')[:40]!r}")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    ok, detay = insert(record)
    if ok:
        stats["added"] += 1
        print(f"  ✅ pending: {record['title'][:55]}")
    else:
        stats["errors"] += 1
        print(f"  ❌ insert hatası: {record['title'][:45]} — {detay}")


def run(dry_run, limit):
    mode = "DRY-RUN — DB'ye yazılmaz" if dry_run else "CANLI — submissions'a yazılır"
    print(f"🚀 DAAD scraper — {mode}")
    if not dry_run and not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY yok (.env). Canlı mod için gerekli.")
        return

    print("scholarships.js + deadlines.js çekiliyor...")
    scholarships = fetch_taffy(SCHOLARSHIPS_JS)
    deadline_map = build_deadline_map()
    print(f"  {len(scholarships)} burs · {len(deadline_map)} deadline kaydı (dolu)\n" + "─" * 60)

    stats = {"processed": 0, "previewed": 0, "added": 0, "skipped": 0, "errors": 0}
    for sch in scholarships:
        if limit and stats["processed"] >= limit:
            break
        process_scholarship(sch, deadline_map, dry_run, stats)
        time.sleep(CRAWL_DELAY)

    print("\n" + "─" * 60)
    print(f"İşlenen: {stats['processed']}")
    if dry_run:
        print(f"Önizlenen: {stats['previewed']}")
    else:
        print(f"Eklendi: {stats['added']} pending · Atlandı(kopya): {stats['skipped']}")
    print(f"Hata/atlanan: {stats['errors']}")


def main():
    ap = argparse.ArgumentParser(description="DAAD burs veritabanı scraper")
    ap.add_argument("--dry-run", action="store_true", help="DB'ye yazma, kayıtları göster")
    ap.add_argument("--limit", type=int, help="en fazla bu kadar burs işle")
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
