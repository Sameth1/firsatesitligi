"""
Scraper API — n8n için FastAPI servisi
======================================
İki scraper'ı (agent_reach_url_scraper, nasilgitmis_scraper) HTTP üzerinden
n8n workflow'larına açar. Sayfa çekme her yerde Scrapling ile yapılır.

Uç noktalar:
  GET  /health        → {"status": "ok"}
  POST /scrape        → {"url","category?"}      tek URL'i çekip alanları döndürür
  POST /scrape-site   → {"site_url","category","max_items?"}
                        Scrapling Spider API ile nasilgitmis tarzı crawl;
                        liste sayfasından yazıları izleyip her birini parse eder.

Bu servis Supabase'e YAZMAZ — yalnızca çıkarılan alanları döndürür. Kayıt ekleme
kararını (submissions tablosuna POST) n8n verir; böylece dedup/onay akışı orada
kalır.

Çalıştırma:
  pip install "scrapling[fetchers]" fastapi uvicorn && scrapling install
  uvicorn scraper_api:app --host 0.0.0.0 --port 8000

Tek URL örneği (n8n HTTP Request node):
  POST http://localhost:8000/scrape
  {"url": "https://home.cern/students-educators/summer-student-programme",
   "category": "internship"}

Site crawl örneği:
  POST http://localhost:8000/scrape-site
  {"site_url": "https://nasilgitmis.com/category/staj/",
   "category": "internship", "max_items": 20}
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from scrapling.spiders import CrawlSpider, CrawlRule, LinkExtractor

# Mevcut scraper'ların çıkarım mantığını yeniden kullan — kopyalama yok.
# (İki modül de import sırasında load_dotenv + stdout reconfigure çalıştırır;
#  yan etkisi yok, run() yalnızca __main__'de tetiklenir.)
import agent_reach_url_scraper as reach
import nasilgitmis_scraper as ng

app = FastAPI(
    title="fırsateşitliği Scraper API",
    description="agent_reach + nasilgitmis scraper'larını n8n'e açan Scrapling servisi",
    version="1.0.0",
)


# ─── İstek/yanıt modelleri ────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str = Field(..., description="Çekilecek fırsat URL'si")
    category: str | None = Field(
        None, description=f"Opsiyonel kategori slug ({', '.join(sorted(reach.VALID_CATEGORIES))})")


class ScrapeSiteRequest(BaseModel):
    site_url: str = Field(..., description="Crawl başlangıcı (ör. kategori liste sayfası)")
    category: str = Field(..., description="Bu sitedeki tüm yazılara uygulanacak kategori slug")
    max_items: int = Field(20, ge=1, le=200, description="En fazla bu kadar yazı parse edilir")


# ─── nasilgitmis tarzı Scrapling Spider ───────────────────────────────────────

_APPLY_KEYWORDS = ("tıkla", "başvur", "apply", "form",
                   "detaylar", "resmi site", "buradan", "kayıt ol")


def _clean_post_content(response, title: str) -> str:
    """Bir yazı sayfasının ana içeriğini düz metne indirger. nasilgitmis'in
    BeautifulSoup tabanlı clean_content'inin Scrapling karşılığı: ana içerik
    kabını seçer, gürültü etiketlerini get_all_text ile atar, ardından
    ng.JUNK_LINE_PATTERNS satır süzgecinden ve başlık-tekrarı elemesinden geçirir.
    (Sınıf-bazlı .share/.comments-area budaması get_all_text'te yok; satır
    süzgeci sosyal/yorum artıklarının çoğunu yakalar.)"""
    nodes = response.css(".entry-content") or response.css("article")
    container = nodes[0] if nodes else response
    raw = container.get_all_text(
        separator="\n", strip=True,
        ignore_tags=("script", "style", "noscript", "nav", "header",
                     "footer", "aside", "form", "svg", "button"))
    norm_title = ng.normalize_title(title) if title else ""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(p.match(line) for p in ng.JUNK_LINE_PATTERNS):
            continue
        if norm_title and (line == title or ng.normalize_title(line) == norm_title):
            continue
        lines.append(line)
    return "\n".join(lines)


def build_post_record(response, category_slug: str) -> dict | None:
    """Scrapling Response'tan submissions şemasına uygun bir kayıt çıkarır —
    nasilgitmis_scraper.parse_post'un Spider/Scrapling uyarlaması. Geçmiş son
    başvuru tarihli ya da başlıksız yazılar için None döner."""
    title = response.css("h1.entry-title::text").get() or response.css("h1::text").get()
    if not title or not title.strip():
        return None
    title = ng.normalize_title(title)

    content = _clean_post_content(response, title)
    combined = f"{title} {content}"

    deadline = ng.find_deadline(content)
    if deadline and ng.date.fromisoformat(deadline) < ng.date.today():
        return None  # geçmiş fırsat — atla

    age_min, age_max = ng.extract_age_range(content)

    # Başvuru linki: metni başvuru anahtar kelimesi içeren ilk dış link.
    apply_url = response.url
    nodes = response.css(".entry-content") or response.css("article")
    scope = nodes[0] if nodes else response
    for a in scope.css("a"):
        href = (a.attrib.get("href") or "").strip()
        text = ng._tr_lower(a.get_all_text(strip=True) or "")
        if any(k in text for k in _APPLY_KEYWORDS):
            if href.startswith("http") and "nasilgitmis.com" not in href:
                apply_url = href
                break

    return {
        "title":                title,
        "url":                  response.url,
        "category_slug":        category_slug,
        "deadline_text":        deadline,
        "host_countries":       [ng.extract_country(combined)],
        "age_min":              age_min,
        "age_max":              age_max or 30,
        "language_requirement": "Türkçe / İngilizce",
        "eligibility_notes":    ng.truncate_at_word(content, 600) if content else None,
        "funding_type":         ng.slug_to_funding_type(category_slug),
        "funding_notes":        f"{urlparse(response.url).netloc}'dan çekildi — başvuru: {apply_url}",
        "submitter_nickname":   "scraper-api",
        "status":               "pending",
    }


class SiteSpider(CrawlSpider):
    """Liste sayfasından yazı linklerini izleyip her yazıyı parse eden generic
    spider. nasilgitmis WordPress yapısına göre ayarlı (h2/h3/.entry-title
    içindeki linkler = yazı; /category/, /page/, /tag/ = atla). max_items'a
    ulaşınca crawl duraklatılır."""

    name = "site_spider"
    download_delay = 1.0              # sitenin sunucusuna nazik ol
    concurrent_requests = 4

    def __init__(self, site_url: str, category_slug: str, max_items: int, **kw):
        super().__init__(**kw)
        self.start_urls = [site_url]
        self.allowed_domains = [urlparse(site_url).netloc]
        self.category_slug = category_slug
        self.max_items = max_items
        self._count = 0

    def rules(self):
        # NOT: Scrapling'de restrict_css, içinde link aranacak KAPSAYICI bölgeyi
        # gösterir — <a>'nın kendisini değil. Yani yazı başlığını taşıyan
        # h2/.entry-title verilir, extractor içindeki <a href>'i bulur.
        return [
            # 1) Yazı linkleri → parse_post
            CrawlRule(
                LinkExtractor(
                    restrict_css=(".entry-title", "h2", "h3"),
                    deny=(r"/category/", r"/page/", r"/tag/", r"/author/"),
                    allow_domains=self.allowed_domains,
                ),
                callback=self.parse_post,
            ),
            # 2) Sonraki sayfa (/page/N) → callback yok; default parse o sayfada
            #    kuralları yeniden işletip oradaki yazıları da toplar.
            CrawlRule(
                LinkExtractor(
                    allow=(r"/page/\d+",),
                    allow_domains=self.allowed_domains,
                ),
            ),
        ]

    async def parse_post(self, response):
        if self._count >= self.max_items:
            self.pause()
            return
        record = build_post_record(response, self.category_slug)
        if record:
            self._count += 1
            yield record
            if self._count >= self.max_items:
                self.pause()


# ─── Uç noktalar ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/scrape")
def scrape(req: ScrapeRequest):
    """Tek URL'i Scrapling ile çekip (HTTP, gerekirse gizli tarayıcı fallback)
    başlık/ülke/deadline/funding alanlarını döndürür. DB'ye yazmaz.

    Endpoint senkron `def` — Scrapling fetch ve Spider kendi event loop'unu
    yönettiği için FastAPI bunu threadpool'da çalıştırır, loop çakışması olmaz."""
    if req.category and req.category not in reach.VALID_CATEGORIES:
        raise HTTPException(422, f"Geçersiz kategori: {req.category}. "
                                 f"Geçerli: {sorted(reach.VALID_CATEGORIES)}")
    page = reach.fetch_page(req.url)
    if page is None:
        raise HTTPException(502, f"Sayfa çekilemedi: {req.url}")
    record = reach.extract_fields(page, req.url, req.category)
    if record is None:
        raise HTTPException(422, "Başlık çıkarılamadı — sayfa fırsat içermiyor olabilir")
    return record


@app.post("/scrape-site")
def scrape_site(req: ScrapeSiteRequest):
    """Scrapling Spider API ile nasilgitmis tarzı crawl: site_url liste
    sayfasından başlar, yazı linklerini izler, her yazıyı parse eder. max_items
    kadar kayıt toplanınca durur. DB'ye yazmaz; kayıt listesini döndürür."""
    if req.category not in reach.VALID_CATEGORIES:
        raise HTTPException(422, f"Geçersiz kategori: {req.category}. "
                                 f"Geçerli: {sorted(reach.VALID_CATEGORIES)}")
    spider = SiteSpider(req.site_url, req.category, req.max_items)
    try:
        result = spider.start()
    except Exception as e:
        raise HTTPException(502, f"Crawl hatası: {e}")
    items = list(result.items)
    return {
        "site_url": req.site_url,
        "category": req.category,
        "count": len(items),
        # truncated=True → max_items'a ulaşıldı, sitede daha fazla yazı olabilir
        # (n8n bir sonraki sayfadan/offset'ten devam edebilir). Scrapling'in kendi
        # `paused` bayrağı yalnızca resume-checkpoint için; cap sinyali bu değil.
        "truncated": len(items) >= req.max_items,
        "items": items,
    }
