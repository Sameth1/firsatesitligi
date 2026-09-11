"""
Fırsat Sağlığı ve Link Denetimi Otomasyonu — scripts/audit_opportunities.py
===========================================================================
Yayındaki (is_active=true) fırsatları periyodik olarak denetler:
  1. Süresi Geçenler: deadline < bugün olan fırsatları is_active=false yapar.
  2. Ölü Bağlantılar: HTTP 404/410 dönen resmi başvuru linklerini is_active=false yapar.
  3. Kapanmış Formlar: Google Forms '/closedform' veya sayfa içi 'application closed'
     gibi sinyaller içeren formları tespit edip is_active=false yapar.
  4. Durum Güncellemesi: opportunities tablosunun last_url_check_* ve last_verified_at
     kolonlarını günceller; admin panelindeki link-audit ekranını besler.
  5. GitHub Actions: $GITHUB_STEP_SUMMARY ortam değişkeni varsa Markdown rapor üretir.

Kullanım:
  python scripts/audit_opportunities.py                 # En eski 100 kaydı denetle
  python scripts/audit_opportunities.py --limit 10      # İlk 10 kayıt
  python scripts/audit_opportunities.py --check-all     # Tüm aktif fırsatları denetle
  python scripts/audit_opportunities.py --dry-run       # DB'ye yazma, raporla
  python scripts/audit_opportunities.py --skip-url-check # Yalnızca tarih kontrolü yap
"""

import os
import re
import sys
import time
import argparse
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

HTTP_REQUEST_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

# Kapanmış form / başvuru sinyalleri
CLOSED_FORM_SIGNALS = [
    "no longer accepting responses",
    "this form is no longer accepting responses",
    "this opportunity has ended",
    "application closed",
    "applications closed",
    "applications are now closed",
    "the application period is now closed",
    "deadline passed",
    "başvuru kapandı",
    "başvurular kapandı",
    "form is closed",
]

TR_AYLAR = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5,
    "mayis": 5, "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8,
    "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11,
    "aralık": 12, "aralik": 12,
}

EN_AYLAR = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_deadline(text: str | None) -> date | None:
    """Metin içinden tarih çıkarır (ISO, GG.AA.YYYY veya Türkçe/İngilizce ay adı)."""
    if not text:
        return None
    t = str(text).lower().strip()
    y = mo = d = None

    # 1. ISO YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    # 2. Noktalı GG.AA.YYYY
    if d is None:
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
        if m:
            d, mo, y = (int(g) for g in m.groups())
    # 3. Türkçe ay: 15 mayıs 2026
    if d is None:
        m = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4})", t)
        if m and m.group(2) in TR_AYLAR:
            d, mo, y = int(m.group(1)), TR_AYLAR[m.group(2)], int(m.group(3))
    # 4. İngilizce ay-önce: June 25, 2026
    if d is None:
        m = re.search(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", t)
        if m and m.group(1) in EN_AYLAR:
            mo, d, y = EN_AYLAR[m.group(1)], int(m.group(2)), int(m.group(3))
    # 5. İngilizce gün-önce: 25 June 2026
    if d is None:
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+),?\s+(\d{4})", t)
        if m and m.group(2) in EN_AYLAR:
            d, mo, y = int(m.group(1)), EN_AYLAR[m.group(2)], int(m.group(3))

    if d and mo and y:
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


def get_opportunity_deadline(opp: dict) -> date | None:
    """Fırsatın son başvuru tarihini date nesnesine çevirir."""
    raw = opp.get("deadline")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    return parse_deadline(opp.get("deadline_notes"))


def patch_opportunity(opp_id: str, patch: dict, dry_run: bool = False) -> bool:
    """opportunities tablosuna PATCH atar."""
    if dry_run:
        return True
    res = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={**HEADERS_SB, "Prefer": "return=minimal"},
        params={"id": f"eq.{opp_id}"},
        json=patch,
        timeout=20,
    )
    return res.status_code in (200, 204)


def fetch_active_opportunities() -> list[dict]:
    """Yayındaki tüm fırsatları çeker."""
    params = {
        "is_active": "eq.true",
        "select": "id,title,official_url,deadline,deadline_notes,last_url_check_at,last_url_check_status",
        "order": "last_url_check_at.asc.nullsfirst,title.asc",
        "limit": "5000",
    }
    res = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities", headers=HEADERS_SB, params=params, timeout=30)
    res.raise_for_status()
    return res.json()


