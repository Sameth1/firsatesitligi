"""
SALTO-YOUTH Avrupa Eğitim Takvimi → submissions (pending)
=========================================================
SALTO-YOUTH, Avrupa Komisyonu'nun Erasmus+ Gençlik ve Avrupa Dayanışma
Programı kaynak merkezleri ağı. "European Training Calendar" bu programlarla
finanse edilen eğitim kursu, seminer, ortaklık kurma etkinliği ve çalışma
ziyaretlerini topluyor. Her ilanın sayfası çok düzenli:

  • Etkinlik türü ve yer: "Training Course" / "14-18 December 2026 | Brussels, Belgium - FL"
  • Kesin son tarih:       "Application deadline (24h UTC): 29 September 2026"
  • Katılımcı ülkeleri:    "for 25 participants from Erasmus+ Youth Programme countries"
                            (grubun bütün ülkeleri ipucunda: "Austria, …, Türkiye")
  • Çalışma dili, düzenleyen kurum ve masraflar (konaklama/yemek ev sahibi
    ulusal ajansça karşılanır; yol masrafı gönderen ulusal ajansa göre)

Neden bu kaynak: nasilgitmis haftada birkaç ilan çıkarıyor, DAAD veritabanı
doygun (151 bursun 147'si zaten işlenmiş). SALTO'da her an Türkiye'den
katılıma açık ve son başvurusu geçmemiş onlarca etkinlik var (Ekim 2026: 59)
ve her hafta yenileri ekleniyor.

FİLTRELEME (scraper tarafı, ajandan ÖNCE):
  • Arama SALTO'nun kendi "Türkiye'den katılımcı" süzgeciyle yapılır; ek olarak
    sayfadaki katılımcı listesinde Türkiye açıkça geçmeli (ipucu dahil).
  • Yalnız çevrim içi etkinlikler ve Türkiye'de yapılanlar alınmaz — platform
    yurt dışı fırsatları için.
  • Ülke, son tarih, kategori, finansman ve uygunluk metni doldurulamazsa
    discovery_gate kaydı kuyruğa almaz.

Yaş, eğitim kademesi ve dil gibi kullanıcı filtreleri burada TAHMİN EDİLMEZ:
ajan bunları sayfadan birebir alıntıyla belirliyor (validate_submissions).

Kullanım:
  python salto_scraper.py --dry-run --limit 5
  python salto_scraper.py                  # canlı — submissions'a yaz

.env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from application_links import resolve_application_route
from discovery_gate import KNOWN_URL_COLUMNS, candidate_blockers

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BASE = "https://www.salto-youth.net"
BROWSE_URL = BASE + "/tools/european-training-calendar/browse/"
TURKIYE_FILTER = "country-213"          # SALTO'nun "participating countries" kodu
PAGE_SIZE = 10
MAX_PAGES = 15
CRAWL_DELAY = 1.0
HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
DETAIL_RE = re.compile(
    r"/tools/european-training-calendar/training/[a-z0-9-]+\.\d+/")
TURKIYE_RE = re.compile(r"\b(?:T[üu]rkiye|Turkey)\b", re.IGNORECASE)
EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# SALTO'nun yer adları → ISO 3166-1 alfa-2. Takvimde görülen bütün program ve
# komşu ortak ülkeleri. Tanınmayan ülke kaydı atlatır (ülkesiz kayıt kapıdan
# geçemez); tahminle doldurulmaz.
SALTO_COUNTRIES = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "croatia": "HR",
    "cyprus": "CY", "czech republic": "CZ", "czechia": "CZ", "denmark": "DK",
    "estonia": "EE", "finland": "FI", "france": "FR", "germany": "DE",
    "greece": "GR", "hungary": "HU", "iceland": "IS", "ireland": "IE",
    "italy": "IT", "latvia": "LV", "liechtenstein": "LI", "lithuania": "LT",
    "luxembourg": "LU", "malta": "MT", "netherlands": "NL", "norway": "NO",
    "poland": "PL", "portugal": "PT", "republic of north macedonia": "MK",
    "north macedonia": "MK", "romania": "RO", "serbia": "RS",
    "slovak republic": "SK", "slovakia": "SK", "slovenia": "SI", "spain": "ES",
    "sweden": "SE", "switzerland": "CH", "türkiye": "TR", "turkey": "TR",
    "united kingdom": "GB", "albania": "AL", "algeria": "DZ", "armenia": "AM",
    "azerbaijan": "AZ", "belarus": "BY", "bosnia and herzegovina": "BA",
    "egypt": "EG", "georgia": "GE", "israel": "IL", "jordan": "JO",
    "kosovo": "XK", "lebanon": "LB", "libya": "LY", "moldova": "MD",
    "montenegro": "ME", "morocco": "MA", "palestine": "PS",
    "russian federation": "RU", "syria": "SY", "tunisia": "TN", "ukraine": "UA",
}

# ─── Supabase yardımcıları (diğer scraper'larla aynı kalıp) ─────────────────

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def url_exists(url):
    """URL yayında, bekliyor ya da daha önce işlenmiş mi? Statü filtresi yok:
    reddedilen ilan haftalık taramada yeniden eklenmez."""
    for table, col in KNOWN_URL_COLUMNS:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(),
                           params={col: f"eq.{url}", "select": "id", "limit": 1},
                           timeout=15)
        if res.ok and res.json():
            return True
    return False


def insert(record):
    res = requests.post(f"{SUPABASE_URL}/rest/v1/submissions",
                        headers={**sb_headers(), "Prefer": "return=minimal"},
                        json=record, timeout=15)
    ok = res.status_code in (200, 201, 204)
    return ok, ("" if ok else f"HTTP {res.status_code}: {res.text[:160]}")

# ─── Liste sayfaları ─────────────────────────────────────────────────────────

def browse_params(today, offset):
    return {
        "b_participating_countries": TURKIYE_FILTER,
        "b_application_deadline_after_day": today.day,
        "b_application_deadline_after_month": today.month,
        "b_application_deadline_after_year": today.year,
        "b_offset": offset,
        "b_browse": "Browse",
    }


def list_training_urls(today, max_pages=MAX_PAGES):
    """Türkiye'den katılıma açık, son başvurusu geçmemiş ilanların adresleri."""
    seen = []
    for page in range(max_pages):
        res = requests.get(BROWSE_URL, params=browse_params(today, page * PAGE_SIZE),
                           headers=HTTP_HEADERS, timeout=30)
        res.raise_for_status()
        found = [BASE + path for path in DETAIL_RE.findall(res.text)]
        new = [url for url in dict.fromkeys(found) if url not in seen]
        if not new:
            break
        seen.extend(new)
        time.sleep(CRAWL_DELAY)
    return seen

