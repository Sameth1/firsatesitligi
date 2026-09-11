"""
Tek-seferlik backfill — opportunities.summary_tr + eligibility_notes_tr
=======================================================================
101_opportunity_summary_tr.sql ile eklenen iki Türkçe kolonu, halihazırda
AKTİF olan fırsatlar için LLM ile doldurur:

  • summary_tr           → fırsatın ne olduğunu anlatan 2-3 cümlelik Türkçe özet
                           (ne tür bir program, kime, ne sağlıyor).
  • eligibility_notes_tr → mevcut eligibility_notes'un Türkçe karşılığı.
                           SADECE çeviri/sadeleştirme; yeni bilgi eklenmez.
                           eligibility_notes boşsa bu alan da boş bırakılır.

Kaynak yalnızca DB'deki alanlardır (başlık, kategori, fon türü, notlar).
Sayfa ÇEKİLMEZ. Model emin değilse ilgili alan null bırakılır — yanlış bilgi
yazmaktansa boş kalması yeğdir (kart Türkçe yoksa orijinali gösteriyor).

LLM katmanı validate_submissions.py'den yeniden kullanılır (OpenAI-uyumlu
chat/completions, NVIDIA NIM, NVIDIA_API_KEY). Yeni sağlayıcı eklenmez.

Gerekli ortam değişkenleri (.env):
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, NVIDIA_API_KEY

Önkoşul: docs/sql/101_opportunity_summary_tr.sql çalıştırılmış olmalı
(`npm run db:101` veya Supabase SQL Editor).

Kullanım (varsayılan DRY-RUN — hiçbir şey yazılmaz):
    python backfill_summary_tr.py                 # tüm aday kayıtlar, sadece önizleme
    python backfill_summary_tr.py --limit 5       # önce 5 kayıtta dene
    python backfill_summary_tr.py --limit 5 --apply
    python backfill_summary_tr.py --apply         # tamamını yaz
    python backfill_summary_tr.py --force --apply # zaten dolu olanları da yenile
"""

import os
import sys
import time
import argparse

import requests
from dotenv import load_dotenv

# LLM katmanı: sağlayıcı ayarları (NVIDIA NIM, OpenAI-uyumlu chat/completions),
# retry/429/503 davranışı ve savunmacı JSON çözücü burada tanımlı. Kopyalamak
# yerine import ediyoruz ki model/base_url/anahtar tek yerde kalsın.
import validate_submissions as vs

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hxwhelhcrynqatadijxz.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

FETCH_LIMIT = 1000          # DB'den çekilen aktif kayıt tavanı
SUMMARY_MAX_CHARS = 600     # 2-3 cümle bunun altında kalır; üstü şişkin sayılır
ELIGIBILITY_MAX_CHARS = 1200
# Model "bilmiyorum" derse alanı yazmak yerine boş bırakmak için kaba filtre.
_REFUSAL_MARKERS = (
    "bilinmiyor", "belirsiz", "bilgi yok", "yeterli bilgi",
    "emin değilim", "bilgi bulunmuyor", "veri yok", "null",
)

SYSTEM_PROMPT = """Sen "Fırsat Eşitliği" platformunun Türkçe içerik editörüsün. Platform, Türkiye'deki gençlere yurt dışı burs, staj, gönüllülük, yaz okulu ve değişim programlarını listeler.

Sana bir fırsat kaydının DB alanları verilir. Görevin, sonuç kartında gösterilecek Türkçe metinleri üretmek.

ÜRETECEĞİN ALANLAR

1) summary_tr — 2-3 CÜMLE Türkçe özet.
   • Şunu anlat: ne tür bir program, kimin için, ne sağlıyor.
   • Sade, somut, bilgilendirici dil. Pazarlama dili YOK, abartı YOK
     ("harika", "kaçırılmayacak", "eşsiz fırsat" gibi ifadeler yasak).
   • Okuyucuya doğrudan hitap etme, emir kipi kullanma ("başvur!" yok).
   • YALNIZCA sana verilen başlık/kategori/fon türü/notlardan çıkarılabilecek
     şeyleri yaz. Genel bilginden ekleme yapma, kurum hakkında ezberden
     bilgi verme.
   • EMİN OLMADIĞIN DETAYI YAZMA: burs tutarı, para birimi, kesin tarih,
     kontenjan sayısı, süre, şehir — verilen alanlarda açıkça yoksa yazma.
   • En fazla 400 karakter.

2) eligibility_notes_tr — verilen "Uygunluk notu (orijinal)" metninin Türkçesi.
   • Bu bir ÇEVİRİ + sadeleştirme işidir. YENİ BİLGİ EKLEME, koşul çıkarma,
     yorum katma. Orijinalde olmayan hiçbir şart yazma.
   • Orijinal zaten Türkçeyse hafifçe sadeleştir ya da aynen bırak.
   • Orijinal boş/yoksa bu alan MUTLAKA null olacak.

BELİRSİZLİK KURALI
Bir alanı doğru üretecek kadar bilgin yoksa o alana null yaz. Uydurmak yerine
boş bırakmak DAHA İYİDİR; boş alanda site orijinal metni gösterir.

ÇIKTI BİÇİMİ
Yalnızca ham JSON döndür. Markdown, kod bloğu, açıklama yazma.
{"summary_tr": "...", "eligibility_notes_tr": "..."}
Üretemediğin alan için string yerine JSON null kullan."""


