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
  Sayfa HTTP 200 dönüyor ama açık/kapalı durumu net değil → LLM'e (NVIDIA NIM,
  OpenAI-uyumlu, ücretsiz tier) sorulur. Diğer HTTP durumları (403/429/5xx/
  timeout) LLM'e gitmez; belirsiz olarak pending bırakılır.

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
  python validate_submissions.py --recheck --dry-run --limit 10
                                               # daha önce ajan notu alan pending'leri yeniden değerlendir
  python validate_submissions.py --audit-opportunities   # aşağıya bak

AUDIT MODU — --audit-opportunities:
  Submission yerine YAYINDAKİ fırsatları (opportunities) denetler. Admin
  panelindeki "Manuel doğrulanmamış" kümesini (last_verified_at IS NULL) çeker;
  her fırsatın URL'i ölü (HTTP 404/410) ya da son başvuru tarihi (deadline /
  deadline_notes) geçmişse is_active=false yapar ve last_verified_at'i now()
  olarak işaretler. Belirsiz sonuçlar (timeout/403/5xx) dokunulmadan bırakılır —
  sonraki çalıştırmaya kalır. LLM kullanmaz; bu modda LLM anahtarı gerekmez.
  --limit ve --dry-run bu modda da geçerlidir.

.env:
  SUPABASE_URL=...
  SUPABASE_SERVICE_ROLE_KEY=...
  NVIDIA_API_KEY=...   # https://build.nvidia.com (ücretsiz tier) — OpenAI-uyumlu
                        # --audit-opportunities modunda gerekmez
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

# LLM sağlayıcı — OpenAI-uyumlu chat/completions. Varsayılan: NVIDIA NIM
# (build.nvidia.com), kişisel kullanım için ücretsiz tier sunar. Başka bir
# OpenAI-uyumlu sağlayıcıya geçmek için yalnızca LLM_BASE_URL / LLM_MODEL /
# NVIDIA_API_KEY env'i değişir, kod aynı kalır.
LLM_API_KEY = os.getenv("NVIDIA_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")
LLM_MIN_INTERVAL = 1.5        # çağrılar arası bekleme — ücretsiz tier RPM sınırı
# gpt-oss gibi reasoning modelleri akıl yürütmeyi de completion token'ı olarak
# harcar (boş prompt'ta bile ~270 token). JSON content akıl yürütmeden SONRA
# gelir; bütçe darsa content yarım/boş kalır (finish_reason='length') → parse
# edilemez. Bu yüzden geniş tut.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3000"))

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

# İngilizce ay adları — youthop gibi İngilizce kaynaklar "june 25, 2026" /
# "25 june 2026" biçiminde tarih verir; parse_deadline bunları da çözsün.
EN_AYLAR = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

