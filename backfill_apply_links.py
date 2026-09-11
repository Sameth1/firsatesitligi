"""Yayındaki fırsatlar için doğrulanmış doğrudan başvuru rotası backfill'i.

Varsayılan salt-okunur rapordur. ``--apply`` yalnız doğrulanan rotaları yazar;
bulunamayanları yayından kaldırmaz, admin inceleme bayrağına taşır.

  python backfill_apply_links.py --limit 20
  python backfill_apply_links.py --json application-link-report.json
  python backfill_apply_links.py --apply
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

from application_links import is_safe_guided_url, resolve_application_route

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv(
    "SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co"
).rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def fetch_active(limit=None):
    """113 uygulanmışsa yeni alanları, değilse eski şemayı okuyarak raporlar."""
    common = "id,title,official_url,funding_notes,submitted_by_nickname,is_active"
    extended = (
        common + ",details_url,source_url,application_route_status,"
        "application_method,application_url_verified_at"
    )
    params = {"is_active": "eq.true", "select": extended, "order": "title.asc"}
    if limit:
        params["limit"] = str(limit)
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities", headers=HEADERS,
        params=params, timeout=30,
    )
    if response.status_code == 400:  # migration 113 henüz uygulanmamış olabilir
        params["select"] = common
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/opportunities", headers=HEADERS,
            params=params, timeout=30,
        )
    response.raise_for_status()
    return response.json()


def patch(opp_id, body):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
        params={"id": f"eq.{opp_id}"}, json=body, timeout=20,
    )
    response.raise_for_status()


def route_start(row):
    return row.get("source_url") or row.get("details_url") or row.get("official_url") or ""


def result_row(row, route):
    return {
        "id": row["id"],
        "title": row["title"],
        "before_url": row.get("official_url"),
        "source_url": route_start(row),
        "details_url": route.details_url,
        "application_url": route.application_url,
        "method": route.application_method,
        "verified": route.verified,
        "http_status": route.status_code,
        "evidence": route.evidence,
        "reason": route.reason,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="doğrulananları DB'ye yaz")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--domain", help="yalnız başlangıç URL'i bu domaini içerenler")
    parser.add_argument("--json", metavar="PATH", help="ayrıntılı raporu JSON'a yaz")
    args = parser.parse_args()

    rows = fetch_active(args.limit)
    if args.domain:
        rows = [row for row in rows if args.domain.casefold() in urlsplit(route_start(row)).netloc.casefold()]

    mode = "CANLI" if args.apply else "DRY-RUN"
    print(f"{len(rows)} aktif kayıt · {mode}")
    counts = Counter()
    report = []
    verified_at = datetime.now(timezone.utc).isoformat()

    for index, row in enumerate(rows, 1):
        start = route_start(row)
        if not start:
            counts["missing"] += 1
            continue
        route = resolve_application_route(start, max_hops=2)
        item = result_row(row, route)
        report.append(item)
        guided = (
            not route.verified
            and route.details_status_code == 200
            and is_safe_guided_url(route.details_url)
        )
        bucket = "verified" if route.verified else "guided" if guided else "unresolved"
        counts[bucket] += 1
        mark = "✓" if route.verified else "→" if guided else "·"
        print(f"{index:>3}/{len(rows)} {mark} {row['title'][:58]} — {route.reason}")

        if not args.apply:
            continue
        if route.verified:
            patch(row["id"], {
                "official_url": route.application_url,
                "details_url": route.details_url,
                "source_url": row.get("source_url") or start,
                "application_route_status": "verified",
                "application_method": route.application_method,
                "application_url_verified_at": verified_at,
                "application_url_check_status": route.status_code,
                "application_url_final": route.final_url,
                "application_url_evidence": route.evidence,
                "review_flag": None,
                "review_note": None,
                "review_flagged_at": None,
            })
        elif guided:
            patch(row["id"], {
                "details_url": route.details_url,
                "application_route_status": "guided",
                "application_method": None,
                "application_url_verified_at": None,
                "application_url_check_status": route.status_code,
                "application_url_final": None,
                "application_url_evidence": None,
                "review_flag": "guided_application_route",
                "review_note": (
                    "Doğrudan form bulunamadı; çalışan resmî fırsat sayfası "
                    "üzerinden birkaç adımda başvuru yapılabilir."
                ),
                "review_flagged_at": verified_at,
            })
        else:
            patch(row["id"], {
                "details_url": route.details_url,
                "application_route_status": "missing",
                "review_flag": "application_link_missing",
                "review_note": "Doğrulanmış doğrudan başvuru adımı bulunamadı: " + route.reason,
                "review_flagged_at": verified_at,
            })

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\nDoğrudan: {counts['verified']} · Rehberli: {counts['guided']} · "
        f"Çözülemedi: {counts['unresolved']} · URL yok: {counts['missing']}"
    )
    if not args.apply:
        print("DB değişmedi. Yazmak için migration 113 sonrası --apply gerekir.")


if __name__ == "__main__":
    main()
