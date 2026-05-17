"""
Submission Doğrulama Ajanı — validate_submissions.py
====================================================
İki katmanlı: önce ÜCRETSİZ heuristikler, sonra (sadece gerekirse) LLM.

KATMAN 1 — ücretsiz heuristikler (LLM çağrısı YOK):
  • Kopya URL  → URL zaten yayındaki bir fırsatta (opportunities) ya da bu
    partide daha önce işlendiyse REDDET (kopya).
  • Süresi geçmiş → submission.deadline_text geçmiş bir tarihe çözülüyorsa
    REDDET.
  • Ölü bağlantı → URL HTTP 404/410 dönüyorsa REDDET.

KATMAN 2 — LLM (yalnızca belirsiz vakalar):
  Sayfa HTTP 200 dönüyor ama açık/kapalı durumu net değil → Gemini'ye
  (ücretsiz tier) sorulur. Diğer HTTP durumları (403/429/5xx/timeout) LLM'e
  gitmez; belirsiz olarak pending bırakılır.

KARAR:
  kapalı / kategori-dışı → otomatik RED (submissions'a doğrudan PATCH; service
    key RLS'i bypass eder).
  açık + uygun + güven yüksek/orta → OTOMATİK ONAY: agent_approve_submission
    RPC'si (migration 094) service key ile çağrılır — submission 'approved'
    olur ve opportunities'e taşınır. RPC başarısız olursa öneri olarak
    işaretlenip 'pending' bırakılır (insan panelden onaylar).
  belirsiz → admin_note; pending kalır.

Kullanım:
  pip install requests beautifulsoup4 python-dotenv      # ek SDK gerekmez
  python validate_submissions.py                # tüm pending'leri işle
  python validate_submissions.py --limit 10     # ilk 10
  python validate_submissions.py --dry-run      # DB'ye yazma, kararı göster

.env:
  SUPABASE_URL=...
  SUPABASE_SERVICE_ROLE_KEY=...
  GEMINI_API_KEY=...        # https://aistudio.google.com/apikey (ücretsiz)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

SUPABASE_URL = os.getenv(
    "SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co"
).rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Ücretsiz tier flash modeli. Güncel modeli doğrulamak / değiştirmek için:
#   GET https://generativelanguage.googleapis.com/v1beta/models?key=API_KEY
# gemini-2.0-flash de çalışır; daha yeni gemini-3-*-flash modelleri de var.
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
GEMINI_MIN_INTERVAL = 5.0     # çağrılar arası bekleme — ücretsiz tier RPM sınırı

AGENT_MARKER = "[ajan]"       # admin_note öneki — tekrar çalıştırmada atlamak için
PAGE_CHAR_LIMIT = 6000

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr,en;q=0.8",
}

TR_AYLAR = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5,
    "mayis": 5, "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8,
    "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11,
    "aralık": 12, "aralik": 12,
}

SYSTEM_PROMPT = """Sen "Fırsat Eşitliği" platformunun submission doğrulama ajanısın. Bu platform Türkiye'deki gençlere yurt dışı burs, staj, gönüllülük, yaz okulu, gençlik projesi ve değişim programı gibi ÜCRETSİZ veya FONLU fırsatları toplar.

Sana bir submission'ın bilgileri ve orijinal sayfasının metni verilir. Üç şeyi değerlendirirsin:

1) durum — Fırsat hâlâ başvuruya açık mı?
   - "acik": Gelecekte bir son başvuru tarihi, aktif başvuru formu/linki ya da "başvurular devam ediyor / applications open / now accepting applications" benzeri ifade var.
   - "kapali": "Başvurular kapandı", "son başvuru tarihi geçti", "applications closed", "deadline has passed", "this programme has ended" benzeri net ifade var; VEYA sayfadaki tek tarih(ler) açıkça geçmişte ve yeni dönem duyurulmamış; VEYA sayfa fırsatın artık mevcut olmadığını gösteriyor.
   - "belirsiz": Sayfa açıldı ama açık mı kapalı mı metinden çıkmıyor.

2) kategori_uygun — Sayfa gerçekten bu fırsatı anlatıyor mu ve platforma uygun mu?
   - true: Gerçek bir fırsat ilanı, belirtilen kategoriyle makul örtüşüyor ve gencin ücret ödemesini gerektirmiyor.
   - false: Fırsat ilanı değil (genel blog, ana sayfa, giriş sayfası, alakasız ürün/hizmet, hata sayfası); VEYA ücretli/ticari program; VEYA kategoriyle hiç ilgisi yok.

