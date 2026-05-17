"""
nasilgitmis.com Scraper
========================
nasilgitmis.com'dan Erasmus+, ESC, Burs ve Staj fırsatlarını çekip
Supabase 'submissions' tablosuna status='pending' olarak yazar.

Doğrudan 'opportunities'e (canlı site) YAZMAZ — kayıtlar öneri olarak
eklenir; validate_submissions.py incelemesinden geçip onaylanınca
agent_approve_submission RPC'si bunları opportunities'e taşır.

Kullanım:
  pip install requests python-dotenv beautifulsoup4
  python nasilgitmis_scraper.py

.env dosyasında olması gerekenler:
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=eyJ...
"""

import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

# Windows konsolu (cp1254) emoji/Türkçe karakterde UnicodeEncodeError verir;
# çıktıyı UTF-8'e sabitle.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

# ─── Ayarlar ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# nasilgitmis.com kategori URL → DB slug eşlemesi
# Not: submissions tablosu category_slug (id değil) tutar; slug→id eşlemesi
# gerekmez — agent_approve_submission RPC'si onay anında kategoriyi çözer.
SITE_CATEGORIES = {
    "https://nasilgitmis.com/category/esc/":          "volunteering",
    "https://nasilgitmis.com/category/erasmus/":      "youth_project",
    "https://nasilgitmis.com/category/egitimveburs/": "scholarship",
    "https://nasilgitmis.com/category/staj/":         "internship",
}

# Ülke adı → ISO kodu
# Sıra önemli: önce çok-kelimeli/uzun isimler, sonra kısa olanlar.
# Kısa kodlar (uk, abd) word-boundary ile aranır — false-positive engelleme.
COUNTRY_MAP = {
    "kuzey makedonya": "MK", "north macedonia": "MK", "makedonya": "MK",
    "güney kore": "KR", "south korea": "KR", "korea": "KR",
    "kuzey kıbrıs": "CY", "kıbrıs": "CY", "cyprus": "CY",
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
    "slovenya": "SI", "slovenia": "SI",
    "bosna": "BA", "bosnia": "BA",
    "sırbistan": "RS", "serbia": "RS",
    "ukrayna": "UA", "ukraine": "UA",
    "japonya": "JP", "japan": "JP",
    "türkiye": "TR", "turkey": "TR",
    "ingiltere": "GB", "united kingdom": "GB",
    "abd": "US", "amerika": "US", "usa": "US",
    # Kısa kodlar — word-boundary ile aranıyor (extract_country bk.):
    "uk": "GB",
}

SHORT_COUNTRY_KEYS = {"uk", "abd", "usa"}  # word-boundary gerektirenler

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
    """URL zaten yayında (opportunities.official_url) ya da öneri olarak
    bekliyor (submissions.url) mu? İkisinden birinde varsa kopya say —
    aynı fırsatı tekrar pending'e eklemeyelim."""
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
    (ok: bool, detay: str) döndürür — hata varsa detay HTTP gövdesini taşır."""
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/submissions",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        json=record,
        timeout=15,
    )
    ok = res.status_code in (200, 201, 204)
    return ok, ("" if ok else f"HTTP {res.status_code}: {res.text[:160]}")

# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

import unicodedata as _unicodedata

def _tr_lower(s: str) -> str:
    """Türkçe-uyumlu lowercase. Python'un .lower()'ı 'İ' → 'i\\u0307' yapar
    ve 'italya' string'iyle eşleşmez. Burada manuel mapliyoruz."""
    return s.replace("İ", "i").replace("I", "ı").lower()


def _ascii_lower(s: str) -> str:
    """Diakritikleri at + lowercase. 'Italya' / 'İsveç' gibi yanlış-doğru yazım
    farklarına çift güvence olsun diye TR fold'a ek olarak kullanılır."""
    nf = _unicodedata.normalize("NFKD", s)
    return "".join(c for c in nf if not _unicodedata.combining(c)).lower()


def extract_country(text):
    """Metinde EN ERKEN konumda geçen ülkeyi seç. Eski sürüm COUNTRY_MAP sözlük
    sırasına göre ilk eşleşeni dönüyordu; bu yüzden içerikte geçen alakasız bir
    ülke, başlıktaki doğru ülkeyi gölgeleyebiliyordu. parse_post combined_text'i
    'başlık + içerik' verdiği için en-erken-konum başlığı otomatik önceler.
    Kısa kodlar (uk/abd/usa) kelime sınırıyla aranır ('ukrayna' false-positive
    olmaz). Hem TR fold hem ASCII fold ile bakılır: 'İtalya'/'Italya' eşit."""
    text_tr = _tr_lower(text)
    text_ascii = _ascii_lower(text)
    best_pos, best_code = None, None
    for name, code in COUNTRY_MAP.items():
        name_tr = _tr_lower(name)
        name_ascii = _ascii_lower(name)
        if name in SHORT_COUNTRY_KEYS:
            m = (re.search(r"\b" + re.escape(name_tr) + r"\b", text_tr)
                 or re.search(r"\b" + re.escape(name_ascii) + r"\b", text_ascii))
            pos = m.start() if m else -1
        else:
            cands = [p for p in (text_tr.find(name_tr), text_ascii.find(name_ascii))
                     if p != -1]
            pos = min(cands) if cands else -1
        if pos != -1 and (best_pos is None or pos < best_pos):
            best_pos, best_code = pos, code
    return best_code or "*"

