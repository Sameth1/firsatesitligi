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
import html
import json
import argparse
import unicodedata
import requests
from urllib.parse import urlsplit, parse_qs, unquote, parse_qsl, urlencode, urlunsplit
from datetime import date, timedelta
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
    "ingiltere": "GB", "united kingdom": "GB", "uk": "GB",
    "britain": "GB", "great britain": "GB", "birleşik krallık": "GB",
    "ireland": "IE", "irlanda": "IE",
    "switzerland": "CH", "isviçre": "CH", "isvicre": "CH",
    "iceland": "IS", "izlanda": "IS",
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
                'meta[name="twitter:title"]::attr(content)',
                "title::text", "h1::text"):
        val = page.css(sel).get()
        if val and val.strip():
            return _clean_title(val)
    return None


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


def page_description(page) -> str | None:
    """Sayfanın kendi özeti: og:description / twitter:description / meta description.
    Gövde metninden çok daha temiz — editör tarafından yazılmış tek cümlelik özet,
    carousel/menü gürültüsü içermez. Açıklamanın birincil kaynağı."""
    for sel in ('meta[property="og:description"]::attr(content)',
                'meta[name="twitter:description"]::attr(content)',
                'meta[name="description"]::attr(content)'):
        val = page.css(sel).get()
        if val and val.strip() and len(val.strip()) >= 40:
            return val.strip()
    return None