SYSTEM_PROMPT = """Sen "Fırsat Eşitliği" platformunun submission doğrulama ajanısın. Bu platform Türkiye'deki gençlere yurt dışı burs, staj, gönüllülük, yaz okulu, gençlik projesi ve değişim programı gibi ÜCRETSİZ veya FONLU fırsatları toplar.

Sana bir submission'ın bilgileri, BUGÜNÜN TARİHİ ve orijinal sayfasının metni verilir. Üç şeyi değerlendirirsin:

1) durum — Fırsat hâlâ başvuruya açık mı?
   - "acik": Son başvuru tarihi BUGÜNDEN SONRA; ya da aktif başvuru formu/linki ya da "başvurular devam ediyor / applications open / now accepting applications" benzeri ifade var.
   - "kapali": "Başvurular kapandı", "son başvuru tarihi geçti", "applications closed", "deadline has passed", "this programme has ended" benzeri net ifade var; VEYA sayfadaki son başvuru / etkinlik / proje tarihi BUGÜNDEN ÖNCE ve yeni dönem duyurulmamış; VEYA sayfa fırsatın artık mevcut olmadığını gösteriyor.
   - "belirsiz": Sayfa açıldı ama açık mı kapalı mı metinden çıkmıyor.

TARİH KURALI: Açık/kapalı kararını yalnızca sana verilen "BUGÜNÜN TARİHİ"ne göre ver — kendi tarih bilgine GÜVENME. Sayfadaki son başvuru tarihi, etkinlik tarihi veya proje tarihi bu tarihten önceyse fırsat GEÇMİŞTİR → durum="kapali". Tarihi bütün olarak (gün-ay-yıl) bugünle karşılaştır; yıl tek başına yeterli ipucu değildir.

GÜNCELLİK KURALI: "Apply now", "Applications are invited" veya çalışan bir başvuru linki tek başına fırsatın bugün açık olduğuna yüksek güvenli kanıt değildir; eski ilanlarda bu ifadeler kalabilir. Açık kararı için gelecekte bir tarih, açık olduğu belirtilen güncel dönem/yıl veya başvurunun şu anda kabul edildiğini gösteren eşdeğer güncel kanıt ara. Böyle bir güncellik kanıtı yoksa durum="belirsiz" ve guven en fazla "orta" olsun; otomatik onaya gönderme.

2) kategori_uygun — Sayfa gerçekten bu fırsatı anlatıyor mu ve platforma uygun mu?
   - true: Gerçek bir fırsat ilanı, belirtilen kategoriyle makul örtüşüyor ve gencin ücret ödemesini gerektirmiyor. TEK bir fırsat = tek program, tek son başvuru tarihi, tek başvuru süreci.
   - false: Fırsat ilanı değil (genel blog, ana sayfa, giriş sayfası, alakasız ürün/hizmet, hata sayfası); VEYA ücretli/ticari program; VEYA kategoriyle hiç ilgisi yok.
   - false (DERLEME/LİSTE KURALI): Sayfa birden çok AYRI fırsatı/placement'ı bir arada listeliyorsa — her birinin kendi son başvuru tarihi ve kendi başvuru linki olan bir derleme/liste/"roundup"/digest — genel teması platforma uygun OLSA BİLE kategori_uygun=false. Çünkü bu tek bir başvurulabilir fırsat değil, fırsat dizinidir. İpuçları: başlıkta/metinde "16 fırsat", "X yeni placement", "this list/batch", arka arkaya birden çok "Apply here"/"Başvur" linki ve birbirinden farklı deadline'lar. Örn. "16 New ESC Volunteering Opportunities" tek fırsat DEĞİLDİR → false.

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


def fetch_pending(limit=None, recheck=False):
    """Pending submission'ları çeker. Service key RLS'i bypass eder.

    Varsayılan akış, daha önce ajan tarafından işlenen kayıtları idempotentlik
    için atlar. ``recheck=True`` eski ajan notlu pending kayıtları da yeniden
    değerlendirir; zamanla geçen deadline'ları ve değişen sayfaları yakalamak
    için kullanılır.
    """
    params = {
        "status": "eq.pending",
        "select": "id,title,url,category_slug,eligibility_notes,deadline_text,admin_note",
        "order": "created_at.asc",
    }
    res = requests.get(f"{SUPABASE_URL}/rest/v1/submissions",
                       headers=sb_headers(), params=params, timeout=20)
    res.raise_for_status()
    rows = res.json()
    # Ajanın daha önce işlediklerini varsayılan olarak atla — idempotent.
    # --recheck özellikle eski pending kararlarını tazelemek için bu süzgeci açar.
    if not recheck:
        rows = [r for r in rows
                if not (r.get("admin_note") or "").startswith(AGENT_MARKER)]
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
    Sırayla denenen formatlar: ISO (2026-06-25), noktalı (25.06.2026),
    Türkçe-ay (25 haziran 2026), İngilizce ay-önce (june 25, 2026 / april
    22nd, 2026) ve İngilizce gün-önce (25 june 2026)."""
    if not text:
        return None
    t = str(text).lower()
    y = mo = d = None

    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)          # ISO
    if m:
        y, mo, d = (int(g) for g in m.groups())
    if d is None:                                              # noktalı GG.AA.YYYY
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
        if m:
            d, mo, y = (int(g) for g in m.groups())
    if d is None:                                              # TR ay: 25 haziran 2026
        m = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4})", t)
        if m and m.group(2) in TR_AYLAR:
            d, mo, y = int(m.group(1)), TR_AYLAR[m.group(2)], int(m.group(3))
    if d is None:                                              # EN ay-önce: june 25, 2026
        m = re.search(
            r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", t
        )
        if m and m.group(1) in EN_AYLAR:
            mo, d, y = EN_AYLAR[m.group(1)], int(m.group(2)), int(m.group(3))
    if d is None:                                              # EN gün-önce: 25 june 2026
        m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
        if m and m.group(2) in EN_AYLAR:
            d, mo, y = int(m.group(1)), EN_AYLAR[m.group(2)], int(m.group(3))

    if d is None:
        return None
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


