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
  Yalnızca açık + uygun + güven YÜKSEK ve bütün zorunlu alanları sayfadaki
    kanıtla doğrulanmış kayıt → OTOMATİK ONAY. Eksik/yanlış alan, eski tarih,
    kaynak/liste linki veya doğrulanamayan kanıt → RED. Yalnız tarihi güncel,
    doğrudan linki doğrulanmış ve alanları tutarlı kayıtta karar çelişkiliyse
    belirsiz → admin_note; pending kalır. DB RPC aynı onay kapılarını tekrarlar.

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
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

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
HUMAN_REJECT_RE = re.compile(r"^\[insan\]\s+RED:([a-z0-9_]+)\s+—\s+(.+)$")
PAGE_CHAR_LIMIT = 6000
VALID_FUNDING_TYPES = {"full", "partial", "free", "stipend"}
VALID_CATEGORY_SLUGS = {"scholarship", "volunteering", "youth_project",
                        "internship", "summer_school", "exchange"}
VALID_STUDY_LEVELS = {"bachelor", "master", "phd", "any"}
# 105'te request_revision'ın admin_note'a yazdığı önek. Ajan isteği bu önekten
# sonrasından okur; not biçimi değişirse tek yerde güncellenir.
REVISION_MARKER = "[insan] REVİZE İSTENDİ:"
AGGREGATOR_DOMAINS = {"youthop.com", "www.youthop.com", "nasilgitmis.com", "www.nasilgitmis.com"}

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

4) Yayın güvenlik doğrulamaları — Her alan yalnız sayfadaki açık kanıtla true olabilir:
   - tek_firsat: Sayfa yalnız TEK fırsatı anlatıyor.
   - dogrudan_firsat_sayfasi: URL genel ana sayfa, giriş ekranı, arama sonucu, etiket/kategori veya çoklu fırsat listesi değil; bu fırsatın kendi detay/başvuru sayfası.
   - son_tarih_dogrulandi: Submission'daki son tarih sayfadaki tarihle aynı, tam olarak gün-ay-yıl içeriyor ve BUGÜNDEN ÖNCE değil.
   - finansman_dogrulandi: Submission'daki finansman türü (full/partial/free/stipend) sayfadaki açık bilgiyle uyuşuyor. Bilgi yoksa false; tahmin etme.
   - ulke_dogrulandi: Submission'daki ev sahibi ülke veya gerçekten global olduğu sayfada doğrulanıyor.
   - uygunluk_dogrulandi: Submission'daki uygunluk notu sayfadaki başvuru koşullarıyla uyuşuyor ve boş/genel bir metin değil.

Bu doğrulamaların herhangi birinde kanıt yoksa veya kayıtla çelişiyorsa false ver. Herhangi bir false kayıt eksik/yanlış sayılarak otomatik reddedilir. `belirsiz` yalnız bütün bu alanlar true iken açık/kapalı kararında gerçek bir çelişki kalırsa kullanılabilir.

KRİTİK: Eksik zorunlu bilgi de kayıt hatasıdır. "kapali", kategori_uygun=false veya yayın doğrulamalarından herhangi birinin false olması submission'ın OTOMATİK REDDEDİLMESİNE yol açar. Kanıt görmeden true üretme. "belirsiz" yalnız bütün yayın doğrulamaları true olduğu halde genel karar güveni orta/düşük kaldığında kullanılabilir.

