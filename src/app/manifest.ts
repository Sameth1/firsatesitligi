import type { MetadataRoute } from 'next'

/**
 * Web App Manifest — siteyi telefona kurulabilir bir uygulamaya çeviren dosya.
 *
 * Next bu dosyayı /manifest.webmanifest olarak yayınlar ve <head>'e link'ini
 * kendisi ekler; elle <link rel="manifest"> koymak gerekmiyor.
 *
 * background_color bilinçli olarak sitenin en koyu zemin jetonu (--ink-900):
 * uygulama açılırken gösterilen splash ekranı bu renkte olur, beyaz bir flaş
 * yaşanmaz.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/',
    name: 'fırsateşitliği — Yurt Dışı Burs, Staj ve Gönüllülük',
    short_name: 'fırsateşitliği',
    description:
      "Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu. "
      + 'Burs, gönüllülük, staj, yaz okulu ve değişim programlarını yaşına, '
      + 'bölümüne ve hedef ülkene göre filtrele.',
    lang: 'tr',
    dir: 'ltr',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: '#070616',
    theme_color: '#0D0A26',
    categories: ['education'],
    icons: [
      { src: '/app-icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/app-icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      // maskable: Android ikonu daireye/kareye kırpar; içerik merkezdeki
      // güvenli alanda kalsın diye ayrı, kepi daha küçük bir sürüm.
      { src: '/app-icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