# ─── LLM katmanı (OpenAI-uyumlu, NVIDIA NIM) ──────────────────────────────────

def _loads_lenient(t):
    """JSON'u savunmacı çözer. Düz parse başarısızsa metindeki ilk DENGELİ {...}
    bloğunu tarar — gpt-oss json_object modu bazen geçerli nesnenin başına çöp
    ekliyor (ör. '{\"' ön eki). String içi süslü parantezleri saymaz."""
    if not t:
        return None
    try:
        return json.loads(t)
    except (json.JSONDecodeError, TypeError):
        pass
    for i in range(len(t)):
        if t[i] != "{":
            continue
        depth, in_str, esc = 0, False, False
        for j in range(i, len(t)):
            c = t[j]
            if in_str:
                esc = (c == "\\" and not esc)
                if c == '"' and not esc:
                    in_str = False
            elif c == '"':
                in_str, esc = True, False
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[i:j + 1])
                    except json.JSONDecodeError:
                        break          # bu { başlangıcı tutmadı, sonrakini dene
    return None


def _parse_verdict(text):
    """LLM'in metin yanıtından JSON kararı çıkarır (savunmacı)."""
    t = (text or "").strip()
    if t.startswith("```"):                       # ```json ... ``` sarmalını söker
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    v = _loads_lenient(t)
    if v is None:
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


def judge_with_llm(sub, url, http_note, page_text):
    """LLM'e (OpenAI-uyumlu chat/completions) sorar, karar dict'i döndürür
    (hata → None). SYSTEM_PROMPT ve user_text sağlayıcıdan bağımsızdır; yalnızca
    taşıyıcı format OpenAI şemasıdır."""
    user_text = (
        f"BUGÜNÜN TARİHİ: {date.today().isoformat()}\n"
        "(Fırsatın açık/kapalı olduğunu bu tarihe göre belirle; kendi tarih bilgine güvenme.)\n\n"
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
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0,
        "max_tokens": LLM_MAX_TOKENS,
        # response_format json_object KULLANILMIYOR: gpt-oss'ta aralıklı olarak
        # geçerli nesnenin başına '{"' artefaktı ekleyip JSON'u bozuyordu. Sistem
        # prompt'u zaten ham JSON dayatıyor; _parse_verdict de dengeli bloğu
        # ayıklıyor (bkz. _loads_lenient).
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    res = None
    for attempt in range(3):
        try:
            res = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers, json=body, timeout=45,
            )
        except requests.exceptions.RequestException as e:
            print(f"  ! LLM ağ hatası: {e}")
            return None
        if res.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            # NVIDIA ücretsiz endpoint'i yoğunlukta 503 döndürebiliyor. 429 için
            # daha uzun, diğer geçici sunucu hataları için kademeli kısa backoff.
            if res.status_code == 429:
                wait = 20 * (attempt + 1)
                reason = "rate limit"
            else:
                wait = 5 * (attempt + 1)
                reason = "geçici sunucu hatası"
            print(f"  LLM {res.status_code} ({reason}) — {wait}s bekleniyor...")
            time.sleep(wait)
            continue
        break
    if res is None or res.status_code != 200:
        detail = res.text[:200] if res is not None else "yanıt yok"
        print(f"  ! LLM HTTP {getattr(res, 'status_code', '?')}: {detail}")
        return None
    try:
        choice = res.json()["choices"][0]
        text = choice["message"]["content"]
        finish = choice.get("finish_reason")
    except (KeyError, IndexError, ValueError):
        print("  ! LLM yanıtı beklenen yapıda değil")
        return None
    verdict = _parse_verdict(text)
    if verdict is None:
        # finish_reason='length' → reasoning max_tokens'ı tüketti, content yarım;
        # LLM_MAX_TOKENS'ı artır. Sessiz başarısızlığı görünür kıl.
        snippet = (text or "").strip()[:120] or "(boş content)"
        print(f"  ! LLM JSON çözülemedi (finish={finish}): {snippet}")
    return verdict


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
    """Tek submission — heuristikler, gerekirse LLM. Tally etiketi döndürür."""
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
    print(f"  HTTP 200, durum belirsiz → LLM ({LLM_MODEL}) sorgulanıyor...")
    stats["llm_calls"] += 1
    verdict = judge_with_llm(sub, url, http_note, page_text)
    time.sleep(LLM_MIN_INTERVAL)                   # sağlayıcı RPM sınırı

    if verdict is None:
        apply_decision(sub, "belirsiz", "LLM kararı alınamadı", dry_run)
        print("  LLM hatası → BELİRSİZ")
        return "belirsiz"

    print(f"  LLM: durum={verdict['durum']} "
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
    return {"reddet": "llm_red", "belirsiz": "belirsiz"}[eylem]


# ─── Opportunity audit (--audit-opportunities) ────────────────────────────────

def fetch_unverified_opportunities(limit=None):
    """last_verified_at IS NULL olan fırsatları çeker — admin panelindeki
    "Manuel doğrulanmamış" kümesi. Service key RLS'i bypass eder."""
    params = {
        "last_verified_at": "is.null",
        "select": "id,title,official_url,deadline,deadline_notes,is_active",
        "order": "id.asc",
    }
    res = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities",
                       headers=sb_headers(), params=params, timeout=20)
    res.raise_for_status()
    rows = res.json()
    return rows[:limit] if limit else rows


