@AGENTS.md

# Proje Bağlamı — Tez Çalışması

Bu repo, **Utku Akalın**'ın lisans tezi kapsamında geliştirilen açık kaynaklı bir web uygulamasıdır.

## Proje: fırsateşitliği

Türkiye'deki gençlerin yurt dışı burs, staj, gönüllülük, yaz okulu ve değişim programlarına erişimini kolaylaştıran ücretsiz bir platform.

- **Canlı site:** https://firsatesitligi.vercel.app
- **GitHub:** https://github.com/Sameth1/firsatesitligi
- **Katkıda bulunan fork:** https://github.com/utkuakalin/firsatesitligi

## Tez Konusu

Tez, **GEO (Generative Engine Optimization)** üzerine — yani web sitelerinin yapay zeka sistemleri (ChatGPT, Claude, Gemini vb.) tarafından nasıl daha iyi anlaşılabileceği ve önerilebileceği üzerine odaklanmaktadır.

Bu proje, tezin pratik uygulama ayağıdır. Teorik çerçeve ile gerçek bir ürün üzerindeki GEO uygulamaları karşılaştırılmaktadır.

## Bu Projede Yapılan GEO & SEO Çalışmaları

### Teknik Optimizasyonlar
- `public/llms.txt` — Yapay zekalara site tanıtımı (yeni standart)
- `public/robots.txt` — GPTBot, Claude-Web gibi AI tarayıcılara erişim izni
- `src/app/layout.tsx` — OpenGraph, Twitter Card, keywords, canonical URL
- `src/app/layout.tsx` — Schema.org JSON-LD (WebApplication tipi)
- `src/app/sitemap.ts` — Otomatik sitemap.xml üretimi
- Google Search Console kaydı ve doğrulaması

### Legitimizasyon Çalışmaları
- LinkedIn paylaşımı
- ProductHunt draft lansmanı
- GitHub açık kaynak katkısı (fork + PR)

### Geliştirilen Özellikler
- Kullanıcı profil formuna "Halihazırdaki en yüksek eğitim seviyesi" filtresi eklendi (`p_highest_edu`)
- Akıllı fallback sistemi: eşleşme yoksa filtreler kademeli gevşetilir

## Tez için Claude'a Sorulabilecek Sorular

- "Bu projede GEO açısından ne yaptık, tez için açıkla"
- "llms.txt'in akademik literatürdeki karşılığı nedir"
- "Schema.org'un yapay zeka görünürlüğüne etkisini anlat"
- "Bu projeyi örnek çalışma olarak teze nasıl dahil ederim"
- "GEO ile SEO arasındaki farkları akademik dille yaz"
