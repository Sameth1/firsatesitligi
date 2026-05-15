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

## Katkı

PR ve issue'lar hoş karşılanır. Yeni fırsat eklemek veya hata bildirmek için GitHub Issues kullanabilirsiniz.

---

## Lisans

MIT

---

*Bu proje bir lisans tezi kapsamında geliştirilmiştir. GEO (Generative Engine Optimization) ve SEO uygulamalarının pratik örneği olarak akademik literatüre katkı sağlamayı hedeflemektedir.*