def opportunity_deadline(opp):
    """Fırsatın son başvuru tarihini (date | None) döndürür. Önce yapısal
    `deadline` kolonu, o boşsa serbest metin `deadline_notes` denenir."""
    raw = opp.get("deadline")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    return parse_deadline(opp.get("deadline_notes"))


def update_opportunity(opp_id, patch, dry_run):
    """opportunities satırını PATCH'ler. dry_run'da DB'ye yazmaz."""
    if dry_run:
        return
    res = requests.patch(
        f"{SUPABASE_URL}/rest/v1/opportunities",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        params={"id": f"eq.{opp_id}"},
        json=patch, timeout=15,
    )
    res.raise_for_status()


def audit_opportunity(opp, dry_run):
    """Tek fırsatı denetler. Tally etiketi döndürür:
    expired | dead | alive | belirsiz.
      expired/dead -> is_active=false + last_verified_at=now()
      alive        -> yalnızca last_verified_at=now()
      belirsiz     -> hiç yazılmaz; sonraki çalıştırmaya kalır."""
    print(f"\n• {(opp.get('title') or '(başlıksız)')[:60]}")
    opp_id = opp["id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1) Son başvuru tarihi geçmiş mi? (URL'e gitmeden — istek tasarrufu)
    dl = opportunity_deadline(opp)
    if dl is not None and dl < date.today():
        update_opportunity(opp_id,
                           {"is_active": False, "last_verified_at": now_iso}, dry_run)
        print(f"  Son başvuru tarihi geçmiş ({dl}) → PASİFLEŞTİRİLDİ")
        return "expired"

    # 2) URL canlı mı?
    url = (opp.get("official_url") or "").strip()
    if not url:
        print("  Fırsatta URL yok → BELİRSİZ (dokunulmadı)")
        return "belirsiz"
    print(f"  URL: {url}")
    status, _final_url, _html, err = fetch_page(url)
    if status in (404, 410):
        update_opportunity(opp_id,
                           {"is_active": False, "last_verified_at": now_iso}, dry_run)
        print(f"  Ölü bağlantı (HTTP {status}) → PASİFLEŞTİRİLDİ")
        return "dead"
    if status is None:
        print(f"  Sayfaya ulaşılamadı ({err}) → BELİRSİZ (dokunulmadı)")
        return "belirsiz"
    if status != 200:
        # 403/429/5xx — geçici ya da bot koruması olabilir; pasifleştirme.
        print(f"  HTTP {status} (geçici/bot koruması olabilir) → BELİRSİZ (dokunulmadı)")
        return "belirsiz"

    # 3) URL canlı + son başvuru tarihi geçmemiş → yalnızca doğrulandı işaretle
    update_opportunity(opp_id, {"last_verified_at": now_iso}, dry_run)
    print("  URL canlı, son başvuru tarihi geçmemiş → AKTİF KALDI (doğrulandı)")
    return "alive"


def run_audit_opportunities(args):
    """--audit-opportunities akışı: last_verified_at boş fırsatları denetler."""
    print("Doğrulanmamış fırsatlar çekiliyor (last_verified_at IS NULL)...")
    try:
        opps = fetch_unverified_opportunities(args.limit)
    except requests.exceptions.RequestException as e:
        print(f"Supabase'den okuma hatası: {e}", file=sys.stderr)
        sys.exit(1)

    if not opps:
        print("Doğrulanmamış fırsat yok — hepsi denetlenmiş.")
        return

    mode = "DRY-RUN — DB'ye yazılmayacak" if args.dry_run else "CANLI — DB'ye yazılacak"
    print(f"{len(opps)} fırsat denetlenecek · {mode}")
    print("─" * 64)

    tally = {k: 0 for k in ("expired", "dead", "alive", "belirsiz")}
    for opp in opps:
        try:
            tally[audit_opportunity(opp, args.dry_run)] += 1
        except requests.exceptions.RequestException as e:
            print(f"  ! ağ/DB hatası — atlandı: {e}")

    deaktif = tally["expired"] + tally["dead"]
    print("\n" + "─" * 64)
    print(f"PASİFLEŞTİRİLDİ : {deaktif}  (is_active=false)")
    print(f"   süresi geçmiş {tally['expired']} · ölü link {tally['dead']}")
    print(f"AKTİF KALDI     : {tally['alive']}  (URL canlı, tarih geçmemiş)")
    print(f"BELİRSİZ        : {tally['belirsiz']}  "
          f"(denetlenemedi — dokunulmadı, sonraki çalıştırmaya kaldı)")
    print(f"\nlast_verified_at güncellendi: {deaktif + tally['alive']} fırsat.")


def main():
    parser = argparse.ArgumentParser(description="Submission doğrulama ajanı")
    parser.add_argument("--limit", type=int, help="En fazla bu kadar kayıt işle")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB'ye yazma, sadece kararı göster")
    parser.add_argument("--recheck", action="store_true",
                        help="Daha önce [ajan] notu almış pending kayıtları da "
                             "yeniden değerlendir")
    parser.add_argument("--audit-opportunities", action="store_true",
                        help="Submission yerine yayındaki fırsatları denetle: "
                             "last_verified_at boş olanların URL'i ölü ya da son "
                             "başvuru tarihi geçmişse is_active=false yapar")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("Eksik ortam değişkeni: SUPABASE_SERVICE_ROLE_KEY — .env kontrol et.",
              file=sys.stderr)
        sys.exit(1)

    # Audit modu yalnızca heuristik (URL + tarih) çalışır — LLM yok, anahtar gerekmez.
    if args.audit_opportunities:
        run_audit_opportunities(args)
        return

    if not LLM_API_KEY:
        print("Eksik ortam değişkeni: NVIDIA_API_KEY — .env kontrol et.",
              file=sys.stderr)
        print("NVIDIA NIM anahtarı (ücretsiz): https://build.nvidia.com",
              file=sys.stderr)
        sys.exit(1)

    print("Pending submission'lar çekiliyor...")
    try:
        subs = fetch_pending(args.limit, recheck=args.recheck)
    except requests.exceptions.RequestException as e:
        print(f"Supabase'den okuma hatası: {e}", file=sys.stderr)
        sys.exit(1)

    if not subs:
        print("İşlenecek pending submission yok (ya da hepsi zaten ajanca işlenmiş).")
        return

    known_urls = fetch_known_urls()
    seen_urls = set()
    stats = {"llm_calls": 0}
    tally = {k: 0 for k in
             ("kopya", "sure_gecti", "olu_link", "llm_red",
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
                  + tally["olu_link"] + tally["llm_red"])
    print("\n" + "─" * 64)
    print(f"REDDEDİLDİ : {reddedildi}")
    print(f"   kopya {tally['kopya']} · süresi geçmiş {tally['sure_gecti']} · "
          f"ölü link {tally['olu_link']} · LLM-red {tally['llm_red']}")
    print(f"ONAYLANDI  : {tally['onaylandi']}   (otomatik onay — opportunities'e eklendi)")
    print(f"ÖNERİLDİ   : {tally['oner']}   (otomatik onay başarısız — pending; elle onayla)")
    print(f"BELİRSİZ   : {tally['belirsiz']}   (pending kaldı)")
    heuristik = reddedildi - tally["llm_red"]
    print(f"\nLLM çağrısı: {stats['llm_calls']} / {len(subs)} "
          f"— heuristikler {heuristik} kararı LLM'siz çözdü.")


if __name__ == "__main__":
    main()
