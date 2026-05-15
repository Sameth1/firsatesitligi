"""
idealist.org Gönüllülük Scraper
================================
idealist.org'dan gönüllülük fırsatlarını çekip
Supabase opportunities tablosuna yazar.

Kullanım:
  pip install requests python-dotenv
  python idealist_scraper.py

Ortam değişkenleri (.env dosyası):
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_SERVICE_KEY=eyJ...
"""

import os
import time
import json
import requests
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

# ─── Ayarlar ─────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # .env'e koy

# idealist'in arka planda kullandığı JSON endpoint
# (F12 > Network > Fetch/XHR yaparak bulundu)
IDEALIST_SEARCH_URL = "https://www.idealist.org/api/v1/search"

# Arama parametreleri — gönüllülük + uluslararası fırsatlar
SEARCH_PARAMS = {
    "type": "VOLOP",          # VOLunteer OPportunity
    "q": "",                  # boş = hepsi
    "location": "",           # boş = global
    "remoteOk": "true",       # remote da dahil
    "pageSize": 50,
    "page": 1,
}

# DB'deki volunteering category_id — kendi DB'nden kontrol et
VOLUNTEERING_CATEGORY_ID = "dfe93634-98a2-48d7-b486-73b8c9631bcc"  # ← değiştir

# ─── Supabase yardımcıları ────────────────────────────────────────────────────

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # upsert için
    }


def url_already_exists(official_url: str) -> bool:
    """Aynı URL daha önce eklendi mi kontrol et."""
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=supabase_headers(),
        params={
            "official_url": f"eq.{official_url}",
            "select": "id",
            "limit": 1,
        },
    )
    return len(res.json()) > 0


def insert_opportunity(record: dict) -> bool:
    """Supabase'e yeni kayıt ekle. True = başarılı."""
    res = requests.post(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=supabase_headers(),
        json=record,
    )
    return res.status_code in (200, 201)


# ─── idealist çekici ─────────────────────────────────────────────────────────

def fetch_idealist_page(page: int) -> dict:
    """Bir sayfa veri çek."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.idealist.org/en/volunteer",
    }
    params = {**SEARCH_PARAMS, "page": page}

    res = requests.get(IDEALIST_SEARCH_URL, headers=headers, params=params, timeout=15)

    if res.status_code != 200:
        print(f"  ⚠ HTTP {res.status_code} — sayfa {page}")
        return {}

    return res.json()


# ─── Veri dönüştürücü ────────────────────────────────────────────────────────

def map_to_opportunity(item: dict):
    """
    idealist JSON kaydını opportunities tablosu formatına çevir.
    Zorunlu alan eksikse None döner.
    """
    title = item.get("name") or item.get("title")
    url   = item.get("url") or item.get("canonicalUrl")

    if not title or not url:
        return None

    # Tam URL'yi garantile
    if not url.startswith("http"):
        url = f"https://www.idealist.org{url}"

    # Lokasyon → host_countries
    location = item.get("location") or {}
    country_code = location.get("country") or location.get("countryCode") or "*"
    host_countries = [country_code.upper()] if country_code != "*" else ["*"]

    # Deadline
    deadline_raw = item.get("deadline") or item.get("applicationDeadline")
    deadline = None
    if deadline_raw:
        try:
            deadline = str(date.fromisoformat(deadline_raw[:10]))
        except Exception:
            pass

    # Açıklama
    description = (
        item.get("description")
        or item.get("body")
        or ""
    )
    # Çok uzunsa kırp
    eligibility_notes = description[:800] if description else None

    return {
        "title":              title,
        "official_url":       url,
        "deadline":           deadline,
        "deadline_notes":     "idealist.org'dan otomatik çekildi" if deadline else "Sürekli açık",
        "host_countries":     host_countries,
        "target_countries":   ["all"],
        "eligible_citizenships": ["all"],
        "target_fields":      ["all"],
        "study_level":        ["any"],
        "age_min":            None,
        "age_max":            None,
        "language_requirement": "İngilizce",
        "eligibility_notes":  eligibility_notes,
        "funding_type":       "free",
        "funding_notes":      "Gönüllülük — ücret alınmaz",
        "category_id":        VOLUNTEERING_CATEGORY_ID,
        "is_featured":        False,
        "is_active":          True,
        "is_verified":        False,  # otomatik eklenen → manuel doğrulama bekliyor
    }


# ─── Ana akış ────────────────────────────────────────────────────────────────

def run():
    print("🚀 idealist.org scraper başladı")
    print(f"   Supabase: {SUPABASE_URL}")
    print()

    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY bulunamadı. .env dosyasını kontrol et.")
        return

    added   = 0
    skipped = 0
    errors  = 0
    page    = 1

    while True:
        print(f"📄 Sayfa {page} çekiliyor...")
        data = fetch_idealist_page(page)

        if not data:
            print("  Veri gelmedi, duruyorum.")
            break

        items = data.get("results") or data.get("hits") or data.get("data") or []

        if not items:
            print("  Sonuç bitti.")
            break

        for item in items:
            record = map_to_opportunity(item)

            if not record:
                errors += 1
                continue

            if url_already_exists(record["official_url"]):
                skipped += 1
                continue

            ok = insert_opportunity(record)
            if ok:
                added += 1
                print(f"  ✅ Eklendi: {record['title'][:60]}")
            else:
                errors += 1
                print(f"  ❌ Hata:    {record['title'][:60]}")

        # Sonraki sayfa var mı?
        total_pages = data.get("pageCount") or data.get("totalPages") or 1
        if page >= total_pages or page >= 10:  # max 10 sayfa = 500 kayıt
            break

        page += 1
        time.sleep(2)  # idealist'e nazik ol

    print()
    print("─" * 40)
    print(f"✅ Eklendi  : {added}")
    print(f"⏭  Atlandı  : {skipped} (zaten vardı)")
    print(f"❌ Hata     : {errors}")
    print("─" * 40)
    print("Bitti!")


if __name__ == "__main__":
    run()
