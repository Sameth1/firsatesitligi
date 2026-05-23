"""
Agent Reach — URL → Submission Scraper
=======================================
Herhangi bir fırsat URL'sini Scrapling ile çekip submissions tablosuna
'pending' olarak yazar. Admin panelinde Onayla/Revize/Reddet ile yayına alınır.

Idealist ve nasılgitmiş gibi site-spesifik scraper'ların aksine bu generic —
ESN, Erasmus+, üniversite burs sayfaları, blog yazıları, Reddit post linki vb.
hangi URL atılırsa Scrapling sayfayı çeker, biz de başlık/ülke/deadline
heuristikleriyle alanları çıkarırız.

Önce hızlı HTTP isteği (Fetcher) denenir; sayfa bot korumasıyla engellerse ya da
içerik JS ile geç yükleniyorsa otomatik olarak StealthyFetcher (gizli tarayıcı)
fallback'ine düşülür — eskiden Jina Reader'ın sunucu tarafında yaptığı işi
yerelde yaparız.

Kullanım:
  pip install "scrapling[fetchers]" python-dotenv && scrapling install
  python agent_reach_url_scraper.py <URL> [--category=scholarship]
  python agent_reach_url_scraper.py <URL> --dry-run    # DB'ye yazma, sadece göster

Birden fazla URL:
  python agent_reach_url_scraper.py --file urls.txt --category=internship

.env (zaten var):
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=eyJ...
"""

import os
import re
import sys
import json
import argparse
import unicodedata
import requests
from datetime import date
from dotenv import load_dotenv
from scrapling.fetchers import Fetcher, StealthyFetcher

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# HTTP isteği için zaman aşımı (sn) ve gizli tarayıcı fallback eşiği.
FETCH_TIMEOUT = 30
STEALTH_TIMEOUT_MS = 60_000
MIN_BODY_CHARS = 200          # bundan azı çıkarsa içerik JS ile geliyor sayılır
BLOCKED_STATUSES = {403, 429, 503}

VALID_CATEGORIES = {
    "scholarship", "volunteering", "youth_project",
    "internship", "summer_school", "exchange",
}

VALID_FUNDING = {"full", "partial", "free", "stipend"}

# nasilgitmis_scraper.py'den taşındı — Türkçe + İngilizce ülke isimleri
COUNTRY_MAP = {
    "kuzey makedonya": "MK", "north macedonia": "MK", "makedonya": "MK",
    "güney kore": "KR", "south korea": "KR", "korea": "KR",
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
    "slovenya": "SI", "slovenia": "SI",
    "malta": "MT",
    "japonya": "JP", "japan": "JP",
    "ingiltere": "GB", "united kingdom": "GB",
    "abd": "US", "amerika": "US", "usa": "US", "united states": "US",
}

AY_MAP = {
    "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
    "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
    "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _tr_lower(s: str) -> str:
    """Türkçe-uyumlu küçük harf: 'İ'→'i', 'I'→'ı'. Python'un düz .lower()'ı
    'İ'yi 'i̇' (combining nokta) yapıp eşleşmeyi bozar."""
    return s.replace("İ", "i").replace("I", "ı").lower()


def _ascii_lower(s: str) -> str:
    """Diakritikleri atıp küçük harfe indirir: 'İsveç'/'Isveç' → 'isvec'.
    _tr_lower'a ek ASCII güvencesi şart — İngilizce 'Italy' büyük-I'li yazıldığı
    için TR fold'da 'ıtaly'ye düşer; ASCII fold onu 'italy' tutar."""
    nf = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nf if not unicodedata.combining(c)).lower()


# Açıklamaya sızmaması gereken, sayfalarda sık geçen boilerplate.
_BOILERPLATE_RE = re.compile(
    r"çerez|cookie|gizlilik politikas|privacy policy|tüm hakları sakl"
    r"|all rights reserved|skip to (main )?content|abone ol|subscribe|newsletter"
    r"|bülten|bizi takip|follow us|share this|sosyal medya|oturum aç"
    r"|sign in|log in|©",
    re.I,
)
# Tek bir ülke atanamayacak — Avrupa geneli / çok-ülkeli program sinyalleri.
_MULTI_COUNTRY_RE = re.compile(
    r"programme countries|program countries|all eu countries|across europe"
    r"|europe-wide|eu-wide|tüm program ülke|avrupa genel|avrupa çap|birçok ülke",
    re.I,
)
# get_all_text çıkarımında atlanacak gürültü etiketleri (menü/altbilgi/form/script).
_NOISE_TAGS = ("script", "style", "noscript", "nav", "header", "footer",
               "aside", "form", "svg", "button", "template")