3) guven — Kararının kanıta dayanma gücü: "yuksek" (açık ve doğrudan kanıt), "orta" (dolaylı/kısmi), "dusuk" (zayıf veya çelişkili).

KRİTİK: "kapali" ya da kategori_uygun=false kararın submission'ın OTOMATİK REDDEDİLMESİNE yol açar. Bu olumsuz kararları yalnızca metinde açık kanıt varken ver. Emin değilsen "belirsiz" + düşük/orta güven seç — yanlış reddetmektense insana bırak.

ÇIKTI: Yanıtını yalnızca şu alanlara sahip TEK bir JSON nesnesi olarak ver. Markdown, ``` işareti veya açıklama EKLEME:
{"durum": "acik|kapali|belirsiz", "kategori_uygun": true|false, "guven": "yuksek|orta|dusuk", "gerekce": "<kararını dayandıran kanıtı belirten Türkçe tek cümle>"}"""


# ─── Supabase ─────────────────────────────────────────────────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_pending(limit=None):
    """pending submission'ları çeker. Service key RLS'i bypass eder."""
    params = {
        "status": "eq.pending",
        "select": "id,title,url,category_slug,eligibility_notes,deadline_text,admin_note",
        "order": "created_at.asc",
    }
    res = requests.get(f"{SUPABASE_URL}/rest/v1/submissions",
                       headers=sb_headers(), params=params, timeout=20)
    res.raise_for_status()
    rows = res.json()
    # Ajanın daha önce işlediklerini atla — idempotent
    rows = [r for r in rows if not (r.get("admin_note") or "").startswith(AGENT_MARKER)]
    return rows[:limit] if limit else rows


def _norm_url(u):
    return (u or "").strip().rstrip("/").lower()


def fetch_known_urls():
    """opportunities tablosundaki official_url'leri normalize küme olarak döndürür
    — kopya submission tespiti için. Hata olursa boş küme (kopya kontrolü
    devre dışı kalır ama çalıştırma durmaz)."""
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/opportunities",
            headers=sb_headers(),
            params={"select": "official_url", "limit": "5000"},
            timeout=20,
        )
        res.raise_for_status()
        return {_norm_url(r["official_url"]) for r in res.json() if r.get("official_url")}
    except requests.exceptions.RequestException as e:
        print(f"Uyarı: mevcut URL listesi çekilemedi — kopya kontrolü zayıf ({e})")
        return set()


def apply_decision(sub, eylem, gerekce, dry_run):
    """Kararı submissions tablosuna yazar.
      reddet -> status=rejected + admin_note + reviewed_at
      onayla -> sadece admin_note PATCH'lenir; status / created_opportunity_id /
                reviewed_at zaten agent_approve_submission RPC'si tarafından
                yazılmıştır (bkz. approve_submission()).
      oner / belirsiz -> sadece admin_note; status 'pending' kalır.
    reviewed_by NULL bırakılır — 'insan değil ajan işledi' sinyali."""
    if eylem == "reddet":
        note = f"{AGENT_MARKER} RED — {gerekce}"
        patch = {
            "status": "rejected",
            "admin_note": note,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    elif eylem == "onayla":
        note = f"{AGENT_MARKER} OTOMATİK ONAY — {gerekce}"
        patch = {"admin_note": note}
    elif eylem == "oner":
        note = f"{AGENT_MARKER} ÖNERİ: onaya uygun — {gerekce}"
        patch = {"admin_note": note}
    else:
        note = f"{AGENT_MARKER} BELİRSİZ: elle bak — {gerekce}"
        patch = {"admin_note": note}

    if not dry_run:
        res = requests.patch(
            f"{SUPABASE_URL}/rest/v1/submissions",
            headers={**sb_headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{sub['id']}"},
            json=patch, timeout=15,
        )
        res.raise_for_status()
    return note


def approve_submission(sub, dry_run):
    """agent_approve_submission RPC'sini service key ile çağırır — submission'ı
    'approved' işaretler, opportunities'e taşır, belgelerini ekler.
    (ok: bool, detay: str) döndürür.

    RPC (migration 094) admin guard'sızdır; EXECUTE izni yalnızca service_role'a
    verildiği için bu script çağırabilir. Hata (kategori bulunamadı, ağ sorunu,
    RPC henüz uygulanmamış vb.) çalıştırmayı durdurmaz — çağıran güvenli tarafa
    düşer: submission'ı öneri olarak 'pending' bırakır."""
    if dry_run:
        return True, "(dry-run — RPC çağrılmadı)"
    try:
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/agent_approve_submission",
            headers=sb_headers(),
            json={"p_id": sub["id"]},
            timeout=20,
        )
    except requests.exceptions.RequestException as e:
        return False, f"ağ hatası: {e}"
    if res.status_code != 200:
        # 404 → RPC migration'ı uygulanmamış; 400 → RPC içi exception
        # (ör. 'Kategori bulunamadı'). Her durumda gerekçe res.text'te.
        return False, f"RPC HTTP {res.status_code}: {res.text[:200]}"
    try:
        opp_id = res.json().get("opportunity_id")
    except (ValueError, AttributeError):
        opp_id = None
    return True, f"opportunity_id={opp_id}" if opp_id else "onaylandı"


# ─── Heuristikler ─────────────────────────────────────────────────────────────

def parse_deadline(text):
    """submission.deadline_text içinden bir tarih çıkarır (date veya None).
    ISO / noktalı / Türkçe-ay formatlarını dener."""
    if not text:
        return None
    t = str(text).lower()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
        if m:
            d, mo, y = (int(g) for g in m.groups())
        else:
            m = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4})", t)
            if not m or m.group(2) not in TR_AYLAR:
                return None
            d, mo, y = int(m.group(1)), TR_AYLAR[m.group(2)], int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def fetch_page(url):
    """(status_code|None, final_url, html|None, error|None)."""
    try:
        res = requests.get(url, headers=HTTP_HEADERS, timeout=20, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        return None, url, None, str(e)
    return res.status_code, res.url, res.text, None


def page_to_text(html):
    """HTML -> okunabilir düz metin; nav/footer/script atılır, kısaltılır."""
    soup = BeautifulSoup(html, "html.parser")
    for sel in ("script", "style", "nav", "footer", "header",
                "aside", "noscript", "form", "iframe"):
        for el in soup.select(sel):
            el.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]
    return "\n".join(lines)[:PAGE_CHAR_LIMIT]


# ─── LLM katmanı (Gemini, ücretsiz tier) ──────────────────────────────────────

def _parse_verdict(text):
    """Gemini'nin metin yanıtından JSON kararı çıkarır (savunmacı)."""
    t = (text or "").strip()
    if t.startswith("```"):                       # ```json ... ``` sarmalını söker
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    try:
        v = json.loads(t)
    except (json.JSONDecodeError, TypeError):
        return None
    durum = v.get("durum")
    if durum not in ("acik", "kapali", "belirsiz"):
        return None
    guven = v.get("guven")
    if guven not in ("yuksek", "orta", "dusuk"):
        guven = "dusuk"                            # tanınmayan güven → temkinli
    return {
        "durum": durum,
        "kategori_uygun": bool(v.get("kategori_uygun", False)),
        "guven": guven,
        "gerekce": (str(v.get("gerekce") or "").strip()[:300] or "(gerekçe yok)"),
    }


