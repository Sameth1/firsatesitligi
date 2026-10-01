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

NOT: DAAD'ın güvenlik duvarı datacenter IP'lerini ZAMAN ZAMAN blokluyor.
GitHub runner'ında 14 ve 21 Eylül koşuları düz `requests` ile 403 aldı, 28 Eylül
aynı kodla geçti. Bu yüzden veri dosyaları sırayla düz istek → Scrapling
Fetcher (gerçek tarayıcı TLS parmak izi) → StealthyFetcher (gizli tarayıcı)
ile deneniyor; hepsi başarısızsa kaynak "erişilemedi" uyarısıyla atlanıyor,
haftalık keşfin geri kalanı çalışmaya devam ediyor.

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
from scrapling.fetchers import Fetcher, StealthyFetcher

import agent_reach_url_scraper as reach
from discovery_gate import KNOWN_URL_COLUMNS, candidate_blockers

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
HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"),
    "Accept": "application/javascript, text/javascript, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Referer": BASE + "/deutschland/stipendium/datenbank/en/21148-scholarship-database/",
}
DATA_RETRY_DELAYS = (0, 5)          # düz istek: hemen, sonra 5 sn sonra
CRAWL_DELAY = 1.0
INTENTION_INTERNSHIP = 4   # intentions.js: 4 = Internship

# ─── Supabase yardımcıları (youthop ile aynı kalıp) ───────────────────────────

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def url_exists(url):
    """URL zaten yayında (opportunities.official_url) ya da pending/işlenmiş
    (submissions.url) mı? STATUS filtresi yok → tekrar scrape/validate etmez."""
    for table, col in KNOWN_URL_COLUMNS:
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


class DaadUnavailable(RuntimeError):
    """Veri dosyası hiçbir yolla alınamadı — kaynak arızası, kod hatası değil."""


def _fetch_data_text(url):
    """TAFFY veri dosyasının ham metnini getirir; engellenirse sıradakine düşer.

    Her deneme yalnız içinde `TAFFY(` geçen bir yanıtı kabul eder: güvenlik
    duvarı 200 ile bir HTML engel sayfası da döndürebiliyor."""
    attempts = []
    for delay in DATA_RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=30)
            if r.ok and "TAFFY(" in r.text:
                return r.text
            attempts.append(f"requests HTTP {r.status_code}")
        except requests.RequestException as exc:
            attempts.append(f"requests {type(exc).__name__}")

    try:
        page = Fetcher.get(url, timeout=30, stealthy_headers=True)
        text = page.body.decode(page.encoding or "utf-8", errors="replace")
        if page.status == 200 and "TAFFY(" in text:
            return text
        attempts.append(f"Fetcher HTTP {page.status}")
    except Exception as exc:                      # scrapling çok çeşitli hata atar
        attempts.append(f"Fetcher {type(exc).__name__}")

    try:
        # Tarayıcı bir .js adresini <pre> içinde düz metin olarak gösterir.
        page = StealthyFetcher.fetch(url, headless=True, timeout=60_000)
        text = page.css("pre::text").get() or ""
        if page.status == 200 and "TAFFY(" in text:
            return text
        attempts.append(f"StealthyFetcher HTTP {page.status}")
    except Exception as exc:
        attempts.append(f"StealthyFetcher {type(exc).__name__}")

    raise DaadUnavailable(f"{url.rsplit('/', 1)[-1]} alınamadı: " + ", ".join(attempts))


def fetch_taffy(url):
    return _parse_taffy(_fetch_data_text(url))


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
    # Metin 600 karakterde kesilince cümle noktaya ulaşmıyor ve yukarıdaki
    # kalıp tutmuyordu ("… please s…"); yarım kalan yönergeyi sonuna kadar at.
    re.compile(r"\s*to ensure that only scholarship programmes.*$", re.I | re.S),
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
        "url":                  base.get("url") or detail_url,
        "details_url":          base.get("details_url") or detail_url,
        "source_url":           detail_url,
        "application_route_status": base.get("application_route_status", "unverified"),
        "application_method":   base.get("application_method"),
        "application_url_verified_at": base.get("application_url_verified_at"),
        "application_url_check_status": base.get("application_url_check_status"),
        "application_url_final": base.get("application_url_final"),
        "application_url_evidence": base.get("application_url_evidence"),
        "category_slug":        category,
        "deadline_text":        deadline_text,    # deadlines.js'ten (serbest metin) ya da None
        "host_countries":       ["DE"],           # DAAD → Almanya
        "age_min":              base.get("age_min"),
        "age_max":              base.get("age_max"),
        "study_level":          base.get("study_level"),
        # Dil şartı tahmin edilmez: ajan sayfadan kanıtla belirler. Eskiden
        # buraya sabit "İngilizce / Almanca (programa göre)" yazılıyordu; bu
        # hem yanlış olabiliyordu hem de modele kaydedilmiş bir değer gibi
        # görünüp kararını etkiliyordu.
        "language_requirement": None,
        "eligibility_notes":    _clean_eligibility(base.get("eligibility_notes")),
        "description":          base.get("description"),
        "funding_type":         base.get("funding_type") or "stipend",  # DAAD = aylık ödenek
        "funding_notes":        f"DAAD burs veritabanından çekildi — kaynak: {detail_url}",
        "submitter_nickname":   "daad-bot",
        "status":               "pending",
        "submission_origin":    "agent",
        "review_stage":         "agent_queue",
        "admin_note":           (None if base.get("application_url_verified_at") else
                                  "[uyarı] doğrulanmış doğrudan başvuru adımı bulunamadı"),
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
    blockers = candidate_blockers(record)
    if blockers:
        stats["errors"] += 1
        print(f"  🚫 kalite kapısı: {record['title'][:55]} — {'; '.join(blockers)}")
        return

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
    try:
        scholarships = fetch_taffy(SCHOLARSHIPS_JS)
        deadline_map = build_deadline_map()
    except DaadUnavailable as exc:
        # Kaynak geçici olarak kapalı: bu haftanın diğer kaynaklarını düşürme.
        # GitHub Actions ::warning:: satırı koşu özetinde görünür kalır.
        print(f"::warning title=DAAD erişilemedi::{exc}")
        return
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
