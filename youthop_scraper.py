"""
youthop.com Scraper
===================
youthop.com (Youth Opportunities) kategori liste sayfalarını gezip her tekil
fırsat detay sayfasını Supabase 'submissions' tablosuna status='pending' olarak
yazar. nasilgitmis_scraper.py ile aynı kalıpta; farkı:

  • Sayfa çekme ve alan çıkarımı agent_reach_url_scraper (reach) üzerinden yapılır
    — youthop detay sayfaları JSON-LD'li ve extract_fields-dostu (title/deadline/
    description hazır). Kopyalama yok.
  • Sayfalama klasik WordPress path tabanlı: /<kategori>/page/N (query ?page= YOK).
  • Liste sayfaları çapraz-kategorili olduğu için kategori, liste URL'sinden DEĞİL
    her detay URL'sinin kendi path prefix'inden türetilir (CATEGORY_MAP).

Doğrudan 'opportunities'e YAZMAZ — kayıtlar pending eklenir; validate_submissions.py
incelemesinden geçip onaylanınca agent_approve_submission RPC'si taşır.

Kullanım:
  pip install "scrapling[fetchers]" requests python-dotenv && scrapling install
  python youthop_scraper.py                       # canlı — submissions'a yaz
  python youthop_scraper.py --dry-run --limit 5   # DB'ye yazma, ilk 5 detayı göster
  python youthop_scraper.py --max-pages 3         # kategori başına en fazla 3 sayfa

.env:
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=eyJ...   # yalnızca canlı modda gerekir
"""

import os
import sys
import time
import json
import argparse
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

# Çıkarım + fetch mantığını reach'ten yeniden kullan (kopyalama yok). ng yalnızca
# slug→funding_type fallback'i için. İkisi de import sırasında load_dotenv +
# stdout reconfigure çalıştırır; yan etkisi yok.
import agent_reach_url_scraper as reach
import nasilgitmis_scraper as ng

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# ─── Ayarlar ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BASE = "https://www.youthop.com"

# Gezilecek kategori liste sayfaları (sayfa 1). Pagination /page/N ile takip edilir.
START_URLS = [
    f"{BASE}/fellowships",
    f"{BASE}/scholarships/undergraduate",
    f"{BASE}/scholarships/post-graduate",
    f"{BASE}/competitions",
    f"{BASE}/exchange-programs",
    f"{BASE}/voluntary",
    f"{BASE}/internships",
]

# Detay URL'sinin İLK path segmenti → reach.VALID_CATEGORIES slug'ı (ya da None).
# Liste sayfaları çapraz-kategorili olduğu için kategori daima DETAY url'sinden
# türetilir. VALID'de karşılığı olmayanlar (competitions/conferences/workshops/
# miscellaneous) None bırakılır: null, yanlış slug'tan güvenlidir (validate'te
# kategori-uyuşmazlığı reddine yol açmaz; onayda RPC kategorisiz yayınlar).
CATEGORY_MAP = {
    "scholarships":      "scholarship",
    "fellowships":       "scholarship",   # fonlu akademik ödül ≈ burs
    "exchange-programs": "exchange",
    "internships":       "internship",
    "voluntary":         "volunteering",
    "competitions":      None,
    "conferences":       None,
    "workshops":         None,
    "miscellaneous":     None,
}

CRAWL_DELAY = 1.0   # detaylar arası bekleme — siteye nazik ol

# ─── Supabase yardımcıları (nasilgitmis ile aynı kalıp) ───────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def url_exists(url):
    """URL zaten yayında (opportunities.official_url) ya da pending (submissions.url)
    mı? Birinde varsa kopya — tekrar ekleme."""
    for table, col in (("opportunities", "official_url"), ("submissions", "url")):
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=sb_headers(),
            params={col: f"eq.{url}", "select": "id", "limit": 1},
            timeout=15,
        )
        if res.ok and res.json():
            return True
    return False


def insert(record):
    """Submission'ı 'submissions' tablosuna pending olarak yazar.
    (ok, detay) döndürür."""
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/submissions",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        json=record,
        timeout=15,
    )
    ok = res.status_code in (200, 201, 204)
    return ok, ("" if ok else f"HTTP {res.status_code}: {res.text[:160]}")

# ─── URL / kategori yardımcıları ──────────────────────────────────────────────

def category_from_url(detail_url):
    """Detay URL path prefix'inden category_slug türet (CATEGORY_MAP). Bilinmeyen
    prefix → None (null kategori; güvenli)."""
    parts = [p for p in urlsplit(detail_url).path.split("/") if p]
    return CATEGORY_MAP.get(parts[0]) if parts else None