ÇIKTI: Yanıtını yalnızca şu alanlara sahip TEK bir JSON nesnesi olarak ver. Markdown, ``` işareti veya açıklama EKLEME:
{"durum": "acik|kapali|belirsiz", "kategori_uygun": true|false, "guven": "yuksek|orta|dusuk", "tek_firsat": true|false, "dogrudan_firsat_sayfasi": true|false, "son_tarih_dogrulandi": true|false, "finansman_dogrulandi": true|false, "ulke_dogrulandi": true|false, "uygunluk_dogrulandi": true|false, "gerekce": "<kararını dayandıran kanıtı belirten Türkçe tek cümle>"}"""


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
        "submission_origin": "eq.agent",
        "review_stage": "in.(agent_queue,agent_uncertain)" if recheck else "eq.agent_queue",
        "select": ("id,title,url,source_url,category_slug,host_countries,eligibility_notes,"
                   "deadline_text,funding_type,study_level,admin_note,"
                   "submitter_nickname,submission_origin,review_stage"),
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

    # Admin'in revize istediği insan gönderileri (105). Ayrı bir istek olarak
    # çekiliyor: PostgREST'te tek sorguda "origin=agent VEYA (origin=human VE
    # stage=agent_revision)" yazmak or=() ile okunaksızlaşıyor, iki net sorgu
    # daha anlaşılır. Bunlar AGENT_MARKER süzgecine takılmamalı — admin aynı
    # kaydı tekrar revize edebilir ve ajan her seferinde yeniden bakmalı.
    rows += fetch_revision_queue()

    return rows[:limit] if limit else rows


def fetch_revision_queue():
    """Admin'in 'Revize' dediği insan gönderileri (review_stage=agent_revision).

    Bu kayıtlar ajanın normal kuyruğundan ayrı: ajan bunları DEĞERLENDİRİR ama
    ONAYLAMAZ/REDDETMEZ — kararı insana bırakır (bkz. apply_decision). 099'daki
    koruma zaten agent_approve_submission'ı yalnız origin='agent' kayıtlarla
    sınırlıyor, bu ayrım onun üstüne ikinci bir emniyet."""
    params = {
        "status": "eq.pending",
        "submission_origin": "eq.human",
        "review_stage": "eq.agent_revision",
        # Normal kuyruktan daha geniş: ajan bu kayıtların BOŞ alanlarını
        # doldurabildiği için hangilerinin boş olduğunu görmesi gerekiyor.
        "select": ("id,title,url,source_url,category_slug,host_countries,eligibility_notes,"
                   "deadline_text,funding_type,funding_notes,language_requirement,"
                   "age_min,age_max,study_level,description,admin_note,"
                   "submitter_nickname,submission_origin,review_stage"),
        "order": "reviewed_at.asc",
    }
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/submissions",
                           headers=sb_headers(), params=params, timeout=20)
        res.raise_for_status()
        rows = res.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        # Revize kuyruğu okunamazsa normal kuyruk çalışmaya devam etsin.
        print(f"  ! revize kuyruğu okunamadı ({e})")
        return []
    return rows if isinstance(rows, list) else []


def fetch_agent_memories():
    """İnsan redlerinden üretilen aktif hafıza kayıtlarını getirir."""
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/agent_memories",
        headers=sb_headers(),
        params={
            "active": "eq.true",
            "select": ("source_nickname,category_slug,reason_code,summary,"
                       "evidence_count,weight"),
            "order": "evidence_count.desc",
            "limit": "500",
        },
        timeout=20,
    )
    res.raise_for_status()
    return res.json()


def memory_context_for(sub, memories):
    """Yalnız aynı kaynak/kategorideki en güçlü geçmiş örnekleri döndürür."""
    source = (sub.get("submitter_nickname") or "manual/unknown").strip()
    category = (sub.get("category_slug") or "unknown").strip()
    relevant = [m for m in memories
                if m.get("source_nickname") == source
                and m.get("category_slug") == category]
    if not relevant:
        return "(bu kaynak/kategori için insan geri bildirimi yok)"
    lines = []
    for item in relevant[:8]:
        lines.append(
            f"- {item['reason_code']} | ağırlık={item['weight']} | "
            f"kanıt={item['evidence_count']}: {item['summary']}"
        )
    return "\n".join(lines)


def _norm_url(u):
    return (u or "").strip().rstrip("/").lower()


def _url_host(url):
    try:
        return urlsplit((url or "").strip()).netloc.lower().split(":", 1)[0]
    except ValueError:
        return ""


def direct_link_blockers(sub):
    """Kaynak yazının yanlışlıkla başvuru URL'i olmasını deterministik engeller."""
    url = (sub.get("url") or "").strip()
    source_url = (sub.get("source_url") or "").strip()
    blockers = []
    if _url_host(url) in AGGREGATOR_DOMAINS:
        blockers.append("doğrudan başvuru/resmî fırsat linki yerine kaynak yazı verilmiş")
    if (source_url and _url_host(source_url) in AGGREGATOR_DOMAINS
            and _norm_url(source_url) == _norm_url(url)):
        blockers.append("kaynak ve başvuru linki aynı")
    return list(dict.fromkeys(blockers))


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


def fetch_human_rejections():
    """İnsan adminlerin reddettiği kayıtları geri bildirim raporu için çeker.

    Bu kayıtlar yalnızca analiz edilir; agent tarafından yeniden açılmaz veya
    durumları değiştirilmez.
    """
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/submissions",
        headers=sb_headers(),
        params={
            "status": "eq.rejected",
            "reviewed_by": "not.is.null",
            "select": "submitter_nickname,admin_note,reviewed_at",
            "order": "reviewed_at.desc",
            "limit": "5000",
        },
        timeout=20,
    )
    res.raise_for_status()
    return res.json()


def run_feedback_report():
    """Yapılandırılmış insan redlerini kaynak ve neden koduna göre özetler."""
    rows = fetch_human_rejections()
    by_reason = Counter()
    by_source = Counter()
    by_source_reason = Counter()

    for row in rows:
        source = (row.get("submitter_nickname") or "manual/unknown").strip()
        note = (row.get("admin_note") or "").strip()
        match = HUMAN_REJECT_RE.match(note)
        if match:
            reason = match.group(1)
        elif note:
            reason = "legacy_unstructured"
        else:
            reason = "missing_reason"
        by_reason[reason] += 1
        by_source[source] += 1
        by_source_reason[(source, reason)] += 1

    print(f"İnsan tarafından reddedilen toplam kayıt: {len(rows)}")
    print("\nNedene göre:")
    for reason, count in by_reason.most_common():
        print(f"  {reason}: {count}")
    print("\nKaynağa göre:")
    for source, count in by_source.most_common():
        print(f"  {source}: {count}")
        details = [
            (reason, n) for (item_source, reason), n in by_source_reason.items()
            if item_source == source
        ]
        for reason, n in sorted(details, key=lambda item: (-item[1], item[0])):
            print(f"    - {reason}: {n}")


def fetch_agent_approved_submissions(limit=None):
    """Gerçek otomatik onayları getirir (admin onaylarını dahil etmez)."""
    params = {
        "status": "eq.approved",
        "submission_origin": "eq.agent",
        "reviewed_by": "is.null",
        "select": ("id,title,url,source_url,category_slug,host_countries,eligibility_notes,"
                   "deadline_text,funding_type,study_level,admin_note,"
                   "created_opportunity_id,reviewed_at"),
        "order": "reviewed_at.desc",
        "limit": str(limit or 5000),
    }
    res = requests.get(f"{SUPABASE_URL}/rest/v1/submissions",
                       headers=sb_headers(), params=params, timeout=20)
    res.raise_for_status()
    return res.json()


def fetch_opportunities_by_ids(ids):
    if not ids:
        return {}
    result = {}
    for start in range(0, len(ids), 100):
        batch = ids[start:start + 100]
        params = {
            "id": f"in.({','.join(batch)})",
            "select": ("id,title,official_url,deadline,deadline_notes,is_active,"
                       "last_verified_at"),
        }
        res = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities",
                           headers=sb_headers(), params=params, timeout=20)
        res.raise_for_status()
        result.update({row["id"]: row for row in res.json()})
    return result


def classify_historic_approval(sub, opportunity):
    """Eski otomatik onayı yeni kapıya göre salt-okunur sınıflandırır."""
    blockers = submission_completeness_blockers(sub)
    if opportunity is None:
        return "admin_kontrolu", blockers + ["yayındaki fırsat kaydı bulunamadı"]
    deadline = opportunity_deadline(opportunity) or parse_deadline(sub.get("deadline_text"))
    if opportunity.get("is_active") and deadline is not None and deadline < date.today():
        return "kapatilmali", [f"son başvuru tarihi geçmiş: {deadline.isoformat()}"]
    if not opportunity.get("is_active"):
        return "zaten_kapali", blockers
    if blockers:
        return "admin_kontrolu", blockers
    if not opportunity.get("last_verified_at"):
        return "admin_kontrolu", ["yayından sonra hiç doğrulanmamış"]
    return "yayinda_kalabilir", []


def run_agent_approval_reaudit(args):
    """Eski agent onaylarını değiştirmeden yeni sıkı kurala göre raporlar."""
    subs = fetch_agent_approved_submissions(args.limit)
    opp_ids = [str(s["created_opportunity_id"]) for s in subs
               if s.get("created_opportunity_id")]
    opportunities = fetch_opportunities_by_ids(opp_ids)
    report = []
    tally = Counter()
    for sub in subs:
        opp = opportunities.get(str(sub.get("created_opportunity_id")))
        classification, reasons = classify_historic_approval(sub, opp)
        tally[classification] += 1
        report.append({
            "sinif": classification,
            "nedenler": reasons,
            "submission_id": sub["id"],
            "opportunity_id": sub.get("created_opportunity_id"),
            "baslik": sub.get("title"),
            "url": (opp or {}).get("official_url") or sub.get("url"),
        })

    print(f"İncelenen gerçek agent otomatik onayı: {len(report)}")
    for key in ("yayinda_kalabilir", "admin_kontrolu", "kapatilmali", "zaten_kapali"):
        print(f"  {key}: {tally[key]}")
    print("Bu mod veritabanında hiçbir şeyi değiştirmez.")

    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "counts": dict(tally),
            "records": report,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Rapor: {output}")

def is_revision(sub):
    """Admin'in revize istediği bir insan gönderisi mi? (105)"""
    return sub.get("review_stage") == "agent_revision"


def apply_decision(sub, eylem, gerekce, dry_run):
    """Kararı submissions tablosuna yazar.
      reddet -> status=rejected + admin_note + reviewed_at
      onayla -> sadece admin_note PATCH'lenir; status / created_opportunity_id /
                reviewed_at zaten agent_approve_submission RPC'si tarafından
                yazılmıştır (bkz. approve_submission()).
      oner / belirsiz -> sadece admin_note; status 'pending' kalır.
    reviewed_by NULL bırakılır — 'insan değil ajan işledi' sinyali."""
    # Revize kuyruğundaki kayıtlarda ajan YALNIZ görüş bildirir. Onay da red de
    # insanın: admin bu kaydı bilerek elde tutmuş, ajan onun kararını
    # kendiliğinden veremez. Her sonuç human_review'e döner, gerekçe notta.
    if is_revision(sub):
        etiket = {"reddet": "SORUNLU", "onayla": "UYGUN GÖRÜNÜYOR",
                  "oner": "UYGUN GÖRÜNÜYOR"}.get(eylem, "BELİRSİZ")
        note = f"{AGENT_MARKER} REVİZE SONUCU ({etiket}) — {gerekce}"
        patch = {"admin_note": note, "review_stage": "human_review"}
        if not dry_run:
            res = requests.patch(
                f"{SUPABASE_URL}/rest/v1/submissions",
                headers={**sb_headers(), "Prefer": "return=minimal"},
                params={"id": f"eq.{sub['id']}"},
                json=patch, timeout=20)
            res.raise_for_status()
        return note

    if eylem == "reddet":
        note = f"{AGENT_MARKER} RED — {gerekce}"
        patch = {
            "status": "rejected",
            "admin_note": note,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_stage": "decided",
        }
    elif eylem == "onayla":
        note = f"{AGENT_MARKER} OTOMATİK ONAY — {gerekce}"
        patch = {"admin_note": note}
    elif eylem == "oner":
        note = f"{AGENT_MARKER} ÖNERİ: onaya uygun — {gerekce}"
        patch = {"admin_note": note, "review_stage": "agent_uncertain"}
    else:
        note = f"{AGENT_MARKER} BELİRSİZ: elle bak — {gerekce}"
        patch = {"admin_note": note, "review_stage": "agent_uncertain"}

    if not dry_run:
        res = requests.patch(
            f"{SUPABASE_URL}/rest/v1/submissions",
            headers={**sb_headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{sub['id']}"},
            json=patch, timeout=15,
        )
        res.raise_for_status()
    return note


def approve_submission(sub, verdict, dry_run):
    """agent_approve_submission RPC'sini service key ile çağırır — submission'ı
    'approved' işaretler, opportunities'e taşır, belgelerini ekler.
    (ok: bool, detay: str) döndürür.

    RPC (migration 099) admin guard'sızdır; EXECUTE izni yalnızca service_role'a
    verildiği için bu script çağırabilir ve aynı sıkı yayın kapılarını DB'de
    tekrarlar. Hata (kategori bulunamadı, ağ sorunu,
    RPC henüz uygulanmamış vb.) çalıştırmayı durdurmaz — çağıran güvenli tarafa
    düşer: submission'ı öneri olarak 'pending' bırakır."""
    if dry_run:
        return True, "(dry-run — RPC çağrılmadı)"
    try:
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/agent_approve_submission",
            headers=sb_headers(),
            json={"p_id": sub["id"], "p_validation": verdict},
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


def fill_summary_tr(opportunity_id, dry_run):
    """Yeni onaylanan fırsata Türkçe özet + Türkçe uygunluk metni yazar.

    NEDEN BURADA: opportunities.summary_tr'yi yalnızca tek-seferlik backfill
    dolduruyordu. Bu akıştan geçen her YENİ fırsat özetsiz kalıyor, sonuç
    kartında açıklama bloğu hiç görünmüyordu — yani kaynak sorun her onayda
    yeniden üretiliyordu. Onay RPC'si opportunity_id döndürdüğü için üretimi
    doğrudan buraya bağlıyoruz.

    Özet KOZMETİKTİR: üretilemezse (LLM erişilemedi, JSON bozuk, alan boş)
    onay geri alınmaz — kayıt özetsiz yayına girer, backfill script'i sonra
    tamamlayabilir. Bu yüzden tüm hatalar yutulur, yalnız log'lanır.
    """
    if dry_run or not opportunity_id:
        return

    # Lazy import: backfill_summary_tr bu modülü (validate_submissions) import
    # ediyor — üstte import edersek dairesel import olur.
    try:
        import backfill_summary_tr as bf
    except ImportError as e:
        print(f"  ! özet üretilemedi (modül yüklenemedi: {e})")
        return

    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/opportunities",
            headers=sb_headers(),
            params={"id": f"eq.{opportunity_id}",
                    "select": ("id,title,category_id,funding_type,funding_notes,"
                               "eligibility_notes,deadline,deadline_notes,"
                               "host_countries,language_requirement,age_min,"
                               "age_max,study_level")},
            timeout=20,
        )
        res.raise_for_status()
        rows = res.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"  ! özet üretilemedi (kayıt okunamadı: {e})")
        return

    if not isinstance(rows, list) or not rows:
        print("  ! özet üretilemedi (yeni kayıt bulunamadı)")
        return
    opp = rows[0]

    categories = bf.fetch_categories()
    summary, elig = bf.generate(opp, categories.get(opp.get("category_id")))
    body = {}
    if summary:
        body["summary_tr"] = summary
    if elig:
        body["eligibility_notes_tr"] = elig
    if not body:
        print("  ! özet üretilemedi (model boş döndü) — backfill sonra tamamlar")
        return

    try:
        bf.patch(opportunity_id, body)
    except requests.exceptions.RequestException as e:
        print(f"  ! özet yazılamadı ({e})")
        return
    print(f"  · Türkçe özet yazıldı ({len(body)} alan)")


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
    # bool("false") True olduğu için truthy dönüşüm yapma. Model yalnızca gerçek
    # JSON boolean true gönderirse doğrulama başarılı sayılır (fail-closed).
    boolean_fields = (
        "kategori_uygun", "tek_firsat", "dogrudan_firsat_sayfasi",
        "son_tarih_dogrulandi", "finansman_dogrulandi",
        "ulke_dogrulandi", "uygunluk_dogrulandi",
    )
    return {
        "durum": durum,
        **{field: v.get(field) is True for field in boolean_fields},
        "guven": guven,
        "gerekce": (str(v.get("gerekce") or "").strip()[:300] or "(gerekçe yok)"),
    }


def _llm_chat(system_prompt, user_text):
    """Sağlayıcıya (OpenAI-uyumlu chat/completions) tek istek atar.

    (icerik, finish_reason) döndürür; hata hâlinde (None, None). Karar
    ayrıştırma bilinçli olarak DIŞARIDA: aynı taşıyıcıyı hem doğrulama
    kararı hem revize değerlendirmesi kullanıyor, yalnız şemaları farklı.
    """
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
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
            return None, None
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
        return None, None
    try:
        choice = res.json()["choices"][0]
        text = choice["message"]["content"]
        finish = choice.get("finish_reason")
    except (KeyError, IndexError, ValueError):
        print("  ! LLM yanıtı beklenen yapıda değil")
        return None, None
    return text, finish


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
        f"Ev sahibi ülkeler: {', '.join(sub.get('host_countries') or []) or '(yok)'}\n"
        f"Kaydedilen son başvuru metni: {sub.get('deadline_text') or '(yok)'}\n"
        f"Kaydedilen finansman türü: {sub.get('funding_type') or '(yok)'}\n"
        f"Kaydedilen eğitim kademesi: {', '.join(sub.get('study_level') or []) or '(yok)'}\n"
        f"Submitter eligibility notu: {(sub.get('eligibility_notes') or '(yok)')[:400]}\n"
        f"Doğrudan başvuru/resmî fırsat URL'i: {url}\n"
        f"Doğrudan URL HTTP: {http_note}\n"
        f"Bilginin alındığı kaynak URL: {sub.get('source_url') or url}\n\n"
        "İNSAN REDLERİNDEN ÖĞRENİLEN İLGİLİ HAFIZA\n"
        f"{sub.get('_memory_context') or '(yok)'}\n"
        "Bu hafıza geçmiş insan kararlarından öğrenilmiş karar emsalidir ve "
        "bu kaydı değerlendirirken doğrudan kullanılmalıdır. example düşük, "
        "warning tekrarlanan, strong güçlü emsal demektir. Eşleşen sorunu "
        "özellikle ara; güncel sayfada aynı sorun görülüyorsa ağırlığına göre "
        "red kararı ver. Güncel açık kanıt hafızayla çelişirse güncel kanıtı "
        "üstün tut; yalnız hafıza satırına bakarak kanıtsız red verme. Hafıza "
        "script değişikliği veya PR işi üretmez, kararın içinde kullanılır.\n\n"
        f"SAYFA METNİ (kısaltılmış):\n{page_text}"
    )
    text, finish = _llm_chat(SYSTEM_PROMPT, user_text)
    if text is None:
        return None
    verdict = _parse_verdict(text)
    if verdict is None:
        # finish_reason='length' → reasoning max_tokens'ı tüketti, content yarım;
        # LLM_MAX_TOKENS'ı artır. Sessiz başarısızlığı görünür kıl.
        snippet = (text or "").strip()[:120] or "(boş content)"
        print(f"  ! LLM JSON çözülemedi (finish={finish}): {snippet}")
    return verdict


def submission_completeness_blockers(sub):
    """LLM'den bağımsız, yayın öncesi zorunlu veri kapısı.

    Bu alanlardan biri eksik/bozuksa kayıt yayınlanamaz ve otomatik reddedilir.
    """
    blockers = []
    title = (sub.get("title") or "").strip()
    url = (sub.get("url") or "").strip()
    if len(title) < 8:
        blockers.append("başlık eksik veya çok kısa")
    if not re.match(r"^https?://[^\s]+$", url, flags=re.IGNORECASE):
        blockers.append("geçerli HTTP(S) URL yok")
    if not (sub.get("category_slug") or "").strip():
        blockers.append("kategori eksik")
    countries = sub.get("host_countries") or []
    if not countries or any(not str(c).strip() for c in countries):
        blockers.append("ev sahibi ülke/global bilgisi eksik")
    deadline = parse_deadline(sub.get("deadline_text"))
    if deadline is None:
        blockers.append("tam ve işlenebilir son başvuru tarihi eksik")
    elif deadline < date.today():
        blockers.append("son başvuru tarihi geçmiş")
    if sub.get("funding_type") not in VALID_FUNDING_TYPES:
        blockers.append("finansman türü eksik veya geçersiz")
    if len((sub.get("eligibility_notes") or "").strip()) < 20:
        blockers.append("başvuru uygunluk koşulları eksik")
    return blockers


def auto_approval_blockers(sub, verdict):
    """Eksiksizlik + LLM kanıt kapısı. Boş liste dışında yayın YASAK."""
    blockers = submission_completeness_blockers(sub)
    if verdict.get("durum") != "acik":
        blockers.append("fırsatın açık olduğu kesin değil")
    if verdict.get("guven") != "yuksek":
        blockers.append("LLM güveni yüksek değil")
    if verdict.get("kategori_uygun") is not True:
        blockers.append("kategori uygunluğu doğrulanmadı")
    if (len((verdict.get("gerekce") or "").strip()) < 10
            or verdict.get("gerekce") == "(gerekçe yok)"):
        blockers.append("kanıta dayalı gerekçe eksik")
    evidence_labels = {
        "tek_firsat": "tek bir fırsat olduğu doğrulanmadı",
        "dogrudan_firsat_sayfasi": "doğrudan fırsat sayfası olduğu doğrulanmadı",
        "son_tarih_dogrulandi": "son tarih sayfadan doğrulanmadı",
        "finansman_dogrulandi": "finansman sayfadan doğrulanmadı",
        "ulke_dogrulandi": "ülke/global bilgisi sayfadan doğrulanmadı",
        "uygunluk_dogrulandi": "başvuru koşulları sayfadan doğrulanmadı",
    }
    blockers.extend(label for field, label in evidence_labels.items()
                    if verdict.get(field) is not True)
    return blockers


def evidence_rejection_reasons(verdict):
    """Sayfada yanlışlığı doğrulanan alanlar pending'e değil redde gider."""
    labels = {
        "tek_firsat": "sayfa tek bir fırsat değil",
        "dogrudan_firsat_sayfasi": "link doğrudan başvuru/resmî fırsat sayfası değil",
        "son_tarih_dogrulandi": "kayıtlı güncel son tarih sayfayla uyuşmuyor",
        "finansman_dogrulandi": "finansman bilgisi sayfayla uyuşmuyor",
        "ulke_dogrulandi": "ülke/global bilgisi sayfayla uyuşmuyor",
        "uygunluk_dogrulandi": "uygunluk koşulları sayfayla uyuşmuyor",
    }
    return [label for field, label in labels.items() if verdict.get(field) is not True]


def decide(verdict):
    """Karar dict'i -> (eylem, gerekce). eylem: reddet | onayla | belirsiz.
    Otomatik ONAY yalnızca açık + kategori-uygun + güven yüksek olduğunda;
    otomatik RED yalnızca yüksek/orta güvenli net olumsuzlarda."""
    if verdict["guven"] == "dusuk":
        return "belirsiz", verdict["gerekce"]
    if verdict["durum"] == "kapali" and verdict["guven"] in ("yuksek", "orta"):
        return "reddet", verdict["gerekce"]
    if not verdict["kategori_uygun"] and verdict["guven"] == "yuksek":
        return "reddet", verdict["gerekce"]
    if (verdict["durum"] == "acik" and verdict["kategori_uygun"]
            and verdict["guven"] == "yuksek"):
        return "onayla", verdict["gerekce"]
    return "belirsiz", verdict["gerekce"]


def fetch_target_and_source(sub, url):
    """Doğrudan hedefi ve (varsa) ayrı kaynak/kanıt sayfasını getirir.

    (status, final_url, err, target_text, source_text) döndürür. Başvuru formu
    az metin taşısa bile ajan tarih/kategori bilgisini kaynak sayfadan okuyabilsin
    diye ikisi birlikte toplanır. Hem doğrulama hem revize akışı bunu kullanır.
    """
    status, final_url, html, err = fetch_page(url)
    source_url = (sub.get("source_url") or "").strip()
    source_text = ""
    if source_url and _norm_url(source_url) != _norm_url(url):
        source_status, _source_final, source_html, _source_err = fetch_page(source_url)
        if source_status == 200 and source_html:
            source_text = page_to_text(source_html)
    target_text = page_to_text(html) if status == 200 and html else ""
    return status, final_url, err, target_text, source_text


# ─── Revize akışı (105) ───────────────────────────────────────────────────────
# Admin panelinde "Revize" denen insan gönderileri buraya düşer. Ajan bu
# kayıtlarda KARAR VERMEZ: adminin notunu okur, kaynağı yeniden çeker, notu
# kanıtla yanıtlar ve YALNIZ BOŞ alanlara öneri üretir. Sonuç human_review'e
# döner; onay da red de insanındır (099'daki koruma da bunu DB'de zorunlu kılar).

REVISION_SYSTEM_PROMPT = """Sen "Fırsat Eşitliği" platformunun submission doğrulama ajanısın. Bu platform Türkiye'deki gençlere yurt dışı burs, staj, gönüllülük, yaz okulu, gençlik projesi ve değişim programı gibi ÜCRETSİZ veya FONLU fırsatları toplar.

Bu görevde bir ADMIN, kullanıcıdan gelen bir kaydı yayına almadan önce senden REVİZE istedi. Sana adminin isteği, kaydın mevcut hâli, BUGÜNÜN TARİHİ ve fırsatın kaynak sayfasının metni verilir.

GÖREVİN:
1) ADMİNİN İSTEĞİNİ DOĞRUDAN YANITLA. Asıl işin bu. Cevabını YALNIZCA sayfa metnindeki kanıta dayandır; sayfada karşılığı yoksa "sayfada doğrulanamadı" de. Tahmin etme, uydurma.
2) Sana "BOŞ ALANLAR" olarak verilen alanlar için öneri üret. Listede olmayan hiçbir alana değer verme — dolu alanlar admin/kullanıcı verisidir, sana ait değildir. Bir boş alanın değerini sayfadan kesin okuyamıyorsan o alanı null bırak; yanlış doldurmak boş bırakmaktan kötüdür.
3) karar ver:
   - "uygun": Adminin sorduğu şey sayfada doğrulandı ve kayıt yayına uygun görünüyor.
   - "sorunlu": Sayfada kayıtla çelişen ya da yayına engel bir durum var (başvurular kapanmış, ücretli/ticari program, kategori yanlış, link doğrudan fırsat sayfası değil, sayfa birden çok fırsatı listeleyen bir derleme...).
   - "belirsiz": Kanıt yetersiz; insanın bakması gerekiyor.

TARİH KURALI: Açık/kapalı yorumunu yalnız sana verilen "BUGÜNÜN TARİHİ"ne göre yap, kendi tarih bilgine güvenme.

ALAN BİÇİMLERİ (uymayan öneri atılır):
- category_slug: scholarship | volunteering | youth_project | internship | summer_school | exchange
- funding_type: full (tam burs) | partial (kısmi) | free (ücretsiz katılım) | stipend (harçlık)
- host_countries: ISO 3166-1 alfa-2 kod dizisi, ör. ["DE","FR"]. Program dünyanın her yerinde/uzaktan ise ["*"].
- deadline_text: gün-ay-yıl içeren tam tarih, ör. "15 Eylül 2026". Yıl veya ay eksikse null ver.
- study_level: bachelor | master | phd | any değerlerinden dizi
- age_min / age_max: tam sayı
- eligibility_notes / funding_notes / language_requirement: Türkçe kısa metin

ÇIKTI: Yanıtını yalnızca şu alanlara sahip TEK bir JSON nesnesi olarak ver. Markdown, ``` işareti veya açıklama EKLEME:
{"karar": "uygun|sorunlu|belirsiz", "admin_notu_cevabi": "<adminin isteğine Türkçe doğrudan cevap, 1-2 cümle>", "gerekce": "<kararını dayandıran kanıtı belirten Türkçe tek cümle>", "alan_onerileri": {"category_slug": null, "host_countries": null, "deadline_text": null, "funding_type": null, "funding_notes": null, "eligibility_notes": null, "language_requirement": null, "study_level": null, "age_min": null, "age_max": null}}"""

# Ajanın doldurabileceği alanlar → admin panelinde göründükleri Türkçe adları.
# Sıra notta ve ekranda aynı okunsun diye anlamlı: önce sınıflandırma, sonra
# koşullar. title/url bilerek YOK — kaydın kimliği ajana emanet edilmez.
FILLABLE_FIELDS = {
    "category_slug": "kategori",
    "host_countries": "ev sahibi ülke",
    "deadline_text": "son başvuru tarihi",
    "funding_type": "finansman türü",
    "funding_notes": "finansman notu",
    "eligibility_notes": "uygunluk koşulları",
    "language_requirement": "dil şartı",
    "study_level": "eğitim kademesi",
    "age_min": "min yaş",
    "age_max": "max yaş",
}

REVISION_LABELS = {"uygun": "UYGUN GÖRÜNÜYOR", "sorunlu": "SORUNLU", "belirsiz": "BELİRSİZ"}


def admin_revision_request(sub):
    """admin_note içinden yalnız adminin yazdığı revize isteğini ayıklar."""
    note = (sub.get("admin_note") or "").strip()
    if note.startswith(REVISION_MARKER):
        return note[len(REVISION_MARKER):].strip()
    return note


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return not value or all(not str(v).strip() for v in value)
    return False


def empty_fields(sub):
    """Kayıtta boş duran ve ajanın doldurabileceği alanların anahtarları."""
    return [f for f in FILLABLE_FIELDS if _is_blank(sub.get(f))]


def sanitize_suggestions(sub, oneriler):
    """LLM'in alan önerilerini DB'ye yazılabilir hâle süzer → (patch, etiketler).

    İKİ KURAL:
      1) Yalnız BOŞ alanlar doldurulur. Kullanıcının veya adminin yazdığı hiçbir
         değer ajan tarafından ezilmez — revize "yeniden yaz" değil "tamamla".
      2) Her değer bu projedeki geçerli kümeye/biçime uymak zorunda; uymayan
         öneri sessizce atılır ve alan boş kalır (insan doldurur).
    """
    if not isinstance(oneriler, dict):
        return {}, []
    blanks = set(empty_fields(sub))
    patch = {}

    def offered(field):
        return field in blanks and oneriler.get(field) is not None

    if offered("category_slug"):
        v = str(oneriler["category_slug"]).strip().lower()
        if v in VALID_CATEGORY_SLUGS:
            patch["category_slug"] = v

    if offered("funding_type"):
        v = str(oneriler["funding_type"]).strip().lower()
        if v in VALID_FUNDING_TYPES:
            patch["funding_type"] = v

    if offered("host_countries"):
        raw = oneriler["host_countries"]
        codes = []
        for c in (raw if isinstance(raw, list) else [raw])[:8]:
            c = str(c).strip().upper()
            if c in ("*", "ALL", "GLOBAL", "WORLDWIDE"):
                codes = ["*"]
                break
            if re.fullmatch(r"[A-Z]{2}", c):
                codes.append(c)
        if codes:
            patch["host_countries"] = codes

    if offered("deadline_text"):
        v = str(oneriler["deadline_text"]).strip()[:120]
        dl = parse_deadline(v)
        # Ajan tarih uyduramasın: metin gerçekten bir güne çözülmeli ve geçmişte
        # olmamalı. Çözülmüyorsa alan boş kalır; eksik tarih zaten yayın kapısı.
        if dl is not None and dl >= date.today():
            patch["deadline_text"] = v

    if offered("eligibility_notes"):
        v = " ".join(str(oneriler["eligibility_notes"]).split())[:600]
        if len(v) >= 20:                      # completeness kapısıyla aynı eşik
            patch["eligibility_notes"] = v

    for field, limit in (("funding_notes", 300), ("language_requirement", 200)):
        if offered(field):
            v = " ".join(str(oneriler[field]).split())[:limit]
            if v:
                patch[field] = v

    if offered("study_level"):
        raw = oneriler["study_level"]
        levels = sorted({str(x).strip().lower() for x in
                         (raw if isinstance(raw, list) else [raw])}
                        & VALID_STUDY_LEVELS)
        if levels:
            patch["study_level"] = levels

    for field in ("age_min", "age_max"):
        if offered(field):
            try:
                v = int(oneriler[field])
            except (TypeError, ValueError):
                continue
            if 10 <= v <= 99:
                patch[field] = v
    lo = patch.get("age_min", sub.get("age_min"))
    hi = patch.get("age_max", sub.get("age_max"))
    if lo is not None and hi is not None and lo > hi:
        patch.pop("age_min", None)           # tutarsız aralık hiç yazılmasın
        patch.pop("age_max", None)

    return patch, [label for field, label in FILLABLE_FIELDS.items() if field in patch]


def _parse_revision(text):
    """LLM'in revize yanıtından değerlendirmeyi çıkarır (savunmacı)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    v = _loads_lenient(t)
    if v is None:
        return None
    karar = str(v.get("karar") or "").strip().lower()
    if karar not in REVISION_LABELS:
        karar = "belirsiz"                    # tanınmayan karar → temkinli
    oneriler = v.get("alan_onerileri")
    return {
        "karar": karar,
        "cevap": str(v.get("admin_notu_cevabi") or "").strip()[:400],
        "gerekce": str(v.get("gerekce") or "").strip()[:300],
        "alan_onerileri": oneriler if isinstance(oneriler, dict) else {},
    }


