"""
Tek-seferlik audit — official_url = kaynak-site bug'ı
=====================================================
youthop-bot ve nasilgitmis-bot kaynaklı yayındaki fırsatların official_url'i
gerçek dış başvuru linki yerine scraper'ın KAYNAK sayfasına (youthop.com /
nasilgitmis.com) işaret ediyor olabilir. Bu script her kaynak sayfayı yeniden
çekip gerçek "Apply"/"Official link" dış linkini çıkarmayı dener ve yalnızca
RAPORLAR — DB'ye HİÇBİR ŞEY YAZMAZ.

Kullanım:
  python audit_apply_links.py            # sayımları göster
  python audit_apply_links.py --samples  # bulunan dış linklerden örnek de bas
"""

import os
import sys
import argparse
from urllib.parse import urlsplit, parse_qs, unquote

import requests
from dotenv import load_dotenv

import agent_reach_url_scraper as reach

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BOT_NICKNAMES = ("youthop-bot", "nasilgitmis-bot")

# Başvuru/resmî link sinyali taşıyan anchor metinleri. İki öncelik grubu:
# önce başvuru EYLEMİ (apply/başvur), sonra genel "resmî site".
APPLY_ACTION_KW = ("apply now", "apply", "application link", "how to apply",
                   "başvur", "kayıt ol", "register")
APPLY_OFFICIAL_KW = ("official link", "official website", "official site",
                     "visit website", "resmi site", "resmi web", "website")
# official_url dış-link sayılmasın diye atlanacak sosyal/uygulama/araç domainleri.
_JUNK_DOMAINS = ("facebook.", "twitter.", "x.com", "whatsapp.", "t.me", "m.me",
                 "linkedin.", "instagram.", "youtube.", "youtu.be", "apps.apple.",
                 "play.google.", "google.com", "pinterest.", "telegram.")


def _resolve_href(href: str) -> str:
    """youthop '/link?u=<encoded>' redirect sarmalını çöz; değilse href'i döndür."""
    sp = urlsplit(href)
    if sp.path.rstrip("/").endswith("/link") and "u=" in (sp.query or ""):
        u = parse_qs(sp.query).get("u", [""])[0]
        real = unquote(u)
        if real.startswith("http"):
            return real
    return href


def _is_real_external(href: str, source_netloc: str) -> bool:
    if not href.startswith("http"):
        return False
    dom = urlsplit(href).netloc.lower()
    if not dom or source_netloc in dom or dom in source_netloc:
        return False
    return not any(j in dom for j in _JUNK_DOMAINS)


def extract_apply_link(page, source_url: str) -> str | None:
    """Sayfadaki gerçek dış başvuru linkini döndürür (yoksa None). Metni başvuru
    anahtar kelimesi taşıyan anchor'ı bulur; youthop /link?u= sarmalını çözer;
    kaynak-domain ve sosyal/araç domainlerini eler. Önce başvuru-eylemi
    ('Apply now'), sonra genel ('Official link') aranır."""
    source_netloc = urlsplit(source_url).netloc.lower()
    anchors = []
    for a in page.css("a"):
        href = (a.attrib.get("href") or "").strip()
        if not href:
            continue
        txt = (a.get_all_text(strip=True) or "").lower()
        anchors.append((txt, _resolve_href(href)))

    for kwset in (APPLY_ACTION_KW, APPLY_OFFICIAL_KW):
        for txt, href in anchors:
            if any(kw in txt for kw in kwset) and _is_real_external(href, source_netloc):
                return href
    return None


def sb_get(params):
    return requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        params=params, timeout=30,
    ).json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", action="store_true", help="bulunan dış linklerden örnek bas")
    args = ap.parse_args()

    rows = sb_get({
        "submitted_by_nickname": f"in.({','.join(BOT_NICKNAMES)})",
        "select": "id,title,official_url,submitted_by_nickname",
        "limit": "1000",
    })
    print(f"İncelenen kayıt: {len(rows)} (youthop-bot + nasilgitmis-bot)\n")

    # source-site eşlemesi: official_url affected ise zaten kaynak sayfa odur.
    src_site = {"youthop-bot": "youthop.com", "nasilgitmis-bot": "nasilgitmis.com"}

    tally = {}  # (bot, durum) -> sayı
    samples = []
    for o in rows:
        bot = o.get("submitted_by_nickname")
        ou = o.get("official_url") or ""
        site = src_site.get(bot, "###")
        affected = site in urlsplit(ou).netloc.lower()

        if not affected:
            tally[(bot, "correct")] = tally.get((bot, "correct"), 0) + 1
            continue

        # affected → kaynak sayfayı (=official_url) çek, gerçek apply linki ara
        page = reach.fetch_page(ou)
        if page is None:
            tally[(bot, "fetch_err")] = tally.get((bot, "fetch_err"), 0) + 1
            continue
        apply = extract_apply_link(page, ou)
        if apply:
            tally[(bot, "recoverable")] = tally.get((bot, "recoverable"), 0) + 1
            if len(samples) < 12:
                samples.append((o.get("title", "")[:40], ou, apply))
        else:
            tally[(bot, "no_external")] = tally.get((bot, "no_external"), 0) + 1

    print("─" * 64)
    for bot in BOT_NICKNAMES:
        c = lambda s: tally.get((bot, s), 0)
        aff = c("recoverable") + c("no_external") + c("fetch_err")
        print(f"{bot}:")
        print(f"  affected (official_url=kaynak): {aff}")
        print(f"    ├─ düzeltilebilir (dış apply linki bulundu): {c('recoverable')}")
        print(f"    ├─ dış link YOK (kaynağa fallback gerekir)  : {c('no_external')}")
        print(f"    └─ kaynak sayfa çekilemedi                  : {c('fetch_err')}")
        print(f"  zaten doğru (correct): {c('correct')}")
    print("─" * 64)
    tot_rec = sum(tally.get((b, "recoverable"), 0) for b in BOT_NICKNAMES)
    tot_no = sum(tally.get((b, "no_external"), 0) for b in BOT_NICKNAMES)
    tot_err = sum(tally.get((b, "fetch_err"), 0) for b in BOT_NICKNAMES)
    print(f"TOPLAM affected: {tot_rec + tot_no + tot_err}  "
          f"(düzeltilebilir {tot_rec} · dış link yok {tot_no} · fetch hata {tot_err})")

    if args.samples and samples:
        print("\n── örnek çıkarımlar ──")
        for title, src, apply in samples:
            print(f"  • {title}\n      kaynak: {src}\n      apply : {apply}")


if __name__ == "__main__":
    main()