def canonical_detail(href):
    """post-header linkini kanonik detay URL'sine çevir: göreli→mutlak, ?ref= gibi
    query'leri at, trailing slash sil. Detay değilse (tek segment = liste kökü,
    /page/ = sayfalama, youthop dışı) None döndür."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("/"):
        href = BASE + href
    sp = urlsplit(href)
    if "youthop.com" not in sp.netloc:
        return None
    parts = [p for p in sp.path.split("/") if p]
    if len(parts) < 2 or "page" in parts:   # /fellowships (liste) ya da /.../page/N
        return None
    return f"{sp.scheme}://{sp.netloc}/{'/'.join(parts)}"   # query atılmış, slash'sız


def list_page_detail_links(list_page):
    """Liste sayfasından detay linklerini (div.post-header a[href]) kanonikleştir +
    sırayı koruyarak tekleştir."""
    out, seen = [], set()
    for href in list_page.css("div.post-header a::attr(href)").getall():
        cu = canonical_detail(href)
        if cu and cu not in seen:
            seen.add(cu)
            out.append(cu)
    return out


def page_url(start_url, n):
    """Kategori sayfası N'in URL'si. n=1 → start; aksi halde /page/N (WordPress)."""
    base = start_url.rstrip("/")
    return base if n == 1 else f"{base}/page/{n}"


def has_next_page(list_page, next_n):
    """Sayfalama navigasyonunda /page/{next_n} hedefli bir 'page-numbers' linki var mı?
    WordPress next linki yoksa son sayfadayız demektir."""
    for href in list_page.css(".pagination a::attr(href), a.page-numbers::attr(href)").getall():
        if f"/page/{next_n}" in (href or ""):
            return True
    return False

# ─── Detay parse ──────────────────────────────────────────────────────────────

def build_record(base, detail_url, category_slug):
    """reach.extract_fields çıktısını (base) nasilgitmis submission şekline uyarlar.
    extract_fields title/deadline/country/funding/eligibility/description'ı zaten
    çıkardı; burada youthop'a özgü alanları (kaynak notu, dil, status) ekliyoruz."""
    funding = base.get("funding_type") or (
        ng.slug_to_funding_type(category_slug) if category_slug else None)
    return {
        "title":                base["title"],
        "url":                  detail_url,          # kanonik (query'siz)
        "category_slug":        category_slug,        # None olabilir (güvenli)
        "deadline_text":        base.get("deadline_text"),
        "host_countries":       base.get("host_countries") or [],
        # youthop İngilizce ve yaş aralığını TR "yaş" kalıbıyla vermez → varsayılan.
        "age_min":              None,
        "age_max":              30,
        "language_requirement": "İngilizce",
        "eligibility_notes":    base.get("eligibility_notes"),
        "description":          base.get("description"),
        "funding_type":         funding,
        "funding_notes":        f"youthop.com'dan çekildi — kaynak: {detail_url}",
        "submitter_nickname":   "youthop-bot",
        "status":               "pending",
    }


def process_detail(detail_url, dry_run, stats):
    """Tek detay sayfasını çek → extract_fields → kayıt. dry_run'da DB'ye yazmaz,
    JSON'u basar. stats['processed'] her FETCH edilen detayda artar (limit bunu sayar)."""
    stats["processed"] += 1
    category_slug = category_from_url(detail_url)
    page = reach.fetch_page(detail_url)
    if page is None:
        stats["errors"] += 1
        print(f"  ❌ çekilemedi: {detail_url}")
        return

    base = reach.extract_fields(page, detail_url, category_slug)
    if base is None:
        stats["errors"] += 1
        print(f"  ❌ başlık çıkmadı: {detail_url}")
        return

    if reach.is_soft_404(detail_url, base["title"]):
        stats["errors"] += 1
        print(f"  🚫 soft-404: {base['title']}")
        return

    record = build_record(base, detail_url, category_slug)

    if dry_run:
        stats["previewed"] += 1
        print(f"  🧪 [{category_slug or 'null'}] {record['title'][:60]}  "
              f"deadline={record['deadline_text']}  funding={record['funding_type']}")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return

    if url_exists(detail_url):
        stats["skipped"] += 1
        print(f"  ⏭ kopya: {record['title'][:60]}")
        return

    ok, detay = insert(record)
    if ok:
        stats["added"] += 1
        print(f"  ✅ pending: {record['title'][:60]}")
    else:
        stats["errors"] += 1
        print(f"  ❌ insert hatası: {record['title'][:55]} — {detay}")

# ─── Crawl ──────────────────────────────────────────────────────────────────

def crawl_category(start_url, max_pages, seen, stats, limit, dry_run):
    """Bir kategoriyi /page/N ile, next link kalmayana ya da max_pages'e dek tara."""
    print(f"\n📂 {start_url}")
    for n in range(1, max_pages + 1):
        if limit and stats["processed"] >= limit:
            return
        lu = page_url(start_url, n)
        page = reach.fetch_page(lu)
        if page is None:
            print(f"  sayfa {n} çekilemedi, kategori bitti")
            return
        links = list_page_detail_links(page)
        print(f"  sayfa {n}: {len(links)} detay link")

        for d in links:
            if limit and stats["processed"] >= limit:
                return
            if d in seen:
                continue
            seen.add(d)
            process_detail(d, dry_run, stats)
            time.sleep(CRAWL_DELAY)

        if not has_next_page(page, n + 1):
            return   # son sayfa


def run(dry_run, limit, max_pages):
    mode = "DRY-RUN — DB'ye yazılmayacak" if dry_run else "CANLI — submissions'a yazılacak"
    print(f"🚀 youthop.com scraper — {mode}")
    if not dry_run and not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY yok (.env). Canlı mod için gerekli.")
        return

    seen = set()
    stats = {"processed": 0, "previewed": 0, "added": 0, "skipped": 0, "errors": 0}

    for start in START_URLS:
        if limit and stats["processed"] >= limit:
            break
        crawl_category(start, max_pages, seen, stats, limit, dry_run)

    print("\n" + "─" * 50)
    print(f"İşlenen detay : {stats['processed']}")
    if dry_run:
        print(f"Önizlenen     : {stats['previewed']}")
    else:
        print(f"Eklendi       : {stats['added']} pending")
        print(f"Atlandı (kopya): {stats['skipped']}")
    print(f"Hata/atlanan  : {stats['errors']}")
    print("─" * 50)


def main():
    ap = argparse.ArgumentParser(description="youthop.com scraper")
    ap.add_argument("--dry-run", action="store_true", help="DB'ye yazma, kayıtları göster")
    ap.add_argument("--limit", type=int, help="en fazla bu kadar detay sayfası işle")
    ap.add_argument("--max-pages", type=int, default=3,
                    help="kategori başına en fazla sayfa (varsayılan 3)")
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, max_pages=args.max_pages)


if __name__ == "__main__":
    main()