# <title> sonundaki "| Site Adı" / "- Site Adı" eklerini ayıracak ayraçlar.
_TITLE_SEP_RE = re.compile(r"\s+[|»·–—-]\s+")


def clean_text_body(text: str) -> str:
    """Scrapling'in çıkardığı düz metni satır satır temizler: boş satırları,
    yatay çizgileri ve çerez/menü gibi boilerplate satırlarını atar. Açıklama ve
    ülke çıkarımı bunun üzerinden yapılır — sayfadaki çerez/menü metni alanlara
    sızmasın. (HTML zaten _NOISE_TAGS ile budanmış halde gelir; bu son süzgeç.)"""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"[-=*_|\s]+", line):  # yatay çizgi / ayraç
            continue
        if _BOILERPLATE_RE.search(line):
            continue
        out.append(line)
    return "\n".join(out)


def fetch_page(url: str):
    """Sayfayı çeker. Önce hızlı HTTP (Fetcher); engellenirse ya da içerik JS ile
    geç geliyorsa gizli tarayıcıya (StealthyFetcher) düşer. Scrapling Response
    döndürür — başarısızsa None. Eskiden Jina Reader'ın yaptığı işin yereli."""
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
        print(f"  ❌ Sayfa alınamadı (HTTP {getattr(page, 'status', '?')})")
        return None
    return page


def _clean_title(raw: str) -> str:
    """'Başlık | Site Adı' → 'Başlık'. Birden fazla parça varsa ve son parça
    kısaysa (≤40 char, muhtemelen site adı) onu atar; aksi halde dokunmaz."""
    parts = _TITLE_SEP_RE.split(raw.strip())
    if len(parts) >= 2 and len(parts[-1]) <= 40 and len(parts[0]) >= 8:
        return parts[0].strip()
    return raw.strip()


def page_title(page) -> str | None:
    """Sayfa başlığı: önce og:title / twitter:title meta'sı (en temiz), sonra
    <title> (site-adı eki temizlenmiş), en son ilk <h1>."""
    for sel in ('meta[property="og:title"]::attr(content)',
                'meta[name="twitter:title"]::attr(content)'):
        val = page.css(sel).get()
        if val and val.strip():
            return val.strip()
    val = page.css("title::text").get()
    if val and val.strip():
        return _clean_title(val)
    val = page.css("h1::text").get()
    return val.strip() if val and val.strip() else None


def page_text(page) -> str:
    """Sayfanın ana içeriğini düz metin olarak döndürür. <article>/<main> varsa
    onu, yoksa <body>'yi alır; _NOISE_TAGS (menü/altbilgi/script…) çıkarılır;
    ardından satır bazlı boilerplate süzgecinden geçirilir."""
    container = page
    for sel in ("article", "main", '[role="main"]', "body"):
        nodes = page.css(sel)
        if nodes:
            container = nodes[0]
            break
    text = container.get_all_text(separator="\n", strip=True, ignore_tags=_NOISE_TAGS)
    return clean_text_body(text)


def _find_country_pos(text: str):
    """(en-erken-konum, ülke kodu) döndürür; eşleşme yoksa None. Hem TR hem ASCII
    fold ile aranır ('İtalya' ve 'Italy' ikisi de tutsun). usa/abd gibi kısa adlar
    kelime sınırıyla aranır — 'abdomen'/'usage' false-positive olmaz."""
    text_tr = _tr_lower(text)
    text_ascii = _ascii_lower(text)
    best_pos, best_code = None, None
    for name, code in COUNTRY_MAP.items():
        name_tr = _tr_lower(name)
        name_ascii = _ascii_lower(name)
        if len(name_ascii) <= 4:
            m = (re.search(r"\b" + re.escape(name_tr) + r"\b", text_tr)
                 or re.search(r"\b" + re.escape(name_ascii) + r"\b", text_ascii))
            pos = m.start() if m else -1
        else:
            cands = [p for p in (text_tr.find(name_tr), text_ascii.find(name_ascii))
                     if p != -1]
            pos = min(cands) if cands else -1
        if pos != -1 and (best_pos is None or pos < best_pos):
            best_pos, best_code = pos, code
    return (best_pos, best_code) if best_code is not None else None