# Tarih çıkarımında kullanılan ay haritası ve 'deadline' etiketleri.
_AY_MAP = {
    "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
    "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
    "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12",
}
# Son başvuru etiketi varyantları. 'application deadline' 'deadline'den ÖNCE —
# alternation soldan denendiği için uzun olan önce gelmeli.
_DEADLINE_KW = (
    r"son\s+başvuru|başvuru\s+tarih[ıi]|başvuru\s+son"
    r"|application\s+deadline|deadline"
)
_DEADLINE_KW_RE = re.compile(_DEADLINE_KW, re.I)
# Etiketten sonraki ~45 karakterlik pencere. re.DOTALL şart: clean_content metni
# \n ile birleştirdiği için etiket ile tarih ayrı satırlarda olabiliyor; eski
# regex'te '.' newline eşleşmediğinden tarih hiç yakalanamıyordu (Bug A).
_DEADLINE_AFTER_RE = re.compile(
    r"(?:" + _DEADLINE_KW + r")(.{0,45})", re.I | re.DOTALL
)


def _find_dates_with_pos(text):
    """Metindeki tüm GEÇERLİ tarihleri [(konum, 'YYYY-MM-DD'), ...] olarak,
    konuma göre sıralı döndürür. Üç format: ISO, Türkçe ay adı, noktalı."""
    found = []
    low = text.lower()
    for m in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
        found.append((m.start(), m.group(0)))
    ay = "|".join(_AY_MAP)
    for m in re.finditer(r"(\d{1,2})\s+(" + ay + r")\s+(\d{4})", low):
        g, a, y = m.group(1), m.group(2), m.group(3)
        found.append((m.start(), f"{y}-{_AY_MAP[a]}-{g.zfill(2)}"))
    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        found.append((m.start(), f"{y}-{mo.zfill(2)}-{d.zfill(2)}"))
    valid = []
    for pos, iso in found:
        try:
            date.fromisoformat(iso)
            valid.append((pos, iso))
        except ValueError:
            pass  # 31.02.2026 gibi geçersiz tarihleri ele
    valid.sort(key=lambda pd: pd[0])
    return valid


def extract_deadline(text):
    """Metindeki ilk geçerli tarihi 'YYYY-MM-DD' döndürür (yoksa None)."""
    dates = _find_dates_with_pos(text)
    return dates[0][1] if dates else None


def find_deadline(content):
    """Son başvuru tarihini bulur.
    Aşama 1 — bir 'deadline' etiketinin (son başvuru / başvuru tarihi / başvuru
    son / application deadline / deadline) hemen ardındaki tarih; re.DOTALL
    sayesinde etiket ile tarih ayrı satırlarda olsa da yakalanır (Bug A).
    Aşama 2 — aşama 1 boşsa: içerikteki tüm tarihler arasından bir etikete EN
    YAKIN olanı seçilir, ilk-rastgele-tarih alınmaz (Bug B). Hiç etiket yoksa
    güvenilir deadline yok kabul edilir (None) — yanlış 'geçmiş' filtrelemesi
    yapılmasın diye."""
    m = _DEADLINE_AFTER_RE.search(content)
    if m:
        d = extract_deadline(m.group(1))
        if d:
            return d
    kw = [mm.start() for mm in _DEADLINE_KW_RE.finditer(content)]
    dates = _find_dates_with_pos(content)
    if not kw or not dates:
        return None
    return min(dates, key=lambda pd: min(abs(pd[0] - k) for k in kw))[1]

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


