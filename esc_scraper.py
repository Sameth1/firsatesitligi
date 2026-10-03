"""
Avrupa Dayanışma Programı (ESC) gönüllülük ilanları → submissions (pending)
==========================================================================
Avrupa Gençlik Portalı'nın (youth.europa.eu) ESC ilan veritabanı, Avrupa
Komisyonu'nun resmî kaynağı. Portal ilanları herkese açık bir arama API'sinden
alıyor:

  GET https://youth.europa.eu/api/rest/eyp/v1/search_en
      ?type=Opportunity&filters[status]=open&size=500&from=0

Her ilan yapılandırılmış alanlarla geliyor: ev sahibi ülke, başvuru son tarihi
(`date_application_end` ya da `has_no_deadline`), gönüllülerin hangi
ülkelerden olabileceği (`volunteer_countries`), katılımcı profili, konaklama
ve harçlık bilgisi. İlanın herkese açık sayfası
https://youth.europa.eu/solidarity/placement/<id>_en sunucuda tam içerikle
üretiliyor; ajan kaydı oradan doğruluyor.

Neden bu kaynak: nasilgitmis'in ESC yazıları zaten bu ilanların özetleri.
Asıl kaynaktan çekmek hem daha çok ilan (Ekim 2026: Türkiye'den gönüllü kabul
eden, yurt dışında, son başvurusu geçmemiş 182 açık ilan) hem de derleme
sitesi yerine resmî sayfa demek. ESC'de yol, konaklama, yemek, harçlık ve
sigorta programdan karşılanır.

FİLTRELEME (scraper tarafı, ajandan ÖNCE):
  • status=open (dolu/kapanmış ilanlar gelmez)
  • volunteer_countries içinde Türkiye ya da "all"
  • ev sahibi ülke Türkiye değil (platform yurt dışı fırsatları için)
  • son başvuru bugün ya da sonrası, veya ilan açıkça son tarihsiz
  • yalnız gönüllülük ve insani yardım gönüllülüğü kolları

Yaş, dil, uyruk gibi kullanıcı filtreleri burada TAHMİN EDİLMEZ; ajan sayfadan
birebir alıntıyla belirler. (Örnek: API bir ilanda Türkiye'yi listeliyor ama
profil "citizen of an EU country" diyor — ajanın katı uyruk taraması bu
çelişkiyi yakalar.)

Kullanım:
  python esc_scraper.py --dry-run --limit 5
  python esc_scraper.py                  # canlı — submissions'a yaz

.env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date

import requests
from dotenv import load_dotenv

from discovery_gate import KNOWN_URL_COLUMNS, ONLINE_ONLY_RE, candidate_blockers

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

API_URL = "https://youth.europa.eu/api/rest/eyp/v1/search_en"
DETAIL_URL = "https://youth.europa.eu/solidarity/placement/{id}_en"
PAGE_SIZE = 500
MAX_RECORDS = 6000
CRAWL_DELAY = 0.5
HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"),
    "Accept": "application/json",
}
ALLOWED_STRANDS = {"volunteering", "humanitarian"}
# Portal AB kodlarını kullanıyor; ISO 3166-1 alfa-2'ye çevir.
EU_TO_ISO = {"EL": "GR", "UK": "GB"}

# ─── Supabase yardımcıları (diğer scraper'larla aynı kalıp) ─────────────────

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"}


def url_exists(url):
    """URL yayında, bekliyor ya da daha önce işlenmiş mi? Statü filtresi yok:
    reddedilen ilan haftalık taramada yeniden eklenmez."""
    for table, col in KNOWN_URL_COLUMNS:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(),
                           params={col: f"eq.{url}", "select": "id", "limit": 1},
                           timeout=15)
        if res.ok and res.json():
            return True
    return False


def insert(record):
    res = requests.post(f"{SUPABASE_URL}/rest/v1/submissions",
                        headers={**sb_headers(), "Prefer": "return=minimal"},
                        json=record, timeout=15)
    ok = res.status_code in (200, 201, 204)
    return ok, ("" if ok else f"HTTP {res.status_code}: {res.text[:160]}")

# ─── API ─────────────────────────────────────────────────────────────────────

def fetch_open_opportunities(max_records=MAX_RECORDS):
    """Açık (status=open) bütün ilanlar, sayfa sayfa."""
    rows, offset = [], 0
    while offset < max_records:
        res = requests.get(API_URL, headers=HTTP_HEADERS, timeout=60, params={
            "type": "Opportunity", "size": PAGE_SIZE, "from": offset,
            "filters[status]": "open",
        })
        res.raise_for_status()
        data = res.json()
        hits = (data.get("hits") or {}).get("hits") or []
        if not hits:
            break
        rows.extend(hit.get("_source") or {} for hit in hits)
        offset += len(hits)
        total = ((data.get("hits") or {}).get("total") or {}).get("value", 0)
        if offset >= total:
            break
        time.sleep(CRAWL_DELAY)
    return rows

# ─── Kayıt oluşturma ─────────────────────────────────────────────────────────

def _plain(value):
    """HTML'li alanı düz metne çevirir."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _deadline(op):
    """(ISO son tarih | None, son tarihsiz mi)."""
    if op.get("has_no_deadline"):
        return None, True
    raw = str(op.get("date_application_end") or "")[:10]
    try:
        return date.fromisoformat(raw).isoformat(), False
    except ValueError:
        return None, False