# ─── Detay sayfası ───────────────────────────────────────────────────────────

def _text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _with_tooltips(el):
    """Elemanın metni; ülke grubu ipuçları parantez içinde açılmış hâlde."""
    if el is None:
        return ""
    clone = BeautifulSoup(str(el), "html.parser")
    for img in clone.select("img[title]"):
        img.replace_with(f" ({img['title'].strip()}) ")
    return _text(clone)


def parse_deadline(text):
    m = re.search(r"application deadline\s*(?:\(24h utc\))?\s*:\s*"
                  r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", text, re.IGNORECASE)
    if not m or m.group(2).lower() not in EN_MONTHS:
        return None
    try:
        return date(int(m.group(3)), EN_MONTHS[m.group(2).lower()],
                    int(m.group(1))).isoformat()
    except ValueError:
        return None


def venue_country(venue):
    """'Brussels, Belgium - FL' → 'BE'. Bulunamazsa None."""
    tail = venue.split(",")[-1] if "," in venue else venue
    tail = re.sub(r"\s+-\s+(?:FL|FR|DE)$", "", tail.strip(), flags=re.IGNORECASE)
    tail = re.sub(r"\s*\*.*$", "", tail).strip().casefold()
    return SALTO_COUNTRIES.get(tail)


def _labelled_value(soup, label):
    """'Working language(s):' gibi bir etiketten sonraki ilk paragraf."""
    for p in soup.select("p.microcopy"):
        if _text(p).casefold().startswith(label.casefold()):
            nxt = p.find_next_sibling("p")
            return _text(nxt)
    return ""


def _section_text(soup, heading):
    """Costs bölümündeki 'Accommodation and food' gibi alt başlığın metni."""
    for h in soup.find_all(["h3", "h4"]):
        if _text(h).casefold() == heading.casefold():
            body = h.find_next_sibling("div")
            return _text(body)
    return ""


def parse_training(html, url):
    """Detay sayfası → (record | None, atlama nedeni)."""
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one(".training-data h1") or soup.find("h1"))
    if not title:
        return None, "başlık yok"

    meta = [_text(p) for p in soup.select(".tool-item-category-container p")]
    activity = meta[0] if meta else ""
    when_where = meta[1] if len(meta) > 1 else ""
    venue = when_where.split("|", 1)[1].strip() if "|" in when_where else ""
    if not venue or re.search(r"\bonline\b", f"{activity} {venue}", re.IGNORECASE):
        return None, "çevrim içi etkinlik (yurt dışı değil)"
    country = venue_country(venue)
    if not country:
        return None, f"yer ülkesi tanınmadı: {venue!r}"
    if country == "TR":
        return None, "Türkiye'de yapılıyor (yurt dışı değil)"

    # "Apply now!" kutusu ana sütunun dışında; son tarih sayfanın tamamından.
    deadline = parse_deadline(_text(soup))

    participants_block = ""
    for p in soup.select("p"):
        if _text(p).casefold().startswith("from") and p.find_previous_sibling("p"):
            prev = _text(p.find_previous_sibling("p")).casefold()
            if "participants" in prev:
                participants_block = _with_tooltips(p)
                count = _text(p.find_previous_sibling("p"))
                break
    else:
        count = ""
    if not participants_block or not TURKIYE_RE.search(participants_block):
        return None, "katılımcı listesinde Türkiye yok"

    groups = re.sub(r"\s*\([^)]*\)", "", participants_block)      # ipuçsuz kısa liste
    recommended = _labelled_value(soup, "and recommended for")
    language = _labelled_value(soup, "Working language")
    profile = _text(soup.find(string=re.compile(r"Participant profile", re.I)) and
                    soup.find(string=re.compile(r"Participant profile", re.I)).find_parent()
                    .find_next_sibling())

    fee = _section_text(soup, "Participation fee")
    lodging = _section_text(soup, "Accommodation and food")
    travel = _section_text(soup, "Travel reimbursement")
    covered = re.search(r"cover", lodging, re.IGNORECASE)
    no_fee = re.search(r"\bno participation fee\b|free of charge", fee, re.IGNORECASE)
    reimbursed = re.search(r"\bwill be (?:fully )?reimbursed\b|\bcovers? (?:all )?travel",
                           travel, re.IGNORECASE)
    funding_type = "full" if (covered and no_fee and reimbursed) else "partial"

    eligibility = " ".join(filter(None, (
        f"{activity}: {count} {groups}".strip() + ".",
        f"Recommended for: {recommended}." if recommended else "",
        f"Working language(s): {language}." if language else "",
        profile[:600],
    )))
    summary = _text(soup.select_one(".training-summary"))
    description = _text(soup.select_one(".training-description"))

    route = resolve_application_route(url, source_html=html, max_hops=2)
    record = {
        "title": title,
        **route.submission_fields(),
        "details_url": url,
        "source_url": url,
        "category_slug": "youth_project",
        "deadline_text": deadline,
        "host_countries": [country],
        "age_min": None,
        "age_max": None,
        "study_level": None,
        "language_requirement": None,
        "eligibility_notes": eligibility[:1500],
        "description": (f"{summary} {description}".strip())[:1500] or None,
        "funding_type": funding_type,
        "funding_notes": " ".join(filter(None, (
            f"Katılım ücreti: {fee}" if fee else "",
            f"Konaklama ve yemek: {lodging}" if lodging else "",
            f"Yol masrafı: {travel}" if travel else "",
        )))[:1500] or None,
        "submitter_nickname": "salto-bot",
        "status": "pending",
        "submission_origin": "agent",
        "review_stage": "agent_queue",
    }
    return record, ""

