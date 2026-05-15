"""
nasilgitmis.com Scraper
========================
nasilgitmis.com'dan Erasmus+, ESC, Burs ve Staj fırsatlarını
çekip Supabase opportunities tablosuna yazar.

Kullanım:
  pip install requests python-dotenv beautifulsoup4
  python nasilgitmis_scraper.py

.env dosyasında olması gerekenler:
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_SERVICE_KEY=eyJ...
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ─── Ayarlar ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Kategori slug → DB category_id eşlemesi
# Supabase'den: SELECT slug, id FROM categories;
CATEGORY_IDS = {
    "volunteering":  "dfe93634-98a2-48d7-b486-73b8c9631bcc",
    "scholarship":   "c492a2d8-04fe-42f4-bbe7-a1dfb703d1df",
    "internship":    "2db63ccc-3cf2-4659-90f6-f8b799559cfe",
    "youth_project": "89b79136-7e5d-4602-837c-c8af353e6b9d",
    "exchange":      "a002a2b8-d3e0-4778-848f-a73ed0bc3571",
    "summer_school": "00bf6fed-dfe6-40a3-b63a-795fa74c6741",
}

# nasilgitmis.com kategori URL → DB slug eşlemesi
SITE_CATEGORIES = {
    "https://nasilgitmis.com/category/esc/":          "volunteering",
    "https://nasilgitmis.com/category/erasmus/":      "youth_project",
    "https://nasilgitmis.com/category/egitimveburs/": "scholarship",
    "https://nasilgitmis.com/category/staj/":         "internship",
}

# Ülke adı → ISO kodu
COUNTRY_MAP = {
    "portekiz": "PT", "portugal": "PT",
    "italya": "IT", "italy": "IT",
    "almanya": "DE", "germany": "DE",
    "fransa": "FR", "france": "FR",
    "ispanya": "ES", "spain": "ES",
    "hollanda": "NL", "netherlands": "NL",
    "polonya": "PL", "poland": "PL",
    "yunanistan": "GR", "greece": "GR",
    "macaristan": "HU", "hungary": "HU",
    "çekya": "CZ", "czech": "CZ",
    "slovakya": "SK", "slovakia": "SK",
    "romanya": "RO", "romania": "RO",
    "bulgaristan": "BG", "bulgaria": "BG",
    "hırvatistan": "HR", "croatia": "HR",
    "litvanya": "LT", "lithuania": "LT",
    "letonya": "LV", "latvia": "LV",
    "estonya": "EE", "estonia": "EE",
    "belçika": "BE", "belgium": "BE",
    "avusturya": "AT", "austria": "AT",
    "isveç": "SE", "sweden": "SE",
    "finlandiya": "FI", "finland": "FI",
    "danimarka": "DK", "denmark": "DK",
    "norveç": "NO", "norway": "NO",
    "malta": "MT",
    "kıbrıs": "CY", "cyprus": "CY",
    "slovenya": "SI", "slovenia": "SI",
    "bosna": "BA", "bosnia": "BA",
    "sırbistan": "RS", "serbia": "RS",
    "japonya": "JP", "japan": "JP",
    "güney kore": "KR", "korea": "KR",
    "türkiye": "TR", "turkey": "TR",
    "ingiltere": "GB", "uk": "GB",
    "abd": "US", "usa": "US",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── Supabase yardımcıları ────────────────────────────────────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def url_exists(url):
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=sb_headers(),
        params={"official_url": f"eq.{url}", "select": "id", "limit": 1},
    )
    return len(res.json()) > 0

def insert(record):
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=sb_headers(),
        json=record,
    )
    return res.status_code in (200, 201)

# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

def extract_country(text):
    """Metinden ülke kodu çıkar."""
    text_lower = text.lower()
    for name, code in COUNTRY_MAP.items():
        if name in text_lower:
            return code
    return "*"

def extract_deadline(text):
    """
    Metinden son başvuru tarihini çıkar.
    Örnek: '27 Nisan 2026', '15.05.2026', '2026-04-27'
    """
    # ISO format: 2026-04-27
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)

    # Türkçe ay isimleri
    ay_map = {
        "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
        "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
        "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12",
    }
    m = re.search(
        r"(\d{1,2})\s+(" + "|".join(ay_map.keys()) + r")\s+(\d{4})",
        text.lower()
    )
    if m:
        gun, ay, yil = m.group(1), m.group(2), m.group(3)
        return f"{yil}-{ay_map[ay]}-{gun.zfill(2)}"

    # Noktalı format: 27.04.2026
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    return None

def extract_age_range(text):
    """18-30 yaş gibi aralıkları çıkar."""
    m = re.search(r"(\d{2})\s*[-–]\s*(\d{2})\s*yaş", text.lower())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def slug_to_funding_type(category_slug):
    mapping = {
        "volunteering":  "free",
        "youth_project": "free",
        "scholarship":   "full",
        "internship":    "stipend",
        "exchange":      "free",
    }
    return mapping.get(category_slug, "free")

# ─── Sayfa çekici ─────────────────────────────────────────────────────────────

def get_links_from_list_page(url):
    """Liste sayfasından yazı linklerini topla."""
    res = requests.get(url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
        return [], None

    soup = BeautifulSoup(res.text, "html.parser")
    links = []

    for a in soup.select("h2 a, h3 a, .entry-title a"):
        href = a.get("href", "")
        if href.startswith("https://nasilgitmis.com/") and href not in links:
            # kategori ve sayfa linklerini atla
            if "/category/" not in href and "/page/" not in href and "/tag/" not in href:
                links.append(href)

    # Sonraki sayfa
    next_page = None
    next_btn = soup.select_one("a.next, .nav-next a, a[rel='next']")
    if next_btn:
        next_page = next_btn.get("href")

    return links, next_page


JUNK_LINE_PATTERNS = [
    re.compile(r"^\s*\d+\s+(min|dakika)\s+read\s*$", re.I),
    re.compile(r"^\s*\d+\s+(ay|yıl|gün|saat|hafta|dakika|saniye)\s+önce\s*$", re.I),
    re.compile(r"^\s*add\s+comment(s)?\s*$", re.I),
    re.compile(r"^\s*no\s+comments?\s*$", re.I),
    re.compile(r"^\s*(facebook|twitter|whatsapp|telegram|linkedin|share|paylaş)\s*$", re.I),
]

def normalize_title(t: str) -> str:
    """Çift boşluk + apostrof öncesi/sonrası boşluk gibi yazım artıklarını temizle."""
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*['’]\s*", "'", t)  # "Italya' da" → "Italya'da"
    return t.strip()


def clean_content(content_el, title: str) -> str:
    """Yazar/meta/footer/comment block'larını söküp metni süz."""
    if not content_el:
        return ""
    junk_selectors = [
        "header", "footer",
        ".entry-meta", ".post-meta", ".meta", ".byline",
        ".author", ".author-info", ".author-box",
        ".share", ".sharedaddy", ".social", ".jp-relatedposts",
        ".entry-title", "h1",
        ".comments-area", "#comments",
        "script", "style", "nav", "aside",
    ]
    for sel in junk_selectors:
        for el in content_el.select(sel):
            el.decompose()

    raw = content_el.get_text(separator="\n", strip=True)
    norm_title = normalize_title(title) if title else ""

    clean_lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(p.match(line) for p in JUNK_LINE_PATTERNS):
            continue
        if norm_title and line == title:
            continue  # başlığın metin içinde tekrarı
        if norm_title and normalize_title(line) == norm_title:
            continue
        clean_lines.append(line)

    return "\n".join(clean_lines)