def judge_with_gemini(sub, url, http_note, page_text):
    """Gemini'ye sorar, karar dict'i döndürür (hata → None)."""
    user_text = (
        "SUBMISSION\n"
        f"Başlık: {sub.get('title') or '(yok)'}\n"
        f"Kategori slug: {sub.get('category_slug') or '(belirtilmemiş)'}\n"
        f"Kaydedilen son başvuru metni: {sub.get('deadline_text') or '(yok)'}\n"
        f"Submitter eligibility notu: {(sub.get('eligibility_notes') or '(yok)')[:400]}\n"
        f"Orijinal URL: {url}\n"
        f"HTTP: {http_note}\n\n"
        f"SAYFA METNİ (kısaltılmış):\n{page_text}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_text}]}],
        "generationConfig": {
            # responseMimeType: uzun süredir stabil — JSON çıktıyı zorlar.
            "responseMimeType": "application/json",
            "temperature": 0,
            "maxOutputTokens": 600,
        },
    }
    res = None
    for attempt in range(3):
        try:
            res = requests.post(
                GEMINI_ENDPOINT,
                params={"key": GEMINI_API_KEY},
                json=body, timeout=45,
            )
        except requests.exceptions.RequestException as e:
            print(f"  ! Gemini ağ hatası: {e}")
            return None
        if res.status_code == 429:               # ücretsiz tier RPM aşıldı
            wait = 20 * (attempt + 1)
            print(f"  Gemini 429 (rate limit) — {wait}s bekleniyor...")
            time.sleep(wait)
            continue
        break
    if res is None or res.status_code != 200:
        detail = res.text[:200] if res is not None else "yanıt yok"
        print(f"  ! Gemini HTTP {getattr(res, 'status_code', '?')}: {detail}")
        return None
    try:
        text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError):
        print("  ! Gemini yanıtı beklenen yapıda değil (safety bloğu olabilir)")
        return None
    return _parse_verdict(text)


