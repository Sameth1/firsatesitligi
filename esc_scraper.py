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
  • faaliyet bitmemiş ve kesin (esnek olmayan) başlangıç tarihi geçmemiş —
    portal bitmiş ilanları da "open" ve "son tarih yok" gösterebiliyor
    (Ekim 2026: "ESC Volunteering Team in Portugal – August 2026")
  • yalnız gönüllülük ve insani yardım gönüllülüğü kolları

Yaş, dil, uyruk gibi kullanıcı filtreleri burada TAHMİN EDİLMEZ; ajan sayfadan
birebir alıntıyla belirler. (Örnek: API bir ilanda Türkiye'yi listeliyor ama
profil "citizen of an EU country" diyor — ajanın katı uyruk taraması bu
çelişkiyi yakalar.)

SENKRONİZASYON (--sync): son tarihsiz ilanların yayından kalkacağı bir tarih
yok; ilan portalda kapanınca ya da faaliyet bitince bizde de kalkmalı. --sync
güncel açık ilan listesini çeker ve
  • kapsam dışına düşen bekleyen esc-bot kayıtlarını reddeder,
  • kapsam dışına düşen yayındaki ESC fırsatlarını pasifleştirir,
  • yayındaki ESC fırsatlarının başvuru linkini doğrudan hedefe çeker:
    kurumun açıklamada verdiği form varsa o, yoksa ilanın Apply butonlu
    sayfası (application_links.KNOWN_APPLY_PAGES).
Ajan çalışmadan önce her triage koşusunda çalışır.

Kullanım:
  python esc_scraper.py --dry-run --limit 5
  python esc_scraper.py                  # canlı — submissions'a yaz
  python esc_scraper.py --sync [--dry-run]

.env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone

import requests
from dotenv import load_dotenv

from application_links import CLOSED_FORM_REASON, resolve_application_route
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
# Portal ilan sayfasını /placement/ adresinden /opportunity/ adresine yönlendiriyor.
DETAIL_ID_RE = re.compile(r"youth\.europa\.eu/solidarity/(?:placement|opportunity)/(\d+)")
# Portal yanıtı kısmi gelirse (bakım, hata) senkronizasyon her şeyi kapsam
# dışı sanıp yayındaki ilanları silmesin. Ekim 2026'da ~2600 açık ilan var.
MIN_OPEN_FOR_SYNC = 500
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
    return _activity_reason(op, today)


def _iso_day(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _activity_reason(op, today):
    """Faaliyet tarihleri katılımı imkânsız kılıyorsa nedeni."""
    end = _iso_day(op.get("date_end"))
    if end and end < today:
        return "faaliyet bitmiş"
    start = _iso_day(op.get("date_start"))
    if start and start < today and op.get("date_flexibility") == "precise":
        return "kesin başlangıç tarihi geçmiş"
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

# ─── Senkronizasyon ──────────────────────────────────────────────────────────

def detail_id(*urls):
    for url in urls:
        match = DETAIL_ID_RE.search(url or "")
        if match:
            return match.group(1)
    return None


def sync_decisions(rows, open_by_id, today, url_fields):
    """(satır, neden) — güncel listede kapsam dışı kalan satırlar."""
    out = []
    for row in rows:
        op_id = detail_id(*(row.get(field) for field in url_fields))
        if not op_id:
            continue
        op = open_by_id.get(op_id)
        reason = ("ilan portalda artık açık değil" if op is None
                  else scope_reason(op, today))
        if reason:
            out.append((row, reason))
    return out


def _sb_get(table, params):
    res = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(),
                       params=params, timeout=30)
    res.raise_for_status()
    return res.json()


def _sb_patch(table, row_id, patch):
    res = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(),
                         params={"id": f"eq.{row_id}"}, json=patch, timeout=30)
    return res.status_code in (200, 204), res.text[:160]