def truncate_at_word(text, limit=600):
    """Metni limit karakterde değil, son tam cümlede (yoksa kelimede) keser —
    eligibility_notes'un kelime ortasında kesilmesini engeller."""
    if not text or len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? ", "\n"):
        idx = cut.rfind(sep)
        if idx > limit * 0.6:
            return cut[:idx + 1].strip()
    sp = cut.rfind(" ")
    cut = cut[:sp] if sp > limit * 0.6 else cut
    return cut.rstrip(" ,;:") + "…"

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
    # Tek başına kategori etiketi bir satırda gelirse içerikten say (başlık tekrar değil)
    re.compile(r"^\s*(staj|burs|burslar|gönüllülük|gönülluluk|erasmus|esc|exchange|değişim)\s*$", re.I),
    # WordPress yorum formu / ilgili yazılar / breadcrumb artıkları
    re.compile(r"^\s*(yorum(lar)?|yorum\s+yap|bir\s+cevap\s+yazın|cevabı\s+iptal\s+et)\s*$", re.I),
    re.compile(r"^\s*e-?posta\b.*yayı[mn]lan", re.I),
    re.compile(r"^\s*(adınız|e-?posta|web\s+sitesi|isim)\s*\*?\s*$", re.I),
    re.compile(r"^\s*(ilgili|önerilen|benzer|popüler)\s+yazılar\s*$", re.I),
    re.compile(r"^\s*anasayfa\s*[»>›/].*", re.I),
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

    # Deadline — find_deadline: etiket sonrası tarih (Bug A), yoksa etikete en
    # yakın tarih (Bug B). _find_dates_with_pos yalnızca geçerli tarih döndürdüğü
    # için fromisoformat burada hata vermez.
    deadline = find_deadline(content)
    if deadline and date.fromisoformat(deadline) < date.today():
        return None  # geçmiş fırsat — ekleme

    # Yaş aralığı
    age_min, age_max = extract_age_range(content)

    # Eligibility notes — ilk ~600 karakter, cümle/kelime sınırında kesilir
    eligibility_notes = truncate_at_word(content, 600) if content else None

    # Başvuru linki — link metni şu kelimelerden birini içeren ilk dış linki al.
    # _tr_lower: büyük harfli buton metinleri ("BAŞVUR", "TIKLA", "KAYIT OL") de
    # eşleşsin — Python'un .lower()'ı 'I'yı 'i' yapıp dotless-ı'lı kelimeleri
    # kaçırıyordu.
    apply_url = url  # default olarak yazının kendi URL'si
    apply_keywords = ("tıkla", "başvur", "apply", "form",
                      "detaylar", "resmi site", "buradan", "kayıt ol")
    for a in (content_el or soup).find_all("a") if content_el else soup.find_all("a"):
        href = a.get("href", "")
        text = _tr_lower(a.get_text(strip=True))
        if any(k in text for k in apply_keywords):
            if href.startswith("http") and "nasilgitmis.com" not in href:
                apply_url = href
                break

    # submissions şeması opportunities'ten farklı: url (official_url değil),
    # category_slug (category_id değil), deadline_text (deadline date değil).
    # target_countries / study_level / is_active gibi opportunity-özel alanları
    # onay anında agent_approve_submission RPC'si dolduruyor; burada yok.
    return {
        "title":                title,
        "url":                  url,          # nasilgitmis yazı linki (kaynak)
        "category_slug":        category_slug,
        "deadline_text":        deadline,      # 'YYYY-MM-DD' ya da None (text)
        "host_countries":       host_countries,
        "age_min":              age_min,
        "age_max":              age_max or 30,
        "language_requirement": "Türkçe / İngilizce",
        "eligibility_notes":    eligibility_notes,
        "funding_type":         slug_to_funding_type(category_slug),
        "funding_notes":        f"nasilgitmis.com'dan çekildi — başvuru: {apply_url}",
        "submitter_nickname":   "nasilgitmis-bot",
        "status":               "pending",
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

            if not record.get("category_slug"):
                print(f"    ⚠ category_slug eksik, atlandı: {link}")
                errors += 1
                continue

            ok, detay = insert(record)
            if ok:
                added += 1
                print(f"    ✅ pending: {record['title'][:55]}")
            else:
                errors += 1
                print(f"    ❌ Hata: {record['title'][:55]} — {detay}")

            time.sleep(1)  # sitenin sunucusuna nazik ol

        page_url = next_page
        if page_url:
            time.sleep(2)

    return added, skipped, errors


def run():
    print("🚀 nasilgitmis.com scraper başladı")
    print(f"   Supabase: {SUPABASE_URL}")
    print("   Hedef: submissions tablosu (status=pending)\n")

    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY bulunamadı. .env dosyasını kontrol et.")
        return

    total_added = total_skipped = total_errors = 0

    for cat_url, slug in SITE_CATEGORIES.items():
        a, s, e = scrape_category(cat_url, slug, max_pages=3)
        total_added   += a
        total_skipped += s
        total_errors  += e

    print("\n" + "─" * 40)
    print(f"✅ Eklendi  : {total_added} pending submission")
    print(f"⏭  Atlandı  : {total_skipped} (opportunities/submissions'ta zaten vardı)")
    print(f"❌ Hata     : {total_errors}")
    print("─" * 40)
    print("Bitti!")


if __name__ == "__main__":
    run()