def decide(verdict):
    """Karar dict'i -> (eylem, gerekce). eylem: reddet | onayla | belirsiz.
    Otomatik ONAY yalnızca açık + kategori-uygun + güven yüksek/orta'da;
    otomatik RED yalnızca yüksek/orta güvenli net olumsuzlarda."""
    if verdict["guven"] == "dusuk":
        return "belirsiz", verdict["gerekce"]
    if verdict["durum"] == "kapali" and verdict["guven"] in ("yuksek", "orta"):
        return "reddet", verdict["gerekce"]
    if not verdict["kategori_uygun"] and verdict["guven"] == "yuksek":
        return "reddet", verdict["gerekce"]
    if (verdict["durum"] == "acik" and verdict["kategori_uygun"]
            and verdict["guven"] in ("yuksek", "orta")):
        return "onayla", verdict["gerekce"]
    return "belirsiz", verdict["gerekce"]


# ─── Akış ─────────────────────────────────────────────────────────────────────

def process(sub, dry_run, known_urls, seen_urls, stats):
    """Tek submission — heuristikler, gerekirse Gemini. Tally etiketi döndürür."""
    print(f"\n• {(sub.get('title') or '(başlıksız)')[:60]}")
    url = (sub.get("url") or "").strip()
    if not url:
        apply_decision(sub, "belirsiz", "Submission'da URL yok", dry_run)
        print("  URL yok → BELİRSİZ")
        return "belirsiz"
    print(f"  URL: {url}")
    norm = _norm_url(url)

    # Heuristik 1 — kopya URL (LLM'siz)
    if norm in known_urls:
        apply_decision(sub, "reddet",
                       "Kopya: bu URL zaten yayındaki bir fırsatta mevcut", dry_run)
        print("  KOPYA (opportunities'te var) → REDDET")
        return "kopya"
    if norm in seen_urls:
        apply_decision(sub, "reddet",
                       "Kopya: aynı URL bu partide daha önce işlendi", dry_run)
        print("  KOPYA (partide tekrar) → REDDET")
        return "kopya"
    seen_urls.add(norm)

    # Heuristik 2 — kayıtlı son başvuru tarihi geçmiş (LLM'siz)
    dl = parse_deadline(sub.get("deadline_text"))
    if dl is not None and dl < date.today():
        apply_decision(sub, "reddet",
                       f"Son başvuru tarihi geçmiş: {dl.isoformat()}", dry_run)
        print(f"  SÜRESİ GEÇMİŞ ({dl}) → REDDET")
        return "sure_gecti"

    # Sayfayı getir
    status, final_url, html, err = fetch_page(url)

    # Heuristik 3 — ölü bağlantı (LLM'siz)
    if status in (404, 410):
        apply_decision(sub, "reddet", f"Ölü bağlantı (HTTP {status})", dry_run)
        print(f"  HTTP {status} → REDDET")
        return "olu_link"
    if status is None:
        apply_decision(sub, "belirsiz", f"Sayfaya ulaşılamadı: {err}", dry_run)
        print("  Bağlantı hatası → BELİRSİZ")
        return "belirsiz"
    if status != 200:
        # 403/429/5xx — geçici ya da bot koruması olabilir; LLM'e gitme.
        apply_decision(sub, "belirsiz",
                       f"Sayfa HTTP {status} döndü (geçici/bot koruması olabilir)", dry_run)
        print(f"  HTTP {status} → BELİRSİZ")
        return "belirsiz"

    # KATMAN 2 — sayfa 200 ama durum belirsiz: LLM devreye girer
    page_text = page_to_text(html)
    if len(page_text) < 80:
        apply_decision(sub, "belirsiz",
                       "Sayfadan anlamlı metin çıkmadı (JS-ağırlıklı olabilir)", dry_run)
        print("  İçerik çok ince → BELİRSİZ")
        return "belirsiz"

    http_note = "200" + (f" (yönlendirildi: {final_url})"
                         if _norm_url(final_url) != norm else "")
    print(f"  HTTP 200, durum belirsiz → Gemini ({GEMINI_MODEL}) sorgulanıyor...")
    stats["gemini_calls"] += 1
    verdict = judge_with_gemini(sub, url, http_note, page_text)
    time.sleep(GEMINI_MIN_INTERVAL)                # ücretsiz tier RPM sınırı

    if verdict is None:
        apply_decision(sub, "belirsiz", "Gemini kararı alınamadı", dry_run)
        print("  Gemini hatası → BELİRSİZ")
        return "belirsiz"

    print(f"  Gemini: durum={verdict['durum']} "
          f"kategori_uygun={verdict['kategori_uygun']} guven={verdict['guven']}")
    eylem, gerekce = decide(verdict)

    if eylem == "onayla":
        # açık + uygun + güven yüksek/orta → agent_approve_submission RPC ile
        # otomatik onay. RPC başarısız olursa güvenli tarafa düş: öneri + pending.
        ok, detay = approve_submission(sub, dry_run)
        if ok:
            apply_decision(sub, "onayla", gerekce, dry_run)
            print(f"  → OTOMATİK ONAY — {gerekce}  [{detay}]")
            return "onaylandi"
        apply_decision(sub, "oner",
                       f"{gerekce} (otomatik onay başarısız: {detay})", dry_run)
        print(f"  → ÖNERİ — otomatik onay BAŞARISIZ ({detay}); elle onayla")
        return "oner"

    apply_decision(sub, eylem, gerekce, dry_run)
    print(f"  → {eylem.upper()} — {gerekce}")
    return {"reddet": "gemini_red", "belirsiz": "belirsiz"}[eylem]