def sync(dry_run, today=None):
    today = today or date.today()
    print(f"🔄 ESC senkronizasyonu — {'DRY-RUN' if dry_run else 'CANLI'}")
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY yok (.env).")
        return 1
    try:
        opportunities = fetch_open_opportunities()
    except (requests.RequestException, ValueError) as exc:
        print(f"::warning title=ESC portalı erişilemedi::{exc}")
        return 0
    if len(opportunities) < MIN_OPEN_FOR_SYNC:
        print(f"::warning title=ESC listesi eksik::yalnız {len(opportunities)} açık ilan "
              "geldi; senkronizasyon atlandı")
        return 0
    open_by_id = {str(op.get("id")): op for op in opportunities}
    now_iso = datetime.now(timezone.utc).isoformat()

    pending = _sb_get("submissions", {
        "submitter_nickname": "eq.esc-bot", "status": "eq.pending",
        "select": "id,title,url,details_url,source_url",
    })
    active = _sb_get("opportunities", {
        "submitted_by_nickname": "eq.esc-bot", "is_active": "eq.true",
        "select": ("id,title,official_url,details_url,source_url,"
                   "application_route_status,application_method"),
    })
    print(f"  {len(opportunities)} açık ilan · {len(pending)} bekleyen · {len(active)} yayında")

    failures = 0
    for row, reason in sync_decisions(pending, open_by_id, today,
                                      ("url", "details_url", "source_url")):
        print(f"  🚫 bekleyen reddedildi: {row['title'][:55]} — {reason}")
        if dry_run:
            continue
        ok, detail = _sb_patch("submissions", row["id"], {
            "status": "rejected",
            "admin_note": f"[ajan] RED — ESC: {reason}",
            "reviewed_at": now_iso,
            "review_stage": "decided",
        })
        failures += 0 if ok else 1
        if not ok:
            print(f"    ❌ {detail}")
    for row, reason in sync_decisions(active, open_by_id, today,
                                      ("official_url", "details_url", "source_url")):
        print(f"  ⏹ yayından kaldırıldı: {row['title'][:55]} — {reason}")
        if dry_run:
            continue
        ok, detail = _sb_patch("opportunities", row["id"], {
            "is_active": False, "last_verified_at": now_iso,
        })
        failures += 0 if ok else 1
        if not ok:
            print(f"    ❌ {detail}")
    closing = {row["id"] for row, _ in sync_decisions(
        active, open_by_id, today, ("official_url", "details_url", "source_url"))}
    for row in active:
        if row["id"] in closing:
            continue
        failures += upgrade_route(row, dry_run, now_iso)
    return 1 if failures else 0


def route_patch(route, now_iso):
    """Doğrulanmış rota → opportunities alanları."""
    return {
        "official_url": route.application_url,
        "details_url": route.details_url,
        "application_route_status": "verified",
        "application_method": route.application_method,
        "application_url_verified_at": now_iso,
        "application_url_check_status": route.status_code,
        "application_url_final": route.final_url,
        "application_url_evidence": route.evidence,
    }


def upgrade_route(row, dry_run, now_iso):
    """Yayındaki ilanı doğrudan başvuru hedefine bağlar; hata sayısı döner.

    Filtreler iki LLM denetimiyle zaten doğrulanmış; burada yalnız başvuru
    linki değişiyor ve o da sayfadaki kanıtla (form linki ya da Apply butonu)
    deterministik doğrulanıyor."""
    if row.get("application_route_status") == "verified":
        return 0
    start = row.get("source_url") or row.get("details_url") or row.get("official_url")
    route = resolve_application_route(start, max_hops=0)
    if route.reason == CLOSED_FORM_REASON:
        # Kurum başvuruyu yalnız bu forma yönlendiriyor ve form kapanmış.
        print(f"  ⏹ yayından kaldırıldı: {row['title'][:55]} — {route.reason}")
        if dry_run:
            return 0
        ok, detail = _sb_patch("opportunities", row["id"], {
            "is_active": False, "last_verified_at": now_iso,
        })
    elif route.verified and route.application_url:
        print(f"  🔗 doğrudan başvuru: {row['title'][:50]} → "
              f"{route.application_method} {route.application_url[:70]}")
        if dry_run:
            return 0
        ok, detail = _sb_patch("opportunities", row["id"], route_patch(route, now_iso))
    else:
        print(f"  · rota doğrulanamadı: {row['title'][:55]} — {route.reason}")
        return 0
    if not ok:
        print(f"    ❌ {detail}")
    time.sleep(CRAWL_DELAY)
    return 0 if ok else 1

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
    ap.add_argument("--sync", action="store_true",
                    help="kapsam dışına düşen bekleyenleri reddet, yayındakileri kaldır")
    args = ap.parse_args()
    if args.sync:
        sys.exit(sync(dry_run=args.dry_run))
    sys.exit(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