# ─── Çalıştırma ──────────────────────────────────────────────────────────────

def run(dry_run, limit, today=None):
    today = today or date.today()
    mode = "DRY-RUN — DB'ye yazılmaz" if dry_run else "CANLI — submissions'a yazılır"
    print(f"🚀 SALTO-YOUTH scraper — {mode}")
    if not dry_run and not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY yok (.env). Canlı mod için gerekli.")
        return 1

    try:
        urls = list_training_urls(today)
    except requests.RequestException as exc:
        # Kaynak geçici olarak kapalı: haftalık keşfin diğer kaynaklarını düşürme.
        print(f"::warning title=SALTO erişilemedi::{exc}")
        return 0
    print(f"  {len(urls)} ilan (Türkiye'den katılıma açık, son başvurusu geçmemiş)\n" + "─" * 60)

    stats = {"processed": 0, "previewed": 0, "added": 0, "skipped": 0,
             "out_of_scope": 0, "errors": 0}
    for url in urls:
        if limit and stats["processed"] >= limit:
            break
        stats["processed"] += 1
        if not dry_run and url_exists(url):
            stats["skipped"] += 1
            print(f"  ⏭ kopya: {url}")
            continue
        try:
            res = requests.get(url, headers=HTTP_HEADERS, timeout=30)
            res.raise_for_status()
        except requests.RequestException as exc:
            stats["errors"] += 1
            print(f"  ❌ çekilemedi: {url} — {exc}")
            continue
        record, reason = parse_training(res.text, url)
        time.sleep(CRAWL_DELAY)
        if record is None:
            stats["out_of_scope"] += 1
            print(f"  ↷ kapsam dışı: {url.rsplit('/', 2)[-2][:60]} — {reason}")
            continue
        blockers = candidate_blockers(record, today=today)
        if blockers:
            stats["errors"] += 1
            print(f"  🚫 kalite kapısı: {record['title'][:55]} — {'; '.join(blockers)}")
            continue
        if dry_run:
            stats["previewed"] += 1
            print(f"  🧪 {record['title'][:60]}  [{record['host_countries'][0]}, "
                  f"son başvuru {record['deadline_text']}, {record['funding_type']}]")
            print(json.dumps(record, ensure_ascii=False, indent=2))
            continue
        ok, detay = insert(record)
        if ok:
            stats["added"] += 1
            print(f"  ✅ pending: {record['title'][:55]}")
        else:
            stats["errors"] += 1
            print(f"  ❌ insert hatası: {record['title'][:45]} — {detay}")

    print("\n" + "─" * 60)
    print(f"İşlenen: {stats['processed']} · Kapsam dışı: {stats['out_of_scope']}")
    if dry_run:
        print(f"Önizlenen: {stats['previewed']}")
    else:
        print(f"Eklendi: {stats['added']} pending · Atlandı(kopya): {stats['skipped']}")
    print(f"Hata/kapı: {stats['errors']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="SALTO-YOUTH Avrupa Eğitim Takvimi scraper")
    ap.add_argument("--dry-run", action="store_true", help="DB'ye yazma, kayıtları göster")
    ap.add_argument("--limit", type=int, help="en fazla bu kadar ilan işle")
    args = ap.parse_args()
    sys.exit(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