def scope_reason(op, today):
    """İlan kapsam dışıysa nedeni, değilse boş metin."""
    if op.get("status") != "open":
        return "ilan açık değil"
    strands = set(op.get("strand") or [])
    if not strands & ALLOWED_STRANDS:
        return f"gönüllülük dışı kol ({', '.join(sorted(strands)) or '?'})"
    volunteers = op.get("volunteer_countries") or []
    if "all" not in volunteers and "TR" not in volunteers:
        return "Türkiye'den gönüllü kabul etmiyor"
    country = EU_TO_ISO.get(op.get("country"), op.get("country"))
    if not country:
        return "ev sahibi ülke yok"
    if country == "TR":
        return "Türkiye'de yapılıyor (yurt dışı değil)"
    if ONLINE_ONLY_RE.search(op.get("title") or ""):
        return "yalnız çevrim içi etkinlik"
    deadline, rolling = _deadline(op)
    if not rolling and (deadline is None or deadline < today.isoformat()):
        return "son başvuru tarihi geçmiş ya da yok"
    return ""


def build_record(op):
    url = DETAIL_URL.format(id=op["id"])
    deadline, _rolling = _deadline(op)
    country = EU_TO_ISO.get(op.get("country"), op.get("country"))
    strands = set(op.get("strand") or [])
    kind = ("ESC insani yardım gönüllülüğü" if "humanitarian" in strands
            else "ESC gönüllülüğü")
    profile = _plain(op.get("participant_profile"))
    place = ", ".join(filter(None, (op.get("town"), country)))
    return {
        "title": _plain(op.get("title"))[:300],
        "url": url,
        "details_url": url,
        "source_url": url,
        "application_route_status": "unverified",
        "category_slug": "volunteering",
        # Son tarihsiz ilanda deadline_text boş; ajan "No application
        # deadline" alıntısıyla sürekli başvuru olarak doğrular.
        "deadline_text": deadline,
        "host_countries": [country],
        "age_min": None,
        "age_max": None,
        "study_level": None,
        "language_requirement": None,
        # Profil metni sayfada birebir geçiyor; ajan uygunluğu bununla sınar.
        "eligibility_notes": (profile[:1200] or None),
        "description": _plain(op.get("description"))[:1500] or None,
        # ESC: yol, konaklama, yemek, harçlık ve sigorta programdan karşılanır.
        # Ajan bunu ilan sayfasındaki "Accommodation, food and transport
        # arrangements" bölümüyle doğrular.
        "funding_type": "full",
        "funding_notes": (f"{kind} — {op.get('organisation_name') or ''} ({place}). "
                          + _plain(op.get("boarding_arrangements"))[:1000]).strip(),
        "submitter_nickname": "esc-bot",
        "status": "pending",
        "submission_origin": "agent",
        "review_stage": "agent_queue",
    }

# ─── Çalıştırma ──────────────────────────────────────────────────────────────

def run(dry_run, limit, today=None):
    today = today or date.today()
    mode = "DRY-RUN — DB'ye yazılmaz" if dry_run else "CANLI — submissions'a yazılır"
    print(f"🚀 ESC (Avrupa Gençlik Portalı) scraper — {mode}")
    if not dry_run and not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY yok (.env). Canlı mod için gerekli.")
        return 1

    try:
        opportunities = fetch_open_opportunities()
    except (requests.RequestException, ValueError) as exc:
        # Kaynak geçici olarak kapalı: haftalık keşfin diğer kaynaklarını düşürme.
        print(f"::warning title=ESC portalı erişilemedi::{exc}")
        return 0

    in_scope, skipped_scope = [], {}
    for op in opportunities:
        reason = scope_reason(op, today)
        if reason:
            skipped_scope[reason] = skipped_scope.get(reason, 0) + 1
        else:
            in_scope.append(op)
    print(f"  {len(opportunities)} açık ilan · {len(in_scope)} kapsamda")
    for reason, count in sorted(skipped_scope.items(), key=lambda kv: -kv[1]):
        print(f"    ↷ {count:4d} × {reason}")
    print("─" * 60)

    stats = {"processed": 0, "previewed": 0, "added": 0, "skipped": 0, "errors": 0}
    for op in in_scope:
        if limit and stats["processed"] >= limit:
            break
        stats["processed"] += 1
        record = build_record(op)
        if not dry_run and url_exists(record["url"]):
            stats["skipped"] += 1
            continue
        blockers = candidate_blockers(record, today=today)
        if blockers:
            stats["errors"] += 1
            print(f"  🚫 kalite kapısı: {record['title'][:55]} — {'; '.join(blockers)}")
            continue
        if dry_run:
            stats["previewed"] += 1
            print(f"  🧪 {record['title'][:60]}  [{record['host_countries'][0]}, "
                  f"son başvuru {record['deadline_text'] or 'sürekli'}]")
            if stats["previewed"] <= 2:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            continue
        ok, detay = insert(record)
        if ok:
            stats["added"] += 1
            print(f"  ✅ pending: {record['title'][:55]}")
        else:
            stats["errors"] += 1
            print(f"  ❌ insert hatası: {record['title'][:45]} — {detay}")

    print("\n" + "─" * 60)
    print(f"İşlenen: {stats['processed']}")
    if dry_run:
        print(f"Önizlenen: {stats['previewed']}")
    else:
        print(f"Eklendi: {stats['added']} pending · Atlandı(kopya): {stats['skipped']}")
    print(f"Hata/kapı: {stats['errors']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="ESC gönüllülük ilanları scraper")
    ap.add_argument("--dry-run", action="store_true", help="DB'ye yazma, kayıtları göster")
    ap.add_argument("--limit", type=int, help="en fazla bu kadar ilan işle")
    args = ap.parse_args()
    sys.exit(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
