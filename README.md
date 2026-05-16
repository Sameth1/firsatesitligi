# fırsateşitliği

> Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu.

🌐 **Canlı site:** [firsatesitligi.vercel.app](https://firsatesitligi.vercel.app)

---

## Nedir?

fırsateşitliği, Türkiye'deki gençlerin yurt dışı burs, staj, gönüllülük, yaz okulu ve değişim programlarına kolayca ulaşmasını sağlayan açık kaynaklı bir web uygulamasıdır.

Kullanıcılar yaş, eğitim seviyesi, bölüm, hedef ülke ve dil bilgisi gibi kişisel parametrelerini girerek kendilerine uygun fırsatları filtreler. Tam eşleşme bulunamadığında filtreler otomatik olarak gevşetilerek her zaman sonuç döndürülür.

---

## Özellikler

- 🎓 Burs, staj, gönüllülük, yaz okulu, gençlik projesi, değişim programı
- 🔍 Kişiselleştirilmiş eşleştirme (yaş, eğitim seviyesi, bölüm, ülke, dil)
- 🧠 Akıllı fallback: filtreler kademeli gevşetilerek her zaman sonuç gösterilir
- 🆓 Tamamen ücretsiz, hesap gerektirmez
- 🇹🇷 Türkçe arayüz, mobil uyumlu

---

## Teknoloji

- **Frontend:** Next.js 16, React, TypeScript
- **Backend:** Supabase (PostgreSQL + RPC)
- **Deploy:** Vercel

---

## GEO & SEO Çalışmaları

Bu proje, bir lisans tezi kapsamında **GEO (Generative Engine Optimization)** uygulamalarının pratik örneği olarak geliştirilmiştir.

### Yapılan teknik optimizasyonlar:

| Optimizasyon | Açıklama |
|---|---|
| `public/llms.txt` | Yapay zekalara site tanıtımı (yeni standart) |
| `public/robots.txt` | GPTBot, Claude-Web gibi AI tarayıcılara erişim izni |
| Schema.org JSON-LD | Google ve yapay zekaların içeriği yapılandırılmış okuması |
| OpenGraph / Twitter Card | Sosyal medya paylaşım önizlemeleri |
| `sitemap.xml` | Otomatik site haritası üretimi |
| Google Search Console | İndeksleme kaydı ve doğrulaması |
| Keywords & Canonical URL | Temel SEO meta etiketleri |

### Legitimizasyon çalışmaları:
- LinkedIn paylaşımı
- ProductHunt lansmanı
- GitHub açık kaynak katkısı

---

## Kurulum

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

---

## Otonom Fırsat Keşif Ajanı

Bu proje kapsamında, web'i otonom olarak tarayan bir yapay zeka ajanı geliştirilmiştir. Ajan; arama sorguları üretmek, web sayfalarını analiz etmek ve fırsat içeren kaynakları tespit etmek için büyük dil modellerinden (LLM) yararlanmaktadır.

### Nasıl Çalışır?

```
1. LLM → Arama sorguları üretir
         ("scholarships for Turkish students apply 2025" vb.)
         ↓
2. DuckDuckGo → Sorgularla web'de arama yapılır
         ↓
3. Her sayfa ziyaret edilir → LLM analiz eder:
   "Bu sayfada Türklerin başvurabileceği uluslararası fırsat var mı? Kaç tane?"
         ↓
4. Fırsat içeren sayfalar siteler_sayili.txt'e kaydedilir
   (fırsat sayısına göre sıralı)
```

### Kullanılan Teknolojiler

| Bileşen | Teknoloji | Açıklama |
|---|---|---|
| LLM | Groq API (Llama 4) | Sorgu üretimi ve sayfa analizi |
| Arama | DuckDuckGo (ddgs) | Ücretsiz, API key gerektirmez |
| Web scraping | requests + BeautifulSoup | Sayfa içeriği çekme |
| Çıktı | siteler_sayili.txt | Fırsat sayısına göre sıralı URL listesi |

### Örnek Çıktı

Tek çalıştırmada (5 tur, ~140 URL taranarak) elde edilen sonuçlar:

```
59 firsat -- https://www.rit.edu/studyabroad/international-fellowship-search
23 firsat -- https://freevolunteering.net/
19 firsat -- https://scholarships.af/82555/opportunities-apply-february/
14 firsat -- https://uniplusglobal.com/blog/507/list-of-fully-funded-summer-programs/
11 firsat -- https://scholarshipexpo.com/list-of-summer-programs-in-the-world-2026/
...
Toplam: 31 sayfa, ~184 tahmini fırsat
```

### Çalıştırma

```bash
# Gerekli paketler
pip3 install groq requests beautifulsoup4 python-dotenv ddgs

# .env dosyasına ekle
GROQ_API_KEY=gsk_...

# Yeni siteler bul
python3 site_bulucu.py --rounds 5

# Bulunan sitelerdeki fırsat sayısını say
python3 say_firsatlari.py
```

### Akademik Bağlam

Bu ajan, GEO (Generative Engine Optimization) tez çalışmasının veri toplama altyapısını oluşturmaktadır. LLM'lerin yapılandırılmamış web içeriğini anlayıp sınıflandırabilmesi, geleneksel kural tabanlı scraperların yetersiz kaldığı senaryolarda belirgin bir avantaj sağlamaktadır. Ajan, her çalıştırmada farklı arama sorguları üreterek keşif kapsamını genişletmekte; bu sayede önceden bilinmeyen fırsat kaynaklarına ulaşılabilmektedir.

---

## Katkı

PR ve issue'lar hoş karşılanır. Yeni fırsat eklemek veya hata bildirmek için GitHub Issues kullanabilirsiniz.

---

## Lisans

MIT

---

*Bu proje bir lisans tezi kapsamında geliştirilmiştir. GEO (Generative Engine Optimization) ve SEO uygulamalarının pratik örneği olarak akademik literatüre katkı sağlamayı hedeflemektedir.*