def patch(opp_id, body):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/opportunities",
                       headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                       params={"id": f"eq.{opp_id}"}, json=body, timeout=20)
    r.raise_for_status()


def fetch_categories():
    """category_id → Türkçe kategori etiketi. Tablo okunamazsa boş dict."""
    try:
        rows = requests.get(f"{SUPABASE_URL}/rest/v1/categories", headers=H,
                            params={"select": "id,label_tr"}, timeout=20).json()
        if isinstance(rows, list):
            return {c["id"]: c.get("label_tr") for c in rows if c.get("id")}
    except (requests.exceptions.RequestException, ValueError, KeyError, TypeError) as e:
        print(f"  ! kategoriler okunamadı ({e}) — kategori etiketi olmadan devam")
    return {}


def fetch_opportunities():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/opportunities", headers=H,
        params={"is_active": "eq.true",
                "select": ("id,title,category_id,funding_type,funding_notes,"
                           "eligibility_notes,deadline,deadline_notes,host_countries,"
                           "language_requirement,age_min,age_max,study_level,"
                           "summary_tr,eligibility_notes_tr"),
                "order": "title.asc",
                "limit": str(FETCH_LIMIT)}, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise SystemExit(f"Beklenmeyen Supabase yanıtı: {str(rows)[:300]}")
    return rows


def blank(v):
    return not (v or "").strip()


def needs_work(opp, force):
    """Bu kayıt için LLM çağrısı gerekiyor mu?"""
    if force:
        return True
    if blank(opp.get("summary_tr")):
        return True
    # Özeti var ama uygunluk metni İngilizce kalmışsa onu da tamamla.
    return (not blank(opp.get("eligibility_notes"))
            and blank(opp.get("eligibility_notes_tr")))


def build_user_text(opp, category_label):
    def val(v):
        if isinstance(v, list):
            return ", ".join(str(x) for x in v) or "(yok)"
        s = str(v).strip() if v is not None else ""
        return s or "(yok)"

    yas = "(yok)"
    if opp.get("age_min") or opp.get("age_max"):
        yas = f"{opp.get('age_min') or '?'}–{opp.get('age_max') or '?'}"

    return (
        "FIRSAT KAYDI (DB alanları)\n"
        f"Başlık: {val(opp.get('title'))}\n"
        f"Kategori: {val(category_label)}\n"
        f"Fon türü: {val(opp.get('funding_type'))}\n"
        f"Fon notu: {val(opp.get('funding_notes'))[:600]}\n"
        f"Ev sahibi ülkeler: {val(opp.get('host_countries'))}\n"
        f"Eğitim kademesi: {val(opp.get('study_level'))}\n"
        f"Yaş aralığı: {yas}\n"
        f"Dil şartı: {val(opp.get('language_requirement'))}\n"
        f"Son başvuru: {val(opp.get('deadline'))} / {val(opp.get('deadline_notes'))[:200]}\n"
        f"Uygunluk notu (orijinal): {val(opp.get('eligibility_notes'))[:1500]}\n\n"
        "Bu alanlardan yola çıkarak summary_tr ve eligibility_notes_tr üret. "
        "Yukarıda geçmeyen hiçbir bilgiyi ekleme."
    )