def parse_post(url, category_slug):
    """Bir yazıyı parse edip opportunity dict'i döndür."""
    res = requests.get(url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # Başlık
    title_el = soup.select_one("h1.entry-title, h1")
    title = title_el.get_text(strip=True) if title_el else None
    if not title:
        return None
    title = normalize_title(title)

    # İçerik — meta/yazar/yorum/paylaşım block'larını söküp temizle
    content_el = soup.select_one(".entry-content, article")
    content = clean_content(content_el, title)

    # Ülke — başlık + içerikten
    combined_text = title + " " + content
    country_code = extract_country(combined_text)
    host_countries = [country_code]

    # Deadline
    deadline = None
    # Önce "Son Başvuru" satırını bul
    deadline_match = re.search(
        r"son\s+başvuru[:\s]+(.{5,30})",
        content.lower()
    )
    if deadline_match:
        deadline = extract_deadline(deadline_match.group(1))
    if not deadline:
        deadline = extract_deadline(content)

    # Deadline geçmişse ekleme
    if deadline:
        try:
            if date.fromisoformat(deadline) < date.today():
                return None  # geçmiş fırsat
        except Exception:
            pass

    # Yaş aralığı
    age_min, age_max = extract_age_range(content)

    # Eligibility notes — ilk 600 karakter
    eligibility_notes = content[:600] if content else None

    # Başvuru linki — "tıklayınız" veya "başvur" linklerini bul
    apply_url = url  # default olarak yazının kendi URL'si
    for a in (content_el or soup).find_all("a") if content_el else soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()
        if any(k in text for k in ["tıkla", "başvur", "apply", "form"]):
            if href.startswith("http") and "nasilgitmis.com" not in href:
                apply_url = href
                break

    return {
        "title":               title,
        "official_url":        url,          # nasilgitmis linki
        "deadline":            deadline,
        "deadline_notes":      f"Kaynak: nasilgitmis.com — başvuru: {apply_url}",
        "host_countries":      host_countries,
        "target_countries":    ["TR"],        # Türk gençlere yönelik
        "eligible_citizenships": ["TR"],
        "target_fields":       ["all"],
        "study_level":         ["any"],
        "age_min":             age_min,
        "age_max":             age_max or 30,
        "language_requirement": "Türkçe / İngilizce",
        "eligibility_notes":   eligibility_notes,
        "funding_type":        slug_to_funding_type(category_slug),
        "funding_notes":       "nasilgitmis.com'dan çekildi — detay için resmi sayfaya bakın",
        "category_id":         CATEGORY_IDS.get(category_slug),
        "is_featured":         False,
        "is_active":           True,
        "is_verified":         False,
    }

# ─── Ana akış ─────────────────────────────────────────────────────────────────

def scrape_category(cat_url, category_slug, max_pages=5):
    """Bir kategoriyi baştan sona tara."""
    print(f"\n📂 Kategori: {cat_url}")
    added = skipped = errors = 0
    page_url = cat_url
    page_num = 0

    while page_url and page_num < max_pages:
        page_num += 1
        print(f"  Sayfa {page_num}: {page_url}")

        links, next_page = get_links_from_list_page(page_url)
        print(f"  {len(links)} yazı bulundu")

        for link in links:
            if url_exists(link):
                skipped += 1
                continue

            record = parse_post(link, category_slug)

            if not record:
                errors += 1
                continue

            if not record.get("category_id") or "BURAYA" in (record.get("category_id") or ""):
                print(f"    ⚠ category_id eksik, atlandı: {link}")
                errors += 1
                continue

            ok = insert(record)
            if ok:
                added += 1
                print(f"    ✅ {record['title'][:55]}")
            else:
                errors += 1
                print(f"    ❌ Hata: {record['title'][:55]}")

            time.sleep(1)  # sitenin sunucusuna nazik ol

        page_url = next_page
        if page_url:
            time.sleep(2)

    return added, skipped, errors


def run():
    print("🚀 nasilgitmis.com scraper başladı")
    print(f"   Supabase: {SUPABASE_URL}\n")

    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY bulunamadı. .env dosyasını kontrol et.")
        return

    total_added = total_skipped = total_errors = 0

    for cat_url, slug in SITE_CATEGORIES.items():
        a, s, e = scrape_category(cat_url, slug, max_pages=3)
        total_added   += a
        total_skipped += s
        total_errors  += e

    print("\n" + "─" * 40)
    print(f"✅ Eklendi  : {total_added}")
    print(f"⏭  Atlandı  : {total_skipped} (zaten vardı)")
    print(f"❌ Hata     : {total_errors}")
    print("─" * 40)
    print("Bitti!")


if __name__ == "__main__":
    run()