def review_revision_with_llm(sub, url, http_note, page_text, istek, blanks):
    """Revize kaydını LLM'e sorar. Hata → None."""
    alan_listesi = ", ".join(f"{f} ({FILLABLE_FIELDS[f]})" for f in blanks) or "(boş alan yok)"
    user_text = (
        f"BUGÜNÜN TARİHİ: {date.today().isoformat()}\n\n"
        "ADMİNİN REVİZE İSTEĞİ (asıl görevin bu):\n"
        f"{istek or '(not yazılmamış — kaydı genel olarak denetle)'}\n\n"
        "SUBMISSION (kayıttaki hâli)\n"
        f"Başlık: {sub.get('title') or '(yok)'}\n"
        f"Kategori slug: {sub.get('category_slug') or '(BOŞ)'}\n"
        f"Ev sahibi ülkeler: {', '.join(sub.get('host_countries') or []) or '(BOŞ)'}\n"
        f"Son başvuru metni: {sub.get('deadline_text') or '(BOŞ)'}\n"
        f"Finansman türü: {sub.get('funding_type') or '(BOŞ)'}\n"
        f"Finansman notu: {sub.get('funding_notes') or '(BOŞ)'}\n"
        f"Eğitim kademesi: {', '.join(sub.get('study_level') or []) or '(BOŞ)'}\n"
        f"Dil şartı: {sub.get('language_requirement') or '(BOŞ)'}\n"
        f"Yaş aralığı: {sub.get('age_min') if sub.get('age_min') is not None else '(BOŞ)'}"
        f" - {sub.get('age_max') if sub.get('age_max') is not None else '(BOŞ)'}\n"
        f"Uygunluk notu: {(sub.get('eligibility_notes') or '(BOŞ)')[:400]}\n"
        f"Gönderenin açıklaması: {(sub.get('description') or '(yok)')[:300]}\n"
        f"Doğrudan başvuru/resmî fırsat URL'i: {url}\n"
        f"Doğrudan URL HTTP: {http_note}\n"
        f"Bilginin alındığı kaynak URL: {sub.get('source_url') or url}\n\n"
        f"BOŞ ALANLAR (yalnız bunlara öneri ver): {alan_listesi}\n\n"
        "İNSAN REDLERİNDEN ÖĞRENİLEN İLGİLİ HAFIZA\n"
        f"{sub.get('_memory_context') or '(yok)'}\n"
        "Bu hafıza geçmiş insan kararlarından öğrenilmiş emsaldir; aynı sorunu "
        "bu sayfada da görüyorsan karara yansıt, yalnız hafızaya bakarak "
        "kanıtsız 'sorunlu' deme.\n\n"
        f"SAYFA METNİ (kısaltılmış):\n{page_text}"
    )
    text, finish = _llm_chat(REVISION_SYSTEM_PROMPT, user_text)
    if text is None:
        return None
    result = _parse_revision(text)
    if result is None:
        snippet = (text or "").strip()[:120] or "(boş content)"
        print(f"  ! LLM revize JSON'u çözülemedi (finish={finish}): {snippet}")
    return result


