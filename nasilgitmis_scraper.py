"""
nasilgitmis.com Scraper
========================
nasilgitmis.com'dan Erasmus+, ESC, Burs ve Staj fırsatlarını çekip
Supabase 'submissions' tablosuna status='pending' olarak yazar.

Sayfa çekme Scrapling ile yapılır (önce hızlı HTTP, gerekirse gizli tarayıcı
fallback); Supabase REST çağrıları requests ile kalır.

Doğrudan 'opportunities'e (canlı site) YAZMAZ — kayıtlar öneri olarak
eklenir; validate_submissions.py incelemesinden geçip onaylanınca
agent_approve_submission RPC'si bunları opportunities'e taşır.

Kullanım:
  pip install "scrapling[fetchers]" requests python-dotenv && scrapling install
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
from datetime import date
from dotenv import load_dotenv
from scrapling.fetchers import Fetcher, StealthyFetcher

# Ortak başvuru-linki çıkarımı (reach.extract_apply_link). reach import sırasında
# load_dotenv + stdout reconfigure çalıştırır; yan etkisi yok, run() yalnız __main__'de.
import agent_reach_url_scraper as reach

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

# Sayfa çekme ayarları (Scrapling). Önce hızlı HTTP; engellenirse ya da içerik
# JS ile geç geliyorsa gizli tarayıcıya düşülür.
FETCH_TIMEOUT = 15
STEALTH_TIMEOUT_MS = 60_000
MIN_BODY_CHARS = 200
BLOCKED_STATUSES = {403, 429, 503}
# get_all_text çıkarımında atlanacak yapısal gürültü etiketleri.
_NOISE_TAGS = ("script", "style", "noscript", "nav", "header", "footer",
               "aside", "form", "svg", "button", "template")

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

# ─── Sayfa çekici (Scrapling) ─────────────────────────────────────────────────

def fetch_page(url):
    """Sayfayı Scrapling ile çeker. Önce hızlı HTTP (Fetcher); engellenirse ya da
    içerik JS ile geç geliyorsa gizli tarayıcıya (StealthyFetcher) düşer. Scrapling
    Response döndürür, başarısızsa None. requests+BeautifulSoup'un yerini alır."""
    try:
        page = Fetcher.get(url, timeout=FETCH_TIMEOUT, stealthy_headers=True)
    except Exception as e:
        print(f"  ⚠️  HTTP fetch hatası: {e} — gizli tarayıcı deneniyor")
        page = None

    blocked = page is None or page.status in BLOCKED_STATUSES
    too_thin = page is not None and len(page.get_all_text(strip=True)) < MIN_BODY_CHARS
    if blocked or too_thin:
        try:
            page = StealthyFetcher.fetch(
                url, headless=True, network_idle=True, timeout=STEALTH_TIMEOUT_MS)
        except Exception as e:
            if page is None:
                print(f"  ❌ Gizli tarayıcı da başarısız: {e}")
                return None
            # HTTP yanıtı vardı ama inceydi — eldekiyle devam et.

    if page is None or page.status >= 400:
        return None
    return page


def get_links_from_list_page(url):
    """Liste sayfasından yazı linklerini topla."""
    page = fetch_page(url)
    if page is None:
        return [], None

    links = []
    for a in page.css(".entry-title a, h2 a, h3 a"):
        href = (a.attrib.get("href") or "").strip()
        if href.startswith("https://nasilgitmis.com/") and href not in links:
            # kategori ve sayfa linklerini atla
            if "/category/" not in href and "/page/" not in href and "/tag/" not in href:
                links.append(href)

    # Sonraki sayfa
    next_page = None
    nb = page.css("a.next, .nav-next a, a[rel='next']")
    if nb:
        next_page = nb[0].attrib.get("href")

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


def clean_content(page, title: str) -> str:
    """Yazı gövdesini düz metne indirger. Önce .entry-content kabını (yoksa
    article) seçer — WordPress'te yorumlar/ilgili yazılar/yazar kutusu bu kabın
    DIŞINDA sibling olarak durduğu için doğal olarak elenir. _NOISE_TAGS ile
    yapısal gürültü, JUNK_LINE_PATTERNS ile satır gürültüsü ve başlık tekrarı
    süzülür. (Eski sürüm BeautifulSoup decompose ile sınıf-bazlı block siliyordu;
    .entry-content seçimi + satır süzgeci aynı sonucu Scrapling'le verir.)"""
    nodes = page.css(".entry-content") or page.css("article")
    if not nodes:
        return ""
    raw = nodes[0].get_all_text(separator="\n", strip=True, ignore_tags=_NOISE_TAGS)
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
    page = fetch_page(url)
    if page is None:
        return None

    # Başlık
    title = page.css("h1.entry-title::text").get() or page.css("h1::text").get()
    if not title or not title.strip():
        return None
    title = normalize_title(title)

    # İçerik — meta/yazar/yorum/paylaşım block'larını söküp temizle
    content = clean_content(page, title)

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

    # Başvuru linki — ortak reach.extract_apply_link: metni başvuru anahtar
    # kelimesi (tıkla/başvur/form/detaylar/buradan/kayıt ol/apply/resmi) taşıyan
    # ilk GERÇEK dış linki alır; sosyal/araç domainlerini (Instagram vb.) eler;
    # html.unescape eder. Bulunamazsa kaynak yazıya fallback + admin uyarısı
    # (eskiden submission atlanıyordu; artık eklenir ama official_url=kaynak
    # olduğu için işaretlenir).
    apply_url = reach.extract_apply_link(page, url)
    if apply_url:
        submission_url = apply_url
        funding_notes = f"nasilgitmis.com'dan çekildi — kaynak yazı: {url}"
        admin_note = None
    else:
        submission_url = url   # kaynak yazı (dış link yok)
        funding_notes = f"nasilgitmis.com kaynak yazısı (dış başvuru linki bulunamadı): {url}"
        admin_note = "[uyarı] dış başvuru linki bulunamadı, kaynak sayfaya yönlendiriyor"

    # submissions şeması opportunities'ten farklı: url (official_url değil),
    # category_slug (category_id değil), deadline_text (deadline date değil).
    # target_countries / study_level / is_active gibi opportunity-özel alanları
    # onay anında agent_approve_submission RPC'si dolduruyor; burada yok.
    rec = {
        "title":                title,
        "url":                  submission_url,
        "source_url":           url,
        "category_slug":        category_slug,
        "deadline_text":        deadline,      # 'YYYY-MM-DD' ya da None (text)
        "host_countries":       host_countries,
        "age_min":              age_min,
        "age_max":              age_max,   # bulunamazsa NULL (sahte 30 default'u kaldırıldı)
        "study_level":          reach.extract_study_level(content, title),  # bachelor/master/phd/any
        "language_requirement": "Türkçe / İngilizce",
        "eligibility_notes":    eligibility_notes,
        "funding_type":         slug_to_funding_type(category_slug),
        "funding_notes":        funding_notes,
        "submitter_nickname":   "nasilgitmis-bot",
        "status":               "pending",
        "submission_origin":    "agent",
        "review_stage":         "agent_queue",
    }
    if admin_note:
        rec["admin_note"] = admin_note
    return rec

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