def _deep_find(obj, key: str):
    """İç içe JSON-LD yapısında (dict/list, @graph dahil) verilen anahtarın ilk
    değerini döndürür. addressCountry/validThrough gibi alanlar şemaya göre farklı
    derinliklerde gömülü olabildiği için özyinelemeli arama şart."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _deep_find(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find(item, key)
            if found is not None:
                return found
    return None


def _normalize_country(val) -> str:
    """JSON-LD addressCountry değerini ISO-2 koda çevirir. Değer ISO kod ('DE'),
    ülke adı ('Germany') ya da {'@type':'Country','name':'Germany'} olabilir."""
    if isinstance(val, dict):
        val = val.get("name") or val.get("addressCountry") or ""
    if not isinstance(val, str):
        return ""
    val = val.strip()
    if len(val) == 2 and val.upper() in {c for c in COUNTRY_MAP.values()}:
        return val.upper()
    hit = _find_country_pos(val)
    return hit[1] if hit else ""


# JSON-LD'de fırsat sayfalarında ana varlık olma olasılığı yüksek @type'lar.
_JSONLD_PRIMARY_TYPES = {
    "JobPosting", "Course", "EducationalOccupationalProgram", "ScholarshipGrant",
    "Event", "Article", "NewsArticle", "WebPage", "Product", "Grant",
}


def extract_jsonld(page) -> dict:
    """Sayfadaki script[type=application/ld+json] bloklarını ayrıştırıp
    {name, description, country, deadline} döndürür (bulunamayan alan yok sayılır).
    Birincil kaynak — heuristiklerden önce buna güvenilir, çünkü site editörünün
    yapılandırdığı veridir. Hiçbir blok yoksa boş dict döner."""
    out: dict = {}
    blocks = page.css('script[type="application/ld+json"]::text').getall()
    nodes: list[dict] = []
    for raw in blocks:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and "@graph" in data:
            data = data["@graph"]
        if isinstance(data, list):
            nodes += [n for n in data if isinstance(n, dict)]
        elif isinstance(data, dict):
            nodes.append(data)

    if not nodes:
        return out

    def _type_of(n):
        t = n.get("@type", "")
        return {t} if isinstance(t, str) else set(t or [])

    primary = next((n for n in nodes if _type_of(n) & _JSONLD_PRIMARY_TYPES), None)
    primary = primary or next((n for n in nodes if n.get("name") or n.get("headline")), None)
    if primary is None:
        return out

    name = primary.get("name") or primary.get("headline")
    if isinstance(name, str) and name.strip():
        out["name"] = name.strip()

    desc = primary.get("description")
    if isinstance(desc, str) and desc.strip() and len(desc.strip()) >= 40:
        out["description"] = " ".join(desc.split())

    country = _normalize_country(_deep_find(primary, "addressCountry"))
    if country:
        out["country"] = country

    deadline = (_deep_find(primary, "validThrough")
                or _deep_find(primary, "applicationDeadline")
                or _deep_find(primary, "endDate"))
    if isinstance(deadline, str) and deadline.strip():
        out["deadline"] = deadline.strip()[:40]

    return out


# Uygunluk/başvuru şartı sinyali taşıyan cümle anahtarları (TR + EN).
_ELIGIBILITY_RE = re.compile(
    r"eligib|requirement|citizen|nationality|national of|applicants? must|open to"
    r"|uygun|vatandaş|başvuru koşul|başvuru şart|gerekli|şartlar",
    re.I,
)


def extract_eligibility(body: str, max_chars: int = 600) -> str:
    """Gövdeden yalnızca uygunluk/şart sinyali taşıyan cümleleri toplar. Açıklamanın
    kopyası DEĞİL — eşleşen cümle yoksa boş döner (eskiden description prefix'iydi)."""
    # Satır ve cümle sınırlarında böl; çok kısa parçaları (menü kalıntısı) ele.
    chunks = re.split(r"(?<=[.!?])\s+|\n+", body)
    hits: list[str] = []
    seen: set[str] = set()
    for ch in chunks:
        s = ch.strip()
        if len(s) < 25 or s in seen:
            continue
        if _ELIGIBILITY_RE.search(s):
            hits.append(s)
            seen.add(s)
    joined = " ".join(hits)
    return joined[:max_chars].rstrip(" ,;:") + ("…" if len(joined) > max_chars else "")


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


# Yakalanan deadline değerinin başında kalan fiil/bağlaç/ayraçlar. "deadline is
# Tuesday..." → group "is tuesday..." gelir; tarih değerine inene kadar bunları
# soyarız ("için"/"tarihi"/"olarak" TR, "is"/"are"/"will be" EN, ":/–/—/-" ayraç).
_DEADLINE_LEAD_RE = re.compile(
    r"^(?:is|are|was|were|will\s+be|için|son|tarih[i]?|olarak|ise|:|–|—|-|,)"
    r"(?=\s|:|–|—|-|,|$)[\s:–—,-]*",
    re.I,
)


# Geçerli bir deadline değeri en az bir rakam ya da ay adı içermeli. "deadline
# cannot be extended" gibi cümleler "deadline" kelimesinden sonra tarih gibi
# yakalanıyor; bu süzgeç onları eler.
_MONTH_NAMES = tuple(AY_MAP.keys())


def _looks_like_date(val: str) -> bool:
    """Değerde rakam veya bilinen ay adı (TR/EN) varsa True. Yoksa tarih değil
    (örn. 'cannot', 'varies', 'değişir')."""
    return bool(re.search(r"\d", val)) or any(m in val for m in _MONTH_NAMES)


def extract_deadline_text(md: str) -> str | None:
    # "Son Başvuru: X" veya "Deadline: X" tarzı satırları yakala
    for pattern in [
        r"son\s+başvuru[:\s]+([^\n]{4,60})",
        r"başvuru\s+son\s+tarih[i]?[:\s]+([^\n]{4,60})",
        r"deadline[:\s]+([^\n]{4,60})",
        r"application\s+deadline[:\s]+([^\n]{4,60})",
    ]:
        m = re.search(pattern, md.lower())
        if m:
            val = m.group(1).strip()
            # Tarih değerine inene kadar baştaki fiil/bağlaç/ayraçları soy.
            prev = None
            while prev != val:
                prev = val
                val = _DEADLINE_LEAD_RE.sub("", val).strip()
            val = val.rstrip(".,;:")
            # Rakam/ay içermiyorsa tarih değil — bu eşleşmeyi atla, sıradakini dene.
            if _looks_like_date(val):
                return val
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
    """Temizlenmiş gövdeden ilk anlamlı metni döndürür. Önce ardışık yinelenen
    cümleleri (menü/başlık tekrarı: 'Who can apply? Who can apply?') birleştirir,
    sonra kelime sınırında keser."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", body)
    deduped: list[str] = []
    for p in parts:
        p = p.strip()
        if p and (not deduped or p != deduped[-1]):
            deduped.append(p)
    text = " ".join(" ".join(deduped).split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    sp = cut.rfind(" ")
    if sp > max_chars * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:") + "…"


# "12 Days Remaining" / "Time Left: 94 Days" / "5 days left" gibi geri-sayım
# rozetleri (youthop vb. sitelerde net tarih yerine bunu gösterir). Net bir son
# başvuru tarihi çıkmazsa son çare: bugüne N gün ekleyip ISO tarih üret.
_DAYS_LEFT_RE = re.compile(
    r"time\s*left[:\s]*(\d{1,4})\s*days?"          # Time Left: 94 Days / Time Left 94 Days
    r"|(\d{1,4})\s*days?\s*(?:remaining|left)",    # 12 Days Remaining / 5 days left / 1 Day Remaining
    re.I,
)


def extract_days_remaining(text: str) -> int | None:
    """Sayfadaki geri-sayım rozetinden kalan gün sayısını döndürür (yoksa None).
    İlk eşleşme alınır; aside/footer page_text'te zaten budanmış olduğu için ana
    rozet öne çıkar. 0-1000 aralığı dışındaki saçma değerler elenir."""
    m = _DAYS_LEFT_RE.search(text or "")
    if not m:
        return None
    try:
        n = int(m.group(1) or m.group(2))
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 1000 else None


# Gerçek dış başvuru linki çıkarımı — official_url'in scraper kaynak sayfasına
# değil, gerçek başvuru adresine işaret etmesi için. İki öncelik: önce başvuru
# EYLEMİ (apply/başvur/tıkla…), sonra genel "resmî site".
_APPLY_ACTION_KW = ("apply now", "apply", "application", "how to apply",
                    "başvur", "kayıt ol", "tıkla", "buradan", "detaylar", "form",
                    "register")
_APPLY_OFFICIAL_KW = ("official link", "official website", "official site",
                      "resmi site", "resmi web", "visit website", "website")
# Apply sanılmaması gereken sosyal/mesajlaşma/uygulama-mağazası domainleri.
# NOT: docs.google / drive.google / forms.gle GERÇEK başvuru formu olabilir —
# bunları engellemiyoruz; yalnız sosyal hesaplar (Instagram vb.) elenir.
_APPLY_JUNK_DOMAINS = (
    "facebook.", "fb.com", "fb.me", "twitter.", "x.com", "whatsapp.", "wa.me",
    "t.me", "m.me", "linkedin.", "instagram.", "youtube.", "youtu.be", "tiktok.",
    "pinterest.", "telegram.", "apps.apple.", "play.google.",
)


# Başvuru linkinden temizlenecek izleme parametreleri. İşlevsel parametreler
# (p_package, p_lang, form alan id'leri vb.) KORUNUR — yalnız bunlar atılır.
_TRACKING_PARAMS_EXACT = {
    "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid", "yclid", "twclid",
    "igshid", "igsh", "mc_cid", "mc_eid", "ref", "ref_src", "ref_url", "_gl",
    "spm", "scid",
}
_TRACKING_PARAMS_PREFIX = ("utm_", "_ga", "_hs", "pk_", "mtm_")


def _strip_tracking(url: str) -> str:
    """URL query'sinden izleme parametrelerini (utm_*, fbclid, gclid, ref, _gl,
    _ga* …) atar; işlevsel parametreleri korur. Query yoksa URL aynen döner."""
    sp = urlsplit(url)
    if not sp.query:
        return url
    kept = [
        (k, v) for k, v in parse_qsl(sp.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS_EXACT
        and not any(k.lower().startswith(p) for p in _TRACKING_PARAMS_PREFIX)
    ]
    return urlunsplit((sp.scheme, sp.netloc, sp.path, urlencode(kept), sp.fragment))


def _resolve_link_wrapper(href: str) -> str:
    """youthop '/link?u=<encoded>' redirect sarmalını çözer; değilse href aynen."""
    sp = urlsplit(href)
    if sp.path.rstrip("/").endswith("/link") and "u=" in (sp.query or ""):
        real = unquote(parse_qs(sp.query).get("u", [""])[0])
        if real.startswith("http"):
            return real
    return href


def _is_real_external(href: str, source_netloc: str) -> bool:
    """href, kaynak-domain ve sosyal/araç domainleri dışında gerçek bir dış link mi?"""
    if not href.startswith("http"):
        return False
    dom = urlsplit(href).netloc.lower()
    if not dom or source_netloc in dom or dom in source_netloc:
        return False
    return not any(j in dom for j in _APPLY_JUNK_DOMAINS)


def extract_apply_link(page, source_url: str) -> str | None:
    """Sayfadaki GERÇEK dış başvuru linkini döndürür (yoksa None).
    - Metni başvuru anahtar kelimesi taşıyan anchor'ı bulur (önce eylem, sonra resmî).
    - youthop '/link?u=' sarmalını gerçek URL'ye çözer.
    - Kaynak-domain ve sosyal/araç domainlerini eler (Instagram'ı apply sanmaz).
    - Sonucu html.unescape eder ('&amp;' → '&').
    Kapsam: önce .entry-content/article (nasilgitmis gövdesi), bulunamazsa tüm
    sayfa (youthop apply butonları gövde dışında)."""
    src_netloc = urlsplit(source_url).netloc.lower()
    scopes = []
    for sel in (".entry-content", "article", "main"):
        nodes = page.css(sel)
        if nodes:
            scopes.append(nodes[0])
            break
    scopes.append(page)   # son çare: tüm sayfa
    for scope in scopes:
        anchors = [
            (_tr_lower(a.get_all_text(strip=True) or ""),
             _resolve_link_wrapper((a.attrib.get("href") or "").strip()))
            for a in scope.css("a")
        ]
        for kwset in (_APPLY_ACTION_KW, _APPLY_OFFICIAL_KW):
            for txt, href in anchors:
                if href and any(kw in txt for kw in kwset) and _is_real_external(href, src_netloc):
                    return _strip_tracking(html.unescape(href))
    return None


# Yaş şartı çıkarımı — yalnız AÇIK yaş ifadelerinde set edilir; bulunamazsa
# (None, None) = yaş sınırı yok. Yanlış pozitif (ör. "18 months", "30 credits")
# riskine karşı bağlam zorunlu (ages/aged/years old/yaş ya da minimum age).
_AGE_RANGE_RE = re.compile(
    r"(?:ages?|aged|between)\s*(\d{1,2})\s*(?:-|–|—|to|and)\s*(\d{1,2})"
    r"|(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*(?:years?[ -]?old|yaş)"
    r"|(\d{1,2})\s*[-–]\s*(\d{1,2})\s*yaş",
    re.I,
)
_AGE_MAX_RE = re.compile(
    r"(?:under|below|younger than|no older than|max(?:imum)?\s*age(?:\s*of)?)\s*(\d{1,2})",
    re.I,
)
_AGE_MIN_RE = re.compile(
    r"minimum\s*age(?:\s*of)?\s*(\d{1,2})|(\d{1,2})\s*(?:years?\s*)?or older",
    re.I,
)


def extract_age_range(text: str) -> tuple[int | None, int | None]:
    """Metinden (age_min, age_max) çıkarır; açık yaş ifadesi yoksa (None, None).
    Öncelik: açık aralık ('aged 28-40', '18-30 yaş') > üst sınır ('under 35') >
    alt sınır ('minimum age 18'). Mantıksız değerler (a<b, 10..99) elenir."""
    low = (text or "").lower()
    m = _AGE_RANGE_RE.search(low)
    if m:
        nums = [int(g) for g in m.groups() if g]
        if len(nums) >= 2 and 10 <= nums[0] < nums[1] <= 99:
            return nums[0], nums[1]
    mx = _AGE_MAX_RE.search(low)
    if mx:
        n = int(mx.group(1))
        if 15 <= n <= 99:
            excl = bool(re.search(r"(?:under|below|younger than)\s*" + str(n), low))
            return None, (n - 1 if excl else n)
    mn = _AGE_MIN_RE.search(low)
    if mn:
        n = int(next(g for g in mn.groups() if g))
        if 10 <= n <= 99:
            return n, None
    return None, None


# Eğitim kademesi çıkarımı. DB/RPC token seti SADECE {bachelor, master, phd, any}
# (frontend study_level seçenekleri). highschool/undergraduate/postgraduate/postdoc
# token'ı YOK → postdoc'u phd'ye, lise/gençlik/gönüllülük gibi eğitim-bağımsızları
# 'any'ye katlarız. RPC hard-filter olduğu için yanlış kademe = o kademe dışındaki
# herkesi eler → emin değilsek 'any' (güvenli, hepsine görünür).
_SL_PHD_RE = re.compile(r"\bph\.?\s?d\b|doctoral|doctorate|post[\s-]?doc|doktora", re.I)
_SL_MASTER_RE = re.compile(
    r"master'?s?\b|\bm\.?sc\b|\bmba\b|postgraduate|post[\s-]?graduate|yüksek\s+lisans", re.I)
_SL_BACHELOR_RE = re.compile(
    r"undergraduate|bachelor'?s?\b|\bb\.?sc\b|(?<!yüksek )\blisans\b", re.I)


def extract_study_level(text: str, title: str = "") -> list[str]:
    """Başlık+metinden hedef eğitim kademesi/kademelerini döndürür (kapsayıcı:
    birden çok geçiyorsa hepsi). Net sinyal yoksa ['any']."""
    t = ((title or "") + "\n" + (text or "")).lower()
    levels = []
    if _SL_PHD_RE.search(t):
        levels.append("phd")
    if _SL_MASTER_RE.search(t):
        levels.append("master")
    if _SL_BACHELOR_RE.search(t):
        levels.append("bachelor")
    return levels or ["any"]


def extract_fields(page, source_url: str, category: str | None) -> dict | None:
    # Birincil kaynak: sayfanın yapılandırılmış JSON-LD verisi. Her alan için
    # bulunamazsa mevcut heuristiklere düşülür.
    ld = extract_jsonld(page)

    title = ld.get("name") or page_title(page)
    if not title:
        return None
    body = page_text(page)
    # deadline/funding heuristikleri başlık + gövdenin tamamını tarasın.
    full_text = f"{title}\n{body}"

    country = ld.get("country") or extract_country(title, body)
    description = (ld.get("description") or page_description(page)
                  or first_paragraph(body, max_chars=1500))
    deadline = ld.get("deadline") or extract_deadline_text(full_text)
    # Net tarih yoksa son çare: "N Days Remaining" rozetinden bugüne N gün ekle.
    # ISO biçim → parse_deadline doğrudan kullanır, Postgres ::date sorunsuz cast eder.
    if not deadline:
        days = extract_days_remaining(full_text)
        if days is not None:
            deadline = (date.today() + timedelta(days=days)).isoformat()
    # Ülke çıkmazsa ['*'] (global/her ülke) — [] olursa ülke-filtreli aramalarda
    # HİÇ görünmez; '*' ise hepsinde görünür (match_opportunities: '*'=any).
    age_min, age_max = extract_age_range(full_text)
    return {
        "title": html.unescape(title),
        "url": source_url,
        "category_slug": category,
        "host_countries": [country] if country else ["*"],
        "deadline_text": deadline,
        "funding_type": extract_funding_type(full_text),
        "eligibility_notes": html.unescape(extract_eligibility(body)),
        "description": html.unescape(description),
        "age_min": age_min,
        "age_max": age_max,
        "study_level": extract_study_level(body, title),
        "language_requirement": None,
        "submitter_nickname": "agent-reach",
        "submitter_email": None,
        "status": "pending",
        "submission_origin": "agent",
        "review_stage": "agent_queue",
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


# Soft-404 sinyalleri: site olmayan sayfayı 200 ile bir hata/yönlendirme
# sayfasına servis edebilir (Chevening /not-found/ gibi). status koduna güvenemeyiz.
_SOFT_404_URL_RE = re.compile(r"/not-found/|/404|/error|/page-not-found/", re.I)
_SOFT_404_TITLE_RE = re.compile(r"^\s*(?:404|not\s+found|page\s+not\s+found)\b", re.I)


def is_soft_404(final_url: str, title: str) -> bool:
    """URL hata sayfası kalıbı içeriyorsa ya da başlık 404/not found ile
    başlıyorsa True. status 200 dönen 'yumuşak' 404'leri yakalar."""
    return bool(_SOFT_404_URL_RE.search(final_url or "")
                or _SOFT_404_TITLE_RE.search(title or ""))


def process_url(url: str, category: str | None, dry_run: bool) -> bool:
    print(f"\n🔗 {url}")
    page = fetch_page(url)
    if page is None:
        return False

    # Sayfa yönlendirildiyse (301/302) içerik son URL'den gelir; kaydı da o URL'ye
    # bağla — yoksa link ölü/yanlış sayfaya işaret eder. Scrapling Response.url
    # son URL'yi taşır; yoksa girilen URL'ye düş.
    final_url = getattr(page, "url", None) or url
    if final_url != url:
        print(f"  ↪️  yönlendirildi: {final_url}")
    record = extract_fields(page, final_url, category)
    if not record:
        print("  ❌ Başlık çıkarılamadı, atlandı")
        return False

    if is_soft_404(final_url, record["title"]):
        print(f"  🚫 soft-404 (sayfa yok / hata sayfası): {record['title']} — atlandı")
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