def apply_revision_result(sub, karar, ozet, field_patch, dry_run):
    """Revize sonucunu yazar: doldurulan alanlar + not + human_review.

    status'a DOKUNULMAZ ('pending' kalır) ve hiçbir onay/red RPC'si çağrılmaz —
    admin bu kaydı bilerek elde tutmuş, kararı ajan kendiliğinden veremez."""
    note = f"{AGENT_MARKER} REVİZE SONUCU ({REVISION_LABELS.get(karar, 'BELİRSİZ')}) — {ozet}"[:2000]
    patch = {**field_patch, "admin_note": note, "review_stage": "human_review"}
    if not dry_run:
        res = requests.patch(
            f"{SUPABASE_URL}/rest/v1/submissions",
            headers={**sb_headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{sub['id']}"},
            json=patch, timeout=20)
        res.raise_for_status()
    return note


def process_revision(sub, dry_run, known_urls, stats):
    """Admin'in revize istediği tek kaydı işler. Tally etiketi döndürür."""
    istek = admin_revision_request(sub)
    print(f"\n• [REVİZE] {(sub.get('title') or '(başlıksız)')[:60]}")
    print(f"  Admin isteği: {(istek or '(not yok)')[:120]}")

    url = (sub.get("url") or "").strip()
    if not url:
        apply_decision(sub, "reddet", "Kayıtta doğrudan URL yok — kaynak doğrulanamıyor", dry_run)
        print("  URL yok → SORUNLU")
        return "revize"

    if _norm_url(url) in known_urls:
        apply_decision(sub, "reddet",
                       "Kopya: bu URL zaten yayındaki bir fırsatta mevcut", dry_run)
        print("  KOPYA (opportunities'te var) → SORUNLU")
        return "revize"

    status, final_url, err, target_text, source_text = fetch_target_and_source(sub, url)
    if status in (404, 410):
        apply_decision(sub, "reddet", f"Ölü bağlantı (HTTP {status})", dry_run)
        print(f"  HTTP {status} → SORUNLU")
        return "revize"

    page_text = target_text
    if source_text:
        page_text = (f"DOĞRUDAN HEDEF SAYFA:\n{target_text or '(metin yok / bot koruması)'}\n\n"
                     f"KAYNAK KANIT SAYFASI:\n{source_text}")[:PAGE_CHAR_LIMIT]
    if len(page_text.strip()) < 80:
        apply_decision(sub, "belirsiz",
                       f"Sayfadan anlamlı metin çıkmadı (HTTP {status or err}) — "
                       "adminin isteği kaynaktan doğrulanamadı", dry_run)
        print("  İçerik çok ince → BELİRSİZ")
        return "revize"

    blanks = empty_fields(sub)
    http_note = str(status) if status is not None else f"ulaşılamadı: {err}"
    if final_url and _norm_url(final_url) != _norm_url(url):
        http_note += f" (yönlendirildi: {final_url})"
    print(f"  Boş alanlar: {', '.join(FILLABLE_FIELDS[f] for f in blanks) or 'yok'}")
    print(f"  Hedef HTTP {status}, revize değerlendirmesi → LLM ({LLM_MODEL}) sorgulanıyor...")
    stats["llm_calls"] += 1
    result = review_revision_with_llm(sub, url, http_note, page_text, istek, blanks)
    time.sleep(LLM_MIN_INTERVAL)

    if result is None:
        apply_decision(sub, "belirsiz",
                       "LLM revize değerlendirmesi alınamadı — tekrar çalıştır", dry_run)
        print("  LLM hatası → BELİRSİZ")
        return "revize"

    field_patch, filled = sanitize_suggestions(sub, result["alan_onerileri"])
    kalan = [FILLABLE_FIELDS[f] for f in blanks if f not in field_patch]

    parcalar = [p for p in (result["cevap"], result["gerekce"]) if p] or ["(gerekçe yok)"]
    if filled:
        parcalar.append("Ajanın doldurduğu alanlar: " + ", ".join(filled))
    if kalan:
        parcalar.append("Hâlâ boş: " + ", ".join(kalan))
    ozet = " | ".join(parcalar)

    apply_revision_result(sub, result["karar"], ozet, field_patch, dry_run)
    print(f"  → REVİZE SONUCU ({REVISION_LABELS[result['karar']]}) — {ozet[:200]}")
    return "revize"


# ─── Akış ─────────────────────────────────────────────────────────────────────

def process(sub, dry_run, known_urls, seen_urls, stats):
    """Tek submission — heuristikler, gerekirse LLM. Tally etiketi döndürür."""
    # Admin'in revize istediği kayıt bu hattan geçmez: orada ajan onay/red
    # kapılarını değil, adminin sorusunu işletir (bkz. process_revision).
    if is_revision(sub):
        return process_revision(sub, dry_run, known_urls, stats)

    print(f"\n• {(sub.get('title') or '(başlıksız)')[:60]}")
    url = (sub.get("url") or "").strip()
    if not url:
        apply_decision(sub, "reddet", "Eksik kayıt: doğrudan URL yok", dry_run)
        print("  URL yok → REDDET")
        return "llm_red"
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

    # Yayın kapısı 1 — eksik kayıt için LLM çağrısı bile yapma. Agent bu
    # alanları kendi tahminiyle doldurmaz; doğrudan reddeder.
    completeness_blockers = submission_completeness_blockers(sub)
    if completeness_blockers:
        reason = "Eksik kayıt: " + "; ".join(completeness_blockers)
        apply_decision(sub, "reddet", reason, dry_run)
        print(f"  {reason} → REDDET")
        return "llm_red"

    link_blockers = direct_link_blockers(sub)
    if link_blockers:
        reason = "Hatalı link: " + "; ".join(link_blockers)
        apply_decision(sub, "reddet", reason, dry_run)
        print(f"  {reason} → REDDET")
        return "llm_red"

    status, final_url, err, target_text, source_text = fetch_target_and_source(sub, url)

    # Heuristik 3 — ölü bağlantı (LLM'siz)
    if status in (404, 410):
        apply_decision(sub, "reddet", f"Ölü bağlantı (HTTP {status})", dry_run)
        print(f"  HTTP {status} → REDDET")
        return "olu_link"
    if final_url and _url_host(final_url) in AGGREGATOR_DOMAINS:
        apply_decision(sub, "reddet",
                       "Doğrudan link kaynak/derleme sitesine yönlendiriyor", dry_run)
        print("  Link kaynak/derleme sitesine yönlendi → REDDET")
        return "llm_red"
    if status is None:
        if not source_text:
            apply_decision(sub, "reddet", f"Doğrudan link doğrulanamadı: {err}", dry_run)
            print("  Doğrudan link doğrulanamadı → REDDET")
            return "llm_red"
    if status != 200:
        # 403/429/5xx hedefte bot koruması olabilir. Ayrı kaynak kanıtı varsa
        # LLM karar verir; yoksa doğrulanamayan link olarak reddedilir.
        if not source_text:
            apply_decision(sub, "reddet",
                           f"Doğrudan link HTTP {status} döndü; doğrulanamadı", dry_run)
            print(f"  HTTP {status} → REDDET")
            return "llm_red"

    # KATMAN 2 — hedef sayfa + ayrı kaynak kanıtı birlikte değerlendirilir.
    page_text = target_text
    if source_text:
        page_text = (f"DOĞRUDAN HEDEF SAYFA:\n{target_text or '(metin yok / bot koruması)'}\n\n"
                     f"KAYNAK KANIT SAYFASI:\n{source_text}")[:PAGE_CHAR_LIMIT]
    if len(page_text) < 80:
        apply_decision(sub, "belirsiz",
                       "Sayfadan anlamlı metin çıkmadı (JS-ağırlıklı olabilir)", dry_run)
        print("  İçerik çok ince → BELİRSİZ")
        return "belirsiz"

    http_note = str(status) if status is not None else f"ulaşılamadı: {err}"
    if final_url and _norm_url(final_url) != norm:
        http_note += f" (yönlendirildi: {final_url})"
    print(f"  Hedef HTTP {status}, kayıt doğrulaması → LLM ({LLM_MODEL}) sorgulanıyor...")
    stats["llm_calls"] += 1
    verdict = judge_with_llm(sub, url, http_note, page_text)
    time.sleep(LLM_MIN_INTERVAL)                   # sağlayıcı RPM sınırı

    if verdict is None:
        apply_decision(sub, "belirsiz", "LLM kararı alınamadı", dry_run)
        print("  LLM hatası → BELİRSİZ")
        return "belirsiz"

    print(f"  LLM: durum={verdict['durum']} "
          f"kategori_uygun={verdict['kategori_uygun']} guven={verdict['guven']}")

    evidence_errors = evidence_rejection_reasons(verdict)
    if evidence_errors:
        reason = f"{verdict['gerekce']} — " + "; ".join(evidence_errors)
        apply_decision(sub, "reddet", reason, dry_run)
        print(f"  → REDDET — {reason}")
        return "llm_red"

    # Kaynak sayfa hedefi doğrulasa bile agent hedefi HTTP 200 ile açamadıysa
    # yayınlama. Bu, gerçek teknik belirsizliktir ve admin kuyruğuna girebilir.
    if status != 200:
        reason = (f"Tarih ve doğrudan hedef kaynakta doğrulandı; ancak hedef "
                  f"agent tarafından açılamadı (HTTP {status or 'bağlantı hatası'})")
        apply_decision(sub, "belirsiz", reason, dry_run)
        print(f"  → BELİRSİZ — {reason}")
        return "belirsiz"

    eylem, gerekce = decide(verdict)

    if eylem == "onayla":
        # Yayın kapısı 2 — modelin tüm kanıt doğrulamaları açıkça true değilse
        # otomatik onay yok. Eksik/orta güvenli kayıt admin kuyruğunda kalır.
        blockers = auto_approval_blockers(sub, verdict)
        if blockers:
            guarded_reason = "Otomatik yayın kapısı: " + "; ".join(blockers)
            apply_decision(sub, "reddet", guarded_reason, dry_run)
            print(f"  → REDDET — {guarded_reason}")
            return "llm_red"

        # Tüm kapılar geçti → RPC ile otomatik onay. RPC aynı alanları ve LLM
        # validation nesnesini DB tarafında tekrar doğrular.
        # Notu önce yaz: durum değiştiğinde kalıcı karar olayı gerekçeyi de
        # aynı snapshot içinde kaydetsin.
        apply_decision(sub, "onayla", gerekce, dry_run)
        ok, detay = approve_submission(sub, verdict, dry_run)
        if ok:
            print(f"  → OTOMATİK ONAY — {gerekce}  [{detay}]")
            # detay "opportunity_id=<uuid>" biçiminde; özet üretimi için gerekli.
            new_id = detay.split("=", 1)[1] if detay.startswith("opportunity_id=") else None
            fill_summary_tr(new_id, dry_run)
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
    parser.add_argument("--feedback-report", action="store_true",
                        help="İnsan adminlerin red nedenlerini kaynak ve neden "
                             "koduna göre salt okunur raporla")
    parser.add_argument("--reaudit-agent-approvals", action="store_true",
                        help="Eski gerçek agent onaylarını yeni sıkı kapıya göre "
                             "salt okunur sınıflandır")
    parser.add_argument("--output", help="Re-audit JSON raporunun dosya yolu")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("Eksik ortam değişkeni: SUPABASE_SERVICE_ROLE_KEY — .env kontrol et.",
              file=sys.stderr)
        sys.exit(1)

    if args.feedback_report:
        try:
            run_feedback_report()
        except requests.exceptions.RequestException as e:
            print(f"Red geri bildirimi okunamadı: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.reaudit_agent_approvals:
        try:
            run_agent_approval_reaudit(args)
        except requests.exceptions.RequestException as e:
            print(f"Agent onayları yeniden incelenemedi: {e}", file=sys.stderr)
            sys.exit(1)
        return

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
    try:
        memories = fetch_agent_memories()
    except requests.exceptions.RequestException as e:
        print(f"Agent hafızası okunamadı: {e}", file=sys.stderr)
        sys.exit(1)
    for sub in subs:
        sub["_memory_context"] = memory_context_for(sub, memories)
    seen_urls = set()
    stats = {"llm_calls": 0}
    tally = {k: 0 for k in
             ("kopya", "sure_gecti", "olu_link", "llm_red",
              "onaylandi", "oner", "belirsiz", "revize")}

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
    if tally["revize"]:
        print(f"REVİZE     : {tally['revize']}   (admin isteği incelendi — "
              f"kayıt human_review'e döndü, kararı insan verir)")
    heuristik = reddedildi - tally["llm_red"]
    print(f"\nLLM çağrısı: {stats['llm_calls']} / {len(subs)} "
          f"— heuristikler {heuristik} kararı LLM'siz çözdü.")


if __name__ == "__main__":
    main()
