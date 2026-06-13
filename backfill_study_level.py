"""
Tek-seferlik backfill — opportunities.study_level
==================================================
Bugünün scraper-kaynaklı aktif fırsatları (youthop-bot + nasilgitmis-bot) için
kaynak sayfayı yeniden çekip extract_study_level ile hedef eğitim kademesini
çıkarır ve opportunities.study_level'ı günceller. Şu an hepsi ['any'] (RPC
hardcoded yazıyordu); gerçek sinyal varsa bachelor/master/phd'ye çevrilir.

Varsayılan DRY-RUN. python backfill_study_level.py [--apply]
"""

import os
import re
import sys
import argparse
from collections import Counter

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
                "select": "id,title,study_level,funding_notes",
                "limit": "500"}, timeout=30).json()

    mode = "CANLI — DB GÜNCELLENECEK" if args.apply else "DRY-RUN — DB'ye yazılmaz"
    print(f"{len(rows)} aktif kayıt · {mode}\n" + "─" * 72)

    trans = Counter()    # 'any→phd' gibi geçiş etiketi
    changed = err = 0
    samples = []
    for o in rows:
        cur = o.get("study_level") or []
        m = _URL_RE.search(o.get("funding_notes") or "")
        if not m:
            err += 1
            continue
        page = reach.fetch_page(m.group(0))
        if page is None:
            err += 1
            continue
        new = reach.extract_study_level(reach.page_text(page), o.get("title") or "")
        if sorted(new) != sorted(cur):
            changed += 1
            trans["+".join(sorted(new))] += 1
            if len(samples) < 14:
                samples.append((o["title"][:42], cur, new))
            if args.apply:
                patch(o["id"], {"study_level": new})
        else:
            trans["değişmedi(" + "+".join(sorted(cur)) + ")"] += 1

    print("YENİ study_level dağılımı (değişenler):")
    for k, v in trans.most_common():
        print(f"  {k:24}: {v}")
    print("─" * 72)
    print(f"DEĞİŞECEK: {changed} / {len(rows)}   |   kaynak fetch hata: {err}")
    if samples:
        print("\n── örnekler (başlık: önce → sonra) ──")
        for t, c, n in samples:
            print(f"  {t:44} {c} → {n}")
    if not args.apply:
        print("\n(DRY-RUN — yazılmadı. Uygulamak için: --apply)")


if __name__ == "__main__":
    main()