def _chat(user_text):
    """OpenAI-uyumlu chat/completions çağrısı — sağlayıcı ayarları, retry ve
    429/503 backoff davranışı validate_submissions ile AYNI (vs.LLM_* sabitleri).
    validate_submissions.judge_with_llm submission'a özel prompt'a bağlı olduğu
    için doğrudan çağrılamıyor; taşıyıcı katman burada tekrarlanıyor."""
    body = {
        "model": vs.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0,
        "max_tokens": vs.LLM_MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {vs.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    res = None
    for attempt in range(3):
        try:
            res = requests.post(f"{vs.LLM_BASE_URL}/chat/completions",
                                headers=headers, json=body, timeout=45)
        except requests.exceptions.RequestException as e:
            print(f"  ! LLM ağ hatası: {e}")
            return None
        if res.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            # NVIDIA ücretsiz endpoint'i yoğunlukta 503 döndürebiliyor. 429 için
            # daha uzun, diğer geçici sunucu hataları için kademeli kısa backoff.
            if res.status_code == 429:
                wait, reason = 20 * (attempt + 1), "rate limit"
            else:
                wait, reason = 5 * (attempt + 1), "geçici sunucu hatası"
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
        return choice["message"]["content"], choice.get("finish_reason")
    except (KeyError, IndexError, ValueError):
        print("  ! LLM yanıtı beklenen yapıda değil")
        return None


def clean_field(raw, max_chars):
    """Model çıktısını temizler; kullanılamazsa None döndürür (uydurma yerine boş)."""
    if raw is None or isinstance(raw, bool):
        return None
    text = str(raw).strip().strip('"').strip()
    if not text or len(text) < 15:
        return None
    low = text.lower()
    if low in ("null", "none", "-", "yok") or any(low.startswith(m) for m in _REFUSAL_MARKERS):
        return None
    if len(text) > max_chars:
        return None                      # şişmiş çıktı — yazmaktansa boş bırak
    return text


def generate(opp, category_label):
    """(summary_tr, eligibility_notes_tr) — üretilemeyen alan None."""
    out = _chat(build_user_text(opp, category_label))
    if out is None:
        return None, None
    text, finish = out
    t = (text or "").strip()
    if t.startswith("```"):                       # ```json ... ``` sarmalını söker
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = vs._loads_lenient(t)                   # savunmacı JSON çözücü (ortak)
    if not isinstance(data, dict):
        snippet = t[:120] or "(boş content)"
        print(f"  ! LLM JSON çözülemedi (finish={finish}): {snippet}")
        return None, None

    summary = clean_field(data.get("summary_tr"), SUMMARY_MAX_CHARS)
    elig = clean_field(data.get("eligibility_notes_tr"), ELIGIBILITY_MAX_CHARS)
    # Orijinal uygunluk notu yoksa Türkçesi de olamaz — model uydurduysa at.
    if blank(opp.get("eligibility_notes")):
        elig = None
    return summary, elig


def main():
    ap = argparse.ArgumentParser(
        description="opportunities.summary_tr + eligibility_notes_tr için "
                    "tek-seferlik LLM backfill'i (varsayılan DRY-RUN).")
    ap.add_argument("--apply", action="store_true",
                    help="DB'ye yaz (varsayılan dry-run)")
    ap.add_argument("--force", action="store_true",
                    help="Zaten dolu olan alanları da yeniden üret")
    ap.add_argument("--limit", type=int, default=None,
                    help="En fazla N kayıt işle (önce birkaç kayıtta denemek için)")
    args = ap.parse_args()

    if not SUPABASE_KEY:
        print("Eksik ortam değişkeni: SUPABASE_SERVICE_ROLE_KEY — .env kontrol et.",
              file=sys.stderr)
        return 1
    if not vs.LLM_API_KEY:
        print("Eksik ortam değişkeni: NVIDIA_API_KEY — .env kontrol et.", file=sys.stderr)
        print("NVIDIA NIM anahtarı (ücretsiz): https://build.nvidia.com", file=sys.stderr)
        return 1

    cats = fetch_categories()
    rows = fetch_opportunities()
    if rows and "summary_tr" not in rows[0]:
        print("opportunities.summary_tr kolonu yok — önce 101 migration'ını "
              "çalıştır (npm run db:101).", file=sys.stderr)
        return 1

    todo = [o for o in rows if needs_work(o, args.force)]
    if args.limit is not None:
        todo = todo[:args.limit]

    mode = "CANLI — DB GÜNCELLENECEK" if args.apply else "DRY-RUN — DB'ye yazılmaz"
    print(f"{len(rows)} aktif kayıt · {len(todo)} işlenecek · model {vs.LLM_MODEL}\n"
          f"{mode}\n" + "─" * 72)

    n_sum = n_elig = n_skip = n_err = 0
    for i, o in enumerate(todo, 1):
        title = (o.get("title") or "")[:52]
        summary, elig = generate(o, cats.get(o.get("category_id")))
        if summary is None and elig is None:
            n_err += 1
            print(f"[{i}/{len(todo)}] ⚠ üretilemedi — {title}")
            time.sleep(vs.LLM_MIN_INTERVAL)
            continue

        body = {}
        if summary and (args.force or blank(o.get("summary_tr"))):
            body["summary_tr"] = summary
            n_sum += 1
        if elig and (args.force or blank(o.get("eligibility_notes_tr"))):
            body["eligibility_notes_tr"] = elig
            n_elig += 1

        if not body:
            n_skip += 1
            print(f"[{i}/{len(todo)}] · değişiklik yok — {title}")
            time.sleep(vs.LLM_MIN_INTERVAL)
            continue

        print(f"[{i}/{len(todo)}] ✓ {title}")
        if "summary_tr" in body:
            print(f"      özet    : {body['summary_tr']}")
        if "eligibility_notes_tr" in body:
            print(f"      uygunluk: {body['eligibility_notes_tr'][:200]}")
        if args.apply:
            try:
                patch(o["id"], body)
            except requests.exceptions.RequestException as e:
                n_err += 1
                print(f"      ! yazma hatası: {e}")
        time.sleep(vs.LLM_MIN_INTERVAL)      # sağlayıcı RPM sınırı

    print("─" * 72)
    print(f"summary_tr yazılacak/yazıldı          : {n_sum}")
    print(f"eligibility_notes_tr yazılacak/yazıldı: {n_elig}")
    print(f"değişiklik yok: {n_skip}   |   hata/üretilemedi: {n_err}")
    if not args.apply:
        print("\n(DRY-RUN — yazılmadı. Uygulamak için: --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