def main():
    parser = argparse.ArgumentParser(description="Submission doğrulama ajanı")
    parser.add_argument("--limit", type=int, help="En fazla bu kadar submission işle")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB'ye yazma, sadece kararı göster")
    args = parser.parse_args()

    missing = [n for n, v in (("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY),
                              ("GEMINI_API_KEY", GEMINI_API_KEY)) if not v]
    if missing:
        print("Eksik ortam değişkeni: " + ", ".join(missing) + " — .env kontrol et.",
              file=sys.stderr)
        print("Gemini ücretsiz anahtarı: https://aistudio.google.com/apikey",
              file=sys.stderr)
        sys.exit(1)

    print("Pending submission'lar çekiliyor...")
    try:
        subs = fetch_pending(args.limit)
    except requests.exceptions.RequestException as e:
        print(f"Supabase'den okuma hatası: {e}", file=sys.stderr)
        sys.exit(1)

    if not subs:
        print("İşlenecek pending submission yok (ya da hepsi zaten ajanca işlenmiş).")
        return

    known_urls = fetch_known_urls()
    seen_urls = set()
    stats = {"gemini_calls": 0}
    tally = {k: 0 for k in
             ("kopya", "sure_gecti", "olu_link", "gemini_red",
              "onaylandi", "oner", "belirsiz")}

    mode = "DRY-RUN — DB'ye yazılmayacak" if args.dry_run else "CANLI — DB'ye yazılacak"
    print(f"{len(subs)} submission · {len(known_urls)} mevcut URL biliniyor · {mode}")
    print("─" * 64)

    for sub in subs:
        try:
            tally[process(sub, args.dry_run, known_urls, seen_urls, stats)] += 1
        except requests.exceptions.RequestException as e:
            print(f"  ! ağ/DB hatası — atlandı: {e}")

    reddedildi = (tally["kopya"] + tally["sure_gecti"]
                  + tally["olu_link"] + tally["gemini_red"])
    print("\n" + "─" * 64)
    print(f"REDDEDİLDİ : {reddedildi}")
    print(f"   kopya {tally['kopya']} · süresi geçmiş {tally['sure_gecti']} · "
          f"ölü link {tally['olu_link']} · Gemini-red {tally['gemini_red']}")
    print(f"ONAYLANDI  : {tally['onaylandi']}   (otomatik onay — opportunities'e eklendi)")
    print(f"ÖNERİLDİ   : {tally['oner']}   (otomatik onay başarısız — pending; elle onayla)")
    print(f"BELİRSİZ   : {tally['belirsiz']}   (pending kaldı)")
    heuristik = reddedildi - tally["gemini_red"]
    print(f"\nGemini çağrısı: {stats['gemini_calls']} / {len(subs)} "
          f"— heuristikler {heuristik} kararı LLM'siz, ücretsiz çözdü.")


if __name__ == "__main__":
    main()
