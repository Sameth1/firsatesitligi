/**
 * Çevrimdışı yedek sayfası. Service worker, ağ yokken ve istenen sayfa
 * önbellekte de bulunamadığında buraya düşer.
 *
 * Bilinçli olarak WebGL'siz ve bağımlılıksız: bu sayfa tam da hiçbir şeyin
 * yüklenemediği anda gösteriliyor.
 */
export default function OfflinePage() {
  return (
    <main style={{
      minHeight: '100vh',
      display: 'grid',
      placeItems: 'center',
      padding: '32px 20px',
      background: 'radial-gradient(120% 90% at 50% 0%, #241C5C 0%, #120E33 45%, #070616 100%)',
      color: '#F4F2FF',
      textAlign: 'center',
    }}>
      <div style={{ maxWidth: 420 }}>
        <div style={{ fontSize: 44, marginBottom: 18 }} aria-hidden="true">📡</div>
        <h1 style={{
          fontSize: 26, fontWeight: 600, letterSpacing: '-0.03em',
          margin: '0 0 12px', lineHeight: 1.2,
        }}>
          Bağlantı yok
        </h1>
        <p style={{ fontSize: 14.5, lineHeight: 1.65, color: '#B3ACDE', margin: '0 0 24px' }}>
          Fırsatlar internet üzerinden geliyor, o yüzden çevrimdışıyken listeyi
          gösteremiyoruz. Bağlantın gelince bu sayfayı yenilemen yeterli.
        </p>
        {/* Kasıtlı olarak <a>: "tekrar dene" tam sayfa yeniden yükleme demek.
            next/link yumuşak gezinme yapar ve ağ yokken zaten başarısız olur. */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a
          href="/"
          style={{
            display: 'inline-block',
            padding: '13px 26px', borderRadius: 999,
            background: 'linear-gradient(115deg, #7C5CFF 0%, #9B6BFF 42%, #2BE0C8 100%)',
            color: '#150F35', fontWeight: 700, fontSize: 14.5, textDecoration: 'none',
          }}
        >
          Tekrar dene
        </a>
      </div>
    </main>
  )
}
