"""
Programmatik link-audit
========================
Her aktif opportunity'nin official_url'ine GET atar,
sonucu opportunities tablosunun last_url_check_* kolonlarına yazar.
Admin panelindeki "Sıradaki N kaydı kontrol et" butonunun otomasyonudur.

Kullanım:
  python link_audit_runner.py
"""

import os
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch_targets(only_unchecked=True):
    """Kontrol edilecek aktif kayıtları çek."""
    params = {
        "select": "id,title,official_url,last_url_check_at",
        "is_active": "eq.true",
        "order": "last_url_check_at.asc.nullsfirst,title.asc",
    }
    if only_unchecked:
        params["last_url_check_at"] = "is.null"
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers=HEADERS_SB,
        params=params,
    )
    return res.json() if res.status_code == 200 else []


def check_url(url):
    """URL'ye GET at, sonuç tuple'ı döndür: (status, error, final_url)."""
    if not url or not url.startswith(("http://", "https://")):
        return (None, "Geçersiz URL", None)
    try:
        res = requests.get(
            url,
            headers={"User-Agent": UA, "Accept": "*/*"},
            timeout=15,
            allow_redirects=True,
        )
        return (res.status_code, None, res.url if res.url != url else None)
    except requests.exceptions.SSLError as e:
        return (None, f"SSL: {str(e)[:120]}", None)
    except requests.exceptions.ConnectionError as e:
        return (None, f"Bağlantı: {str(e)[:120]}", None)
    except requests.exceptions.Timeout:
        return (None, "Zaman aşımı (15s)", None)
    except Exception as e:
        return (None, f"{type(e).__name__}: {str(e)[:120]}", None)


def write_result(opp_id, http_status, error, final_url):
    """Sonucu opportunities tablosuna yaz."""
    payload = {
        "last_url_check_at": datetime.now(timezone.utc).isoformat(),
        "last_url_check_status": http_status,
        "last_url_check_error": error,
        "last_url_check_final_url": final_url,
    }
    res = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={**HEADERS_SB, "Prefer": "return=minimal"},
        params={"id": f"eq.{opp_id}"},
        json=payload,
    )
    return res.status_code in (200, 204)


def run():
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY yok"); return

    targets = fetch_targets(only_unchecked=True)
    print(f"🔎 {len(targets)} kayıt kontrol edilecek (last_url_check_at=null)")
    print()

    ok_count = err_count = redirect_count = 0
    for i, t in enumerate(targets, 1):
        title = (t["title"] or "")[:50]
        url = t["official_url"]
        status, error, final = check_url(url)

        write_result(t["id"], status, error, final)

        if error:
            err_count += 1
            tag = f"❌ {error[:40]}"
        elif status and 200 <= status < 400:
            ok_count += 1
            tag = f"✅ {status}"
            if final:
                redirect_count += 1
                tag += f" → redirect"
        else:
            err_count += 1
            tag = f"⚠ {status}"

        print(f"  [{i:>2}/{len(targets)}] {tag:<25} {title}")
        time.sleep(0.5)

    print()
    print("─" * 50)
    print(f"✅ Yaşıyor   : {ok_count}")
    print(f"  ↳ redirect: {redirect_count}")
    print(f"❌ Sorunlu   : {err_count}")
    print("─" * 50)


if __name__ == "__main__":
    run()
