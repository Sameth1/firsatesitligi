"""
Tek-seferlik backfill — official_url = kaynak-site bug'ını düzelt
=================================================================
youthop-bot ve nasilgitmis-bot kaynaklı yayındaki fırsatların official_url'i
scraper KAYNAK sayfasına işaret ediyor. Bu script her kaynak sayfayı yeniden
çekip reach.extract_apply_link ile GERÇEK dış başvuru linkini bulur ve
opportunities.official_url'i günceller.

  • Gerçek dış link bulunursa  → official_url = o link.
  • Bulunamazsa (Instagram-only vb.) → official_url DEĞİŞMEZ (kaynak kalır);
    funding_notes'a uyarı eklenir. (opportunities'te admin_note kolonu yok;
    uyarı funding_notes'a yazılır.)

Varsayılan DRY-RUN — DB'ye yazmaz, before/after raporu basar.
  python backfill_apply_links.py            # dry-run rapor
  python backfill_apply_links.py --apply    # DB'ye yaz
"""

import os
import sys
import argparse
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

import agent_reach_url_scraper as reach

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

SRC_SITE = {"youthop-bot": "youthop.com", "nasilgitmis-bot": "nasilgitmis.com"}
WARN = "[uyarı] dış başvuru linki bulunamadı, kaynak sayfaya yönlendiriyor"


def patch(opp_id, body):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
        params={"id": f"eq.{opp_id}"}, json=body, timeout=20,
    )
    r.raise_for_status()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="DB'ye yaz (varsayılan dry-run)")
    args = ap.parse_args()

    rows = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities", headers=H,
        params={"submitted_by_nickname": f"in.({','.join(SRC_SITE)})",
                "select": "id,title,official_url,funding_notes,submitted_by_nickname",
                "limit": "1000"}, timeout=30,
    ).json()

    mode = "CANLI — DB GÜNCELLENECEK" if args.apply else "DRY-RUN — DB'ye yazılmaz"
    print(f"{len(rows)} kayıt (youthop-bot + nasilgitmis-bot) · {mode}\n" + "─" * 72)

    n_fix = n_warn = n_skip = n_err = 0
    for o in rows:
        bot = o["submitted_by_nickname"]
        cur = o.get("official_url") or ""
        site = SRC_SITE.get(bot, "###")
        if site not in urlsplit(cur).netloc.lower():
            n_skip += 1
            continue  # zaten dış link (affected değil)

        page = reach.fetch_page(cur)
        if page is None:
            n_err += 1
            print(f"  ❌ FETCH-ERR  {o['title'][:46]}")
            continue
        apply = reach.extract_apply_link(page, cur)

        if apply:
            n_fix += 1
            print(f"  ✅ FIX  {o['title'][:44]}")
            print(f"        ÖNCE : {cur}")
            print(f"        SONRA: {apply}")
            if args.apply:
                patch(o["id"], {"official_url": apply})
        else:
            n_warn += 1
            print(f"  ⚠️  KAYNAK KALIR (dış link yok)  {o['title'][:40]}")
            print(f"        official_url (değişmez): {cur}")
            if args.apply:
                fn = (o.get("funding_notes") or "").strip()
                new_fn = fn if WARN in fn else (fn + " " + WARN).strip()
                patch(o["id"], {"funding_notes": new_fn})

    print("─" * 72)
    print(f"DÜZELTİLECEK (official_url→apply): {n_fix}")
    print(f"KAYNAK KALIR + uyarı (funding_notes): {n_warn}")
    print(f"Zaten doğru (atlandı): {n_skip}   |   fetch hata: {n_err}")
    if not args.apply:
        print("\n(DRY-RUN — hiçbir şey yazılmadı. Uygulamak için: --apply)")


if __name__ == "__main__":
    main()
