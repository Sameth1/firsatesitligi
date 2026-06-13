"""
Tek-seferlik backfill — personalizasyon alanları (host_countries + age)
=======================================================================
Bugünün scraper-kaynaklı AKTİF fırsatları (youthop-bot + nasilgitmis-bot):
  • host_countries = [] → ['*']  (boş = ülke-filtreli aramalarda HİÇ görünmez;
    '*' = global, hepsinde görünür — match_opportunities '*'=any).
  • age: kaynak sayfayı yeniden çekip extract_age_range ile gerçek yaş arar.
      - gerçek yaş bulunursa → onu yaz (ör. youthop'ta kaçırılmış 28-40'ı kurtar).
      - bulunamaz VE mevcut (age_min=NULL, age_max=30 sahte default) ise → NULL.
      - aksi halde (zaten gerçek yaş verisi) → dokunma.

Kaynak sayfa URL'i funding_notes'tan ("kaynak: <url>") çıkarılır (official_url
artık dış apply linki).

Varsayılan DRY-RUN. python backfill_personalization.py [--apply]
"""

import os
import re
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
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
_URL_RE = re.compile(r"https?://[^\s]+")


def patch(opp_id, body):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/opportunities",
                       headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                       params={"id": f"eq.{opp_id}"}, json=body, timeout=20)
    r.raise_for_status()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="DB'ye yaz (varsayılan dry-run)")
    args = ap.parse_args()

    rows = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities", headers=H,
        params={"submitted_by_nickname": "in.(youthop-bot,nasilgitmis-bot)",
                "is_active": "eq.true",
                "select": "id,title,host_countries,age_min,age_max,funding_notes",
                "limit": "500"}, timeout=30).json()

    mode = "CANLI — DB GÜNCELLENECEK" if args.apply else "DRY-RUN — DB'ye yazılmaz"
    print(f"{len(rows)} aktif kayıt · {mode}\n" + "─" * 72)

    n_host = n_age_recover = n_age_null = n_age_keep = n_err = 0
    for o in rows:
        body = {}
        cur_hc = o.get("host_countries") or []
        # 1) host_countries boş → ['*']
        if not cur_hc:
            body["host_countries"] = ["*"]
            n_host += 1

        # 2) yaş — kaynak sayfadan re-check
        cur_min, cur_max = o.get("age_min"), o.get("age_max")
        m = _URL_RE.search(o.get("funding_notes") or "")
        amin = amax = None
        found = False
        if m:
            page = reach.fetch_page(m.group(0))
            if page is not None:
                txt = (o.get("title") or "") + "\n" + reach.page_text(page)
                amin, amax = reach.extract_age_range(txt)
                found = amin is not None or amax is not None
            else:
                n_err += 1
        if found:
            if (amin, amax) != (cur_min, cur_max):
                body["age_min"], body["age_max"] = amin, amax
                n_age_recover += 1
                print(f"  🎯 YAŞ KURTAR ({cur_min},{cur_max})→({amin},{amax})  {o['title'][:40]}")
        elif cur_min is None and cur_max == 30:
            body["age_min"], body["age_max"] = None, None
            n_age_null += 1
        else:
            n_age_keep += 1

        if not body:
            continue
        tags = []
        if "host_countries" in body: tags.append("host→*")
        if "age_max" in body and body.get("age_max") is None and "age_min" in body and body["age_min"] is None and not (amin or amax):
            tags.append("age→NULL")
        if args.apply:
            patch(o["id"], body)

    print("─" * 72)
    print(f"host_countries [] → ['*'] : {n_host}")
    print(f"yaş KURTARILAN (gerçek bulundu): {n_age_recover}")
    print(f"yaş NULL'lanan (sahte 30, yaş yok): {n_age_null}")
    print(f"yaş dokunulmayan: {n_age_keep}   |   kaynak fetch hata: {n_err}")
    if not args.apply:
        print("\n(DRY-RUN — yazılmadı. Uygulamak için: --apply)")


if __name__ == "__main__":
    main()