def extract_country(title: str, body: str) -> str:
    """Ülkeyi önce başlıkta arar (en güçlü sinyal). Başlıkta yoksa: metin
    Avrupa-geneli/çok-ülkeli program işaret ediyorsa ülke ATAMAZ (admin seçsin);
    aksi halde gövdede en erken konumdaki ülkeyi alır. Eski sürüm ham markdown'ı
    tarayıp nav/footer'daki ilk ülke adını kapıyordu."""
    hit = _find_country_pos(title or "")
    if hit:
        return hit[1]
    if _MULTI_COUNTRY_RE.search(body or ""):
        return ""
    hit = _find_country_pos(body or "")
    return hit[1] if hit else ""


def extract_deadline_text(md: str) -> str | None:
    # "Son Başvuru: X" veya "Deadline: X" tarzı satırları yakala
    for pattern in [
        r"son\s+başvuru[:\s]+([^\n]{4,40})",
        r"başvuru\s+son\s+tarih[i]?[:\s]+([^\n]{4,40})",
        r"deadline[:\s]+([^\n]{4,40})",
        r"application\s+deadline[:\s]+([^\n]{4,40})",
    ]:
        m = re.search(pattern, md.lower())
        if m:
            return m.group(1).strip().rstrip(".,;:")
    return None


def extract_funding_type(md: str) -> str | None:
    low = md.lower()
    if any(k in low for k in ["tam burs", "fully funded", "full scholarship", "100% funded"]):
        return "full"
    if any(k in low for k in ["kısmi burs", "partial funding", "partially funded"]):
        return "partial"
    if any(k in low for k in ["stipend", "harçlık", "monthly allowance", "aylık ödenek"]):
        return "stipend"
    if any(k in low for k in ["ücretsiz", "free of charge", "gönüllü", "volunteer"]):
        return "free"
    return None


def first_paragraph(body: str, max_chars: int = 600) -> str:
    """Temizlenmiş gövdeden ilk anlamlı metni, kelime sınırında keserek döndür."""
    text = " ".join(body.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    sp = cut.rfind(" ")
    if sp > max_chars * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:") + "…"


def extract_fields(page, source_url: str, category: str | None) -> dict | None:
    title = page_title(page)
    if not title:
        return None
    body = page_text(page)
    # deadline/funding heuristikleri başlık + gövdenin tamamını tarasın.
    full_text = f"{title}\n{body}"
    country = extract_country(title, body)
    return {
        "title": title,
        "url": source_url,
        "category_slug": category,
        "host_countries": [country] if country else [],
        "deadline_text": extract_deadline_text(full_text),
        "funding_type": extract_funding_type(full_text),
        "eligibility_notes": first_paragraph(body, max_chars=600),
        "description": first_paragraph(body, max_chars=1500),
        "language_requirement": None,
        "submitter_nickname": "agent-reach",
        "submitter_email": None,
    }


def submit(record: dict) -> tuple[bool, str]:
    if not SUPABASE_KEY:
        return False, "SUPABASE_SERVICE_ROLE_KEY yok (.env kontrol et)"
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/submissions",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=record,
        timeout=15,
    )
    return res.status_code in (200, 201), res.text


def process_url(url: str, category: str | None, dry_run: bool) -> bool:
    print(f"\n🔗 {url}")
    page = fetch_page(url)
    if page is None:
        return False

    record = extract_fields(page, url, category)
    if not record:
        print("  ❌ Başlık çıkarılamadı, atlandı")
        return False

    print(f"  📝 {record['title']}")
    print(f"     ülke={record['host_countries']}  deadline={record['deadline_text']}  funding={record['funding_type']}")

    if dry_run:
        print("  🧪 dry-run — DB'ye yazılmadı")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return True

    ok, msg = submit(record)
    if ok:
        print("  ✅ submissions'a 'pending' olarak eklendi — admin panelinde onayla")
    else:
        print(f"  ❌ Hata: {msg[:200]}")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Agent Reach URL scraper")
    parser.add_argument("url", nargs="?", help="Tek URL")
    parser.add_argument("--file", help="Her satırı bir URL olan dosya")
    parser.add_argument("--category", choices=sorted(VALID_CATEGORIES), help="Kategori slug (opsiyonel)")
    parser.add_argument("--dry-run", action="store_true", help="DB'ye yazma, sadece göster")
    args = parser.parse_args()

    if not args.url and not args.file:
        parser.error("Bir URL veya --file ver")

    urls: list[str] = []
    if args.url:
        urls.append(args.url)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            urls += [line.strip() for line in f if line.strip() and not line.startswith("#")]

    ok_count = 0
    for url in urls:
        if process_url(url, args.category, args.dry_run):
            ok_count += 1

    print(f"\n─ Bitti: {ok_count}/{len(urls)} başarılı")


if __name__ == "__main__":
    main()