def check_url_health(url: str, timeout: int = 15) -> tuple[int | None, str | None, str | None, str | None]:
    """
    URL'ye GET atar.
    Döndürür: (status_code, error_message, final_url, closed_signal)
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None, "Geçersiz URL şeması", None, None

    try:
        res = requests.get(
            url,
            headers=HTTP_REQUEST_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        final_url = res.url if res.url != url else None
        check_url_lower = (res.url or url).lower()

        # Google Forms kapalı yönlendirmesi
        if "/closedform" in check_url_lower:
            return res.status_code, None, final_url, "closedform (Google Forms kapalı)"

        # 200 OK ise sayfa metninde kapalı form sinyali ara
        if res.status_code == 200 and "text" in res.headers.get("Content-Type", ""):
            try:
                soup = BeautifulSoup(res.text[:100_000], "html.parser")
                # Script ve stil etiketlerini temizle
                for tag in soup(["script", "style", "noscript"]):
                    tag.extract()
                text = soup.get_text(separator=" ", strip=True).lower()
                for sig in CLOSED_FORM_SIGNALS:
                    if sig in text:
                        return res.status_code, None, final_url, sig
            except Exception:
                pass

        return res.status_code, None, final_url, None

    except requests.exceptions.SSLError as e:
        return None, f"SSL Hatası: {str(e)[:100]}", None, None
    except requests.exceptions.ConnectionError as e:
        return None, f"Bağlantı Hatası: {str(e)[:100]}", None, None
    except requests.exceptions.Timeout:
        return None, f"Zaman Aşımı ({timeout}s)", None, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}", None, None


def write_github_summary(stats: dict, details: list[dict]):
    """GitHub Actions özet tablosu oluşturur."""
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    md = [
        "## 🔍 Fırsat Sağlığı ve Link Denetim Raporu",
        f"**Tarih:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "| Metrik | Sayı |",
        "| :--- | :---: |",
        f"| Toplam İncelenen Aktif Fırsat | **{stats['total_checked']}** |",
        f"| ⏰ Süresi Dolduğu İçin Kapatılan | **{stats['expired_deactivated']}** |",
        f"| 💀 Ölü Link (HTTP 404/410) Nedeniyle Kapatılan | **{stats['dead_deactivated']}** |",
        f"| 🚫 Kapanmış Form Sinyaliyle Kapatılan | **{stats['closed_deactivated']}** |",
        f"| ✅ Aktif ve Canlı Kalan (200 OK) | **{stats['alive_ok']}** |",
        f"| ⚠️ Geçici Hata / Bot Koruması (Kapatılmadı) | **{stats['transient_warnings']}** |",
        "",
    ]

    if details:
        md.append("### 📋 Pasifleştirilen Fırsatlar")
        md.append("| Fırsat Adı | Neden | Detay / Link |")
        md.append("| :--- | :--- | :--- |")
        for d in details:
            clean_title = d["title"].replace("|", "-")
            md.append(f"| {clean_title} | **{d['reason']}** | `{d['detail']}` |")
        md.append("")

    try:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
    except Exception as e:
        print(f"GitHub Summary yazılamadı: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Fırsat Sağlığı ve Link Denetimi Otomasyonu")
    parser.add_argument("--limit", type=int, default=100, help="Denetlenecek URL sınırı (varsayılan: 100)")
    parser.add_argument("--check-all", action="store_true", help="Tüm aktif fırsatları denetle")
    parser.add_argument("--dry-run", action="store_true", help="DB'ye yazma, yalnızca raporla")
    parser.add_argument("--skip-url-check", action="store_true", help="Sadece son başvuru tarihi taramasını yap")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP istek zaman aşımı (sn, varsayılan: 15)")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY eksik (.env kontrol edin)", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print("🚀 Fırsat Sağlığı ve Link Denetimi Başlatılıyor")
    mode_str = "🧪 DRY-RUN (Veritabanına yazılmaz)" if args.dry_run else "🟢 CANLI MOD (Veritabanı güncellenir)"
    print(f"Mod: {mode_str}")
    print("=" * 65)

    all_active = fetch_active_opportunities()
    print(f"🔎 Yayında toplam {len(all_active)} aktif fırsat bulundu.\n")

    now_iso = datetime.now(timezone.utc).isoformat()
    today = date.today()

    stats = {
        "total_checked": 0,
        "expired_deactivated": 0,
        "dead_deactivated": 0,
        "closed_deactivated": 0,
        "alive_ok": 0,
        "transient_warnings": 0,
    }
    deactivated_details = []

    # ─── AŞAMA 1: Son Başvuru Tarihi Taraması ────────────────────────────────────
    print("─── Aşama 1: Son Başvuru Tarihi Kontrolü ───")
    remaining_for_url_check = []

    for opp in all_active:
        dl = get_opportunity_deadline(opp)
        if dl is not None and dl < today:
            # Süresi geçmiş
            stats["expired_deactivated"] += 1
            print(f"  ⏰ [SÜRESİ DOLMUŞ ({dl})] {opp['title'][:55]}")
            patch_opportunity(
                opp["id"],
                {"is_active": False, "last_verified_at": now_iso},
                args.dry_run
            )
            deactivated_details.append({
                "title": opp["title"],
                "reason": "Süresi Doldu",
                "detail": f"Son tarih: {dl}",
            })
        else:
            remaining_for_url_check.append(opp)

    print(f"✓ Tarih taraması bitti: {stats['expired_deactivated']} fırsat süresi dolduğu için kapatıldı.\n")

    if args.skip_url_check:
        print("⏭️ --skip-url-check belirtildiği için URL canlılık denetimi atlandı.")
        write_github_summary(stats, deactivated_details)
        return

    # ─── AŞAMA 2: Link Sağlığı ve Kapalı Form Kontrolü ───────────────────────────
    targets = remaining_for_url_check if args.check_all else remaining_for_url_check[:args.limit]
    stats["total_checked"] = len(targets)

    print(f"─── Aşama 2: Link Canlılık ve Form Kontrolü ({len(targets)} kayıt) ───")

    for i, opp in enumerate(targets, 1):
        opp_id = opp["id"]
        title = opp.get("title") or "(Başlıksız)"
        url = (opp.get("official_url") or "").strip()

        if not url:
            print(f"  [{i:>2}/{len(targets)}] ⚠️ URL YOK: {title[:50]}")
            continue

        status, err, final_url, closed_sig = check_url_health(url, timeout=args.timeout)

        # 1. Kesin Ölü Bağlantı (HTTP 404, 410)
        if status in (404, 410):
            stats["dead_deactivated"] += 1
            err_msg = f"Ölü Bağlantı (HTTP {status})"
            print(f"  [{i:>2}/{len(targets)}] 💀 {err_msg}: {title[:45]}")
            patch_opportunity(
                opp_id,
                {
                    "is_active": False,
                    "last_url_check_at": now_iso,
                    "last_url_check_status": status,
                    "last_url_check_error": err_msg,
                    "last_url_check_final_url": final_url,
                    "last_verified_at": now_iso,
                },
                args.dry_run
            )
            deactivated_details.append({
                "title": title,
                "reason": f"Ölü Link ({status})",
                "detail": url,
            })

        # 2. Kapanmış Form Sinyali (Google Forms closedform / application closed)
        elif closed_sig:
            stats["closed_deactivated"] += 1
            err_msg = f"Kapanmış Form ({closed_sig})"
            print(f"  [{i:>2}/{len(targets)}] 🚫 {err_msg}: {title[:45]}")
            patch_opportunity(
                opp_id,
                {
                    "is_active": False,
                    "last_url_check_at": now_iso,
                    "last_url_check_status": status,
                    "last_url_check_error": err_msg,
                    "last_url_check_final_url": final_url,
                    "last_verified_at": now_iso,
                },
                args.dry_run
            )
            deactivated_details.append({
                "title": title,
                "reason": "Kapanmış Form",
                "detail": closed_sig,
            })

        # 3. Sağlam ve Canlı Link (HTTP 200, 301, 302 vb.)
        elif status is not None and 200 <= status < 400:
            stats["alive_ok"] += 1
            redir_note = " → Yönlendirme" if final_url else ""
            print(f"  [{i:>2}/{len(targets)}] ✅ {status}{redir_note}: {title[:50]}")
            patch_opportunity(
                opp_id,
                {
                    "last_url_check_at": now_iso,
                    "last_url_check_status": status,
                    "last_url_check_error": None,
                    "last_url_check_final_url": final_url,
                    "last_verified_at": now_iso,
                },
                args.dry_run
            )

        # 4. Geçici Ağ Hatası / Bot Koruması (Timeout, Cloudflare 403, 500 vb.) -> Kapatılmaz!
        else:
            stats["transient_warnings"] += 1
            warning_msg = err or f"HTTP {status}"
            print(f"  [{i:>2}/{len(targets)}] ⚠️ {warning_msg[:30]}: {title[:50]}")
            patch_opportunity(
                opp_id,
                {
                    "last_url_check_at": now_iso,
                    "last_url_check_status": status,
                    "last_url_check_error": warning_msg,
                    "last_url_check_final_url": final_url,
                },
                args.dry_run
            )

        # Sunucuları yormamak için kısa bekleme
        time.sleep(0.3)

    # ─── ÖZET VE RAPOR ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("📊 DENETİM ÖZETİ")
    print("=" * 65)
    print(f"Toplam Kontrol Edilen   : {stats['total_checked']}")
    print(f"⏰ Süresi Dolan (Kapatıldı): {stats['expired_deactivated']}")
    print(f"💀 Ölü Link (Kapatıldı)    : {stats['dead_deactivated']}")
    print(f"🚫 Kapalı Form (Kapatıldı) : {stats['closed_deactivated']}")
    print(f"✅ Canlı & Aktif (200 OK)  : {stats['alive_ok']}")
    print(f"⚠️ Geçici Uyarı (Açık Kaldı): {stats['transient_warnings']}")
    total_deact = stats['expired_deactivated'] + stats['dead_deactivated'] + stats['closed_deactivated']
    print(f"🛑 Toplam Pasifleştirilen  : {total_deact}")
    print("=" * 65)

    write_github_summary(stats, deactivated_details)


if __name__ == "__main__":
    main()
