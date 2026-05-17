# fırsateşitliği

> Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu.

🌐 **Canlı site:** [firsatesitligi.vercel.app](https://firsatesitligi.vercel.app)
📦 **Depo:** [github.com/Sameth1/firsatesitligi](https://github.com/Sameth1/firsatesitligi)

---

## İçindekiler

- [Nedir?](#nedir)
- [Özellikler](#özellikler)
- [Mimari](#mimari)
- [Kullanılan Teknolojiler](#kullanılan-teknolojiler)
- [Submission Pipeline — Topluluk Kaynaklı Fırsat Akışı](#submission-pipeline--topluluk-kaynaklı-fırsat-akışı)
- [Otomasyon Scriptleri](#otomasyon-scriptleri)
- [Veritabanı](#veritabanı)
- [GEO & SEO Çalışmaları](#geo--seo-çalışmaları)
- [Yol Haritası](#yol-haritası)
- [Kurulum](#kurulum)
- [Katkı](#katkı)
- [Lisans](#lisans)

---

## Nedir?

fırsateşitliği, Türkiye'deki gençlerin yurt dışı burs, staj, gönüllülük, yaz okulu ve değişim programlarına kolayca ulaşmasını sağlayan açık kaynaklı bir web uygulamasıdır.

Kullanıcılar yaş, eğitim seviyesi, bölüm, hedef ülke ve dil bilgisi gibi kişisel parametrelerini girerek kendilerine uygun fırsatları filtreler. Tam eşleşme bulunamadığında filtreler otomatik olarak gevşetilerek her zaman sonuç döndürülür.

Proje, bir lisans tezi kapsamında **GEO (Generative Engine Optimization)** uygulamalarının pratik örneği olarak geliştirilmektedir.

---

## Özellikler

- 🎓 Burs, staj, gönüllülük, yaz okulu, gençlik projesi, değişim programı
- 🔍 Kişiselleştirilmiş eşleştirme (yaş, eğitim seviyesi, bölüm, ülke, dil)
- 🧠 Akıllı fallback: filtreler kademeli gevşetilerek her zaman sonuç gösterilir
- 🆓 Tamamen ücretsiz, hesap gerektirmez
- 🇹🇷 Türkçe arayüz, mobil uyumlu
- 🤝 Topluluk katkısı: kullanıcılar fırsat önerebilir (submission sistemi)
- 🤖 Yapay zeka destekli otomasyon: fırsat keşfi, scraping ve doğrulama

---

## Mimari

Proje üç katmandan oluşur:

```
┌─────────────────────────────────────────────────────────────┐
│  WEB UYGULAMASI  (Next.js 16 · Vercel)                        │
│  Kullanıcı filtre formu → eşleştirme → fırsat sonuçları       │
└───────────────────────────┬───────────────────────────────────┘
                            │  Supabase JS / RPC
┌───────────────────────────▼───────────────────────────────────┐
│  VERİTABANI  (Supabase · PostgreSQL)                          │
│  opportunities · submissions · categories · admins · documents │
│  RPC fonksiyonları · Row Level Security (RLS)                  │
└───────────────────────────▲───────────────────────────────────┘
                            │  REST / service-role key
┌───────────────────────────┴───────────────────────────────────┐
│  OTOMASYON KATMANI  (Python scriptleri)                        │
│  keşif → scraping → doğrulama → otomatik onay                  │
└─────────────────────────────────────────────────────────────────┘
```

- **Web uygulaması** son kullanıcıya yöneliktir; yalnızca yayında (`opportunities`) olan fırsatları gösterir.
- **Veritabanı** tek doğruluk kaynağıdır; iş mantığının kritik kısmı RPC fonksiyonlarında ve RLS politikalarında yaşar.
- **Otomasyon katmanı** içerik hattını besler: web'i tarayıp aday fırsatları bulur, `submissions` tablosuna öneri olarak yazar, doğrular ve uygun olanları yayına taşır.

---

## Kullanılan Teknolojiler

### Web Uygulaması

| Bileşen | Teknoloji |
|---|---|
| Framework | Next.js 16.2.4 (App Router) |
| UI | React 19.2.4, TypeScript 5 |
| Stil | Tailwind CSS 4 |
| Backend / DB | Supabase (PostgreSQL + RPC + RLS + Auth) |
| Supabase istemcileri | `@supabase/ssr`, `@supabase/supabase-js` |
| Deploy | Vercel |
| Lint | ESLint 9 (`eslint-config-next`) |

### Otomasyon Katmanı (Python 3)

| Bileşen | Teknoloji | Kullanım |
|---|---|---|
| HTTP & parsing | `requests`, `BeautifulSoup4` | Sayfa çekme ve HTML ayrıştırma |
| Konfigürasyon | `python-dotenv` | `.env` ortam değişkenleri |
| Keşif LLM'i | Groq API (Llama 4) | Arama sorgusu üretimi, sayfa analizi |
| Doğrulama LLM'i | Google Gemini API (`gemini-2.5-flash`) | Submission açık/kapalı & kategori doğrulaması |
| Genel scraping | Jina Reader | Herhangi bir URL → temiz markdown |
| Web arama | DuckDuckGo (`ddgs`) | API anahtarı gerektirmeyen arama |

---

## Submission Pipeline — Topluluk Kaynaklı Fırsat Akışı

Fırsatlar doğrudan yayına girmez; bir **inceleme hattından** geçer. Bu, hem kullanıcı önerilerini hem de otomatik scraping çıktısını tek bir denetlenebilir akışta toplar.

```
  KAYNAKLAR                      İNCELEME                       YAYIN
  ─────────                      ────────                       ─────

  Kullanıcı önerisi  ┐
  nasilgitmis.com    ├──►  submissions tablosu  ──►  validate_     ──►  opportunities
  Idealist           │     (status = 'pending')      submissions.py     (canlı site)
  Genel URL (Jina)   ┘                                    │
                                                          │
                            ┌─────────────────────────────┤
                            │                             │
                       Katman 1                       Katman 2
                       Heuristik (LLM'siz)             Gemini LLM
                       • kopya URL                     • durum: açık/kapalı?
                       • süresi geçmiş                 • kategori uygun mu?
                       • ölü bağlantı (404/410)        • güven: yüksek/orta/düşük
                            │                             │
                            ▼                             ▼
                       otomatik RED              açık+uygun+güvenli → OTOMATİK ONAY
                                                 kapalı/kategori-dışı → RED
                                                 belirsiz → insan incelemesi
```

### Karar mantığı (`validate_submissions.py`)

1. **Katman 1 — Heuristikler (ücretsiz, LLM'siz).** Kopya URL, süresi geçmiş `deadline_text` veya 404/410 dönen bağlantı → otomatik **RED**. Bu kararlar LLM kotası harcamaz.
2. **Katman 2 — Gemini LLM (yalnızca belirsiz HTTP-200 vakalar).** Sayfa açık ama durumu net değilse Gemini'ye sorulur. Gemini üç çıktı verir: `durum` (açık/kapalı/belirsiz), `kategori_uygun` (true/false), `guven` (yüksek/orta/düşük).
3. **Karar:**
   - `kapalı` + güven yüksek/orta → **RED**
   - `kategori_uygun=false` + güven yüksek → **RED**
   - `açık` + `kategori_uygun` + güven yüksek/orta → **OTOMATİK ONAY** (`agent_approve_submission` RPC)
   - diğer tüm durumlar → **belirsiz**, `pending` kalır, insan panelden inceler

Yanlış reddetmeyi önlemek için olumsuz kararlar yalnızca açık kanıt varken verilir; tereddütte karar insana bırakılır. Otomatik onay yapılan kayıtlarda `reviewed_by` alanı `NULL` bırakılır — "insan değil otomasyon onayladı" denetim sinyali.

### `agent_approve_submission` RPC'si

Standart `approve_submission()` RPC'si çağıranın admin olmasını (`auth.uid()`) şart koşar; bu yüzden service-role anahtarıyla çalışan scriptler onay yapamaz. `docs/sql/094_agent_approve_submission.sql` migration'ı, **admin guard'ı olmayan** ikiz bir fonksiyon ekler. Güvenlik sınırı, fonksiyonu çağırma yetkisidir: `EXECUTE` izni `public`/`anon`/`authenticated`'tan alınıp **yalnızca `service_role`'a** verilir.

---

## Otomasyon Scriptleri

Tüm scriptler kök dizinde yer alır; `.env` dosyasından `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (service-role RLS'i bypass eder) okur.

| Script | Görev | Hedef |
|---|---|---|
| `site_bulucu.py` | Groq + DuckDuckGo ile fırsat barındıran web sayfalarını keşfeder | `siteler.txt` |
| `say_firsatlari.py` | Bulunan sitelerdeki tahmini fırsat sayısını sayar | `siteler_sayili.txt` |
| `nasilgitmis_scraper.py` | nasilgitmis.com'dan Erasmus+/ESC/burs/staj fırsatlarını çeker | `submissions` (pending) |
| `idealist_scraper.py` | idealist.org gönüllülük fırsatlarını çeker | `opportunities` |
| `agent_reach_url_scraper.py` | Herhangi bir fırsat URL'sini Jina Reader'dan geçirip alan çıkarımı yapar | `submissions` (pending) |
| `validate_submissions.py` | İki katmanlı doğrulama ajanı (heuristik + Gemini), uygun önerileri otomatik onaylar | `submissions` → `opportunities` |
| `link_audit_runner.py` | Aktif fırsatların `official_url`'lerine GET atıp sağlık durumunu kaydeder | `opportunities.last_url_check_*` |
| `fix_broken_links.py` | Bozuk URL'leri aday URL'lerle değiştirir; hiçbiri çalışmazsa `is_active=false` yapar | `opportunities` |

### Otonom Fırsat Keşif Ajanı (`site_bulucu.py` + `say_firsatlari.py`)

Web'i otonom tarayan yapay zeka ajanı; arama sorguları üretmek, sayfaları analiz etmek ve fırsat içeren kaynakları tespit etmek için LLM'lerden yararlanır:

```
1. LLM → Arama sorguları üretir ("scholarships for Turkish students apply 2025" vb.)
2. DuckDuckGo → Sorgularla web'de arama yapılır
3. Her sayfa LLM ile analiz edilir: "Türklerin başvurabileceği fırsat var mı? Kaç tane?"
4. Fırsat içeren sayfalar siteler_sayili.txt'e fırsat sayısına göre sıralı kaydedilir
```

Tek çalıştırma örneği (5 tur, ~140 URL): 31 sayfa, ~184 tahmini fırsat tespit edildi.

---

## Veritabanı

PostgreSQL şeması Supabase üzerinde barınır. Migration'lar `docs/sql/` altında numaralı SQL dosyaları olarak tutulur ve idempotenttir (tekrar çalıştırılabilir).

| Migration | İçerik |
|---|---|
| `004_language_and_filter_options.sql` | Dil ve filtre seçenekleri |
| `005_smart_language_filter.sql` | Akıllı dil filtresi |
| `006_submissions_v2.sql` | Topluluk katkısı: `submissions` tablosu, `admins`, `approve/reject/request_revision` RPC'leri, RLS, IP rate-limit |
| `007_opportunity_url_health.sql` | URL sağlık kontrolü kolonları |
| `090_one_shot_after_006.sql` | 006 sonrası tek seferlik düzeltmeler |
| `091_admin_rpc_grants.sql` | Admin RPC çalıştırma yetkileri |
| `092_approve_submission_funding_default.sql` | `approve_submission` için funding varsayılanı |
| `093_match_filter_is_active.sql` | Eşleştirme filtresine `is_active` koşulu |
| `094_agent_approve_submission.sql` | Service-role otomatik onay RPC'si (admin guard'sız) |

Migration'lar `npm run db:0XX` script'leriyle bağlı Supabase projesine uygulanır (bkz. `package.json`).

Ana tablolar:
- **`opportunities`** — yayındaki fırsatlar; web uygulamasının gösterdiği veri.
- **`submissions`** — inceleme bekleyen öneriler (`status`: pending / approved / needs_revision / rejected).
- **`categories`** — fırsat kategorileri (burs, staj, gönüllülük, ...).
- **`admins`** — panel erişimi olan kullanıcılar.
- **`documents`** — fırsata bağlı başvuru belgeleri.

---

## GEO & SEO Çalışmaları

Proje, **GEO (Generative Engine Optimization)** — web sitelerinin ChatGPT, Claude, Gemini gibi yapay zeka sistemleri tarafından daha iyi anlaşılması ve önerilmesi — üzerine bir tez çalışmasının pratik uygulama ayağıdır.

### Yapılan teknik optimizasyonlar

| Optimizasyon | Açıklama |
|---|---|
| `public/llms.txt` | Yapay zekalara site tanıtımı (yeni standart) |
| `public/robots.txt` | GPTBot, Claude-Web gibi AI tarayıcılara erişim izni |
| Schema.org JSON-LD | İçeriğin yapılandırılmış (WebApplication) okunması |
| OpenGraph / Twitter Card | Sosyal medya paylaşım önizlemeleri |
| `sitemap.xml` | Otomatik site haritası üretimi |
| Google Search Console | İndeksleme kaydı ve doğrulaması |
| Keywords & Canonical URL | Temel SEO meta etiketleri |

### Legitimizasyon çalışmaları
- LinkedIn paylaşımı · ProductHunt lansmanı · GitHub açık kaynak katkısı

---

## Yol Haritası

### ✅ Tamamlananlar

- Next.js tabanlı web platformu ve kişiselleştirilmiş eşleştirme (kademeli fallback)
- Supabase şeması: `opportunities`, `submissions`, `categories`, `admins`, `documents`
- RPC + RLS tabanlı güvenlik modeli
- Topluluk katkısı sistemi: submission formu, admin paneli, onay/red RPC'leri
- GEO & SEO optimizasyonları (`llms.txt`, JSON-LD, sitemap, robots.txt)
- Otonom fırsat keşif ajanı (`site_bulucu.py` + `say_firsatlari.py`)
- Site-spesifik scraper'lar (`nasilgitmis_scraper.py`, `idealist_scraper.py`)
- Genel amaçlı URL scraper'ı (`agent_reach_url_scraper.py`, Jina Reader)
- Link sağlığı otomasyonu (`link_audit_runner.py`, `fix_broken_links.py`)
- `agent_approve_submission` service-role onay RPC'si (migration 094)
- İki katmanlı doğrulama ajanı + otomatik onay mantığı (`validate_submissions.py`)

### 🚧 Devam Edenler

- **LLM doğrulama hattının canlıya alınması.** `validate_submissions.py` kod olarak tamamlandı; otomatik onay akışı `agent_approve_submission` RPC'sine bağlandı. Şu an Gemini ücretsiz tier kota sınırı nedeniyle bekliyor — model değişimi veya faturalandırma ile çözülecek.
- Migration `094`'ün bağlı Supabase projesine uygulanması (canlı otomatik onaydan önce gerekli).
- `nasilgitmis_scraper.py` ile toplanan pending submission'ların doğrulama hattından geçirilmesi.

### 🗺️ Planlananlar

- Scraping + doğrulama hattının zamanlanmış (cron) çalıştırılması
- Scraper hata sayaçlarının ayrıştırılması (süresi geçmiş / ulaşılamadı / gerçek hata)
- Kaynak site havuzunun genişletilmesi
- Tez için GEO/SEO etki ölçümlerinin raporlanması

---

## Kurulum

### Web Uygulaması

```bash
git clone https://github.com/Sameth1/firsatesitligi.git
cd firsatesitligi
npm install
```

`.env.local` dosyası oluştur:

```
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

```bash
npm run dev
```

### Otomasyon Scriptleri (Python)

```bash
pip install requests beautifulsoup4 python-dotenv groq ddgs
```

Kök dizinde `.env` dosyası oluştur (bu dosya `.gitignore`'dadır — gizli kalır):

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...        # RLS'i bypass eder, gizli tut
GEMINI_API_KEY=AIza...                  # validate_submissions.py için
GROQ_API_KEY=gsk_...                    # site_bulucu.py için
```

Örnek çalıştırma:

```bash
# Yeni fırsat siteleri keşfet
python site_bulucu.py --rounds 5
python say_firsatlari.py

# nasilgitmis.com'dan fırsatları submissions'a çek
python nasilgitmis_scraper.py

# Bekleyen submission'ları doğrula (DB'ye yazmadan önizleme)
python validate_submissions.py --dry-run
python validate_submissions.py --limit 10     # ilk 10 kaydı işle
```

> ⚠️ `SUPABASE_SERVICE_ROLE_KEY` ve `GEMINI_API_KEY`/`GROQ_API_KEY` hassas anahtarlardır. `.env` dosyası asla commit'lenmemelidir.

---

## Katkı

PR ve issue'lar hoş karşılanır. Yeni fırsat eklemek için canlı sitedeki "fırsat öner" formunu ya da GitHub Issues'u kullanabilirsiniz.

---

## Lisans

MIT

---

*Bu proje bir lisans tezi kapsamında geliştirilmektedir. GEO (Generative Engine Optimization) ve SEO uygulamalarının pratik örneği olarak akademik literatüre katkı sağlamayı hedeflemektedir.*
