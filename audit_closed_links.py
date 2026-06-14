"""
Tek-seferlik audit — kapalı/ölü fırsat linkleri
================================================
Yayındaki (is_active=true) fırsatların official_url'ini çekip sayfa metninde
"kapandı/artık yok" sinyali arar (Google Forms 'no longer accepting responses',
"application closed", "başvuru kapandı" vb.). Yalnızca RAPORLAR — DB'ye HİÇBİR
ŞEY YAZMAZ. Match'leri insan gözden geçirip elle pasifleştirebilir.

Kullanım:
  python audit_closed_links.py --limit 10     # test
  python audit_closed_links.py                # tüm aktifler
"""

import os
import sys
import argparse

import requests
from dotenv import load_dotenv

import agent_reach_url_scraper as reach

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# "Kapalı/bitti" sinyalleri (küçük harf, substring). Geniş tutulur; audit olduğu
# için yanlış-pozitif tolere edilir — eşleşen ifade raporlanır, insan karar verir.
CLOSED_SIGNALS = [
    "sorry",
    "no longer available",
    "this opportunity has ended",
    "application closed",
    "applications closed",
    "deadline passed",
    "kapalı",
    "başvuru kapandı",
    "form is closed",
    "this form is no longer accepting responses",
    "no longer accepting responses",
]


def fetch_active(limit=None):
    params = {"is_active": "eq.true", "select": "id,title,official_url",
              "order": "submitted_by_nickname.asc", "limit": str(limit or 5000)}
    r = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities",
                     headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def find_closed_signal(page):
    """Kapalı sinyali döndürür (yoksa None). İki katman:
    1. SON URL kontrolü — kapalı Google Form '/viewform'dan '/closedform'a
       yönlenir; bu mesaj JS-render olduğu için metinde GÖRÜNMEZ, yalnız URL'de.
    2. Metin sinyalleri (statik HTML'de görünen 'application closed' vb.)."""
    final_url = (getattr(page, "url", "") or "").lower()
    if "/closedform" in final_url:
        return "closedform (Google Forms kapalı)"

    try:
        text = page.get_all_text(strip=True).lower()
    except Exception:
        return None
    for sig in CLOSED_SIGNALS:
        if sig in text:
            return sig
    return None


def main():
    ap = argparse.ArgumentParser(description="Aktif fırsat linklerinde kapalı sinyali denetimi")
    ap.add_argument("--limit", type=int, help="en fazla bu kadar fırsat denetle")
    args = ap.parse_args()

    rows = fetch_active(args.limit)
    print(f"{len(rows)} aktif fırsat denetleniyor (DB'ye yazılmaz)\n" + "─" * 70)

    flagged = clean = err = 0
    hits = []
    for o in rows:
        u = (o.get("official_url") or "").strip()
        if not u:
            err += 1
            continue
        try:
            page = reach.fetch_page(u)
        except Exception as e:
            # Bozuk encoding / lxml hatası bir sayfada tüm run'ı düşürmesin.
            err += 1
            print(f"  ❓ FETCH HATASI [{type(e).__name__}]  {o['title'][:46]}\n        {u}")
            continue
        if page is None:
            err += 1
            print(f"  ❓ ÇEKİLEMEDİ  {o['title'][:48]}\n        {u}")
            continue
        sig = find_closed_signal(page)
        if sig:
            flagged += 1
            hits.append((o["title"], u, sig))
            print(f"  🚩 KAPALI? [{sig}]  {o['title'][:46]}\n        {u}")
        else:
            clean += 1

    print("─" * 70)
    print(f"İŞARETLENEN (kapalı şüphesi): {flagged}")
    print(f"Temiz: {clean}   |   çekilemedi: {err}   |   toplam: {len(rows)}")
    if hits:
        print("\n── işaretlenenler (title · sinyal) ──")
        for t, u, s in hits:
            print(f"  • {t[:50]:52} [{s}]")


if __name__ == "__main__":
    main()
