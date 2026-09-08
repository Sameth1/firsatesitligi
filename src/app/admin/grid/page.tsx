'use client'
import dynamic from 'next/dynamic'
import Link from 'next/link'

// Syncfusion Grid tarayıcı API'lerine dayanır → SSR kapalı, yalnız client.
const SubmissionsGrid = dynamic(() => import('./submissions-grid'), {
  ssr: false,
  loading: () => (
    <div style={{ padding: 40, color: '#aaa', fontSize: 13 }}>Tablo yükleniyor…</div>
  ),
})

export default function AdminGridPage() {
  return (
    <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
            <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Admin · Tablo (beta)</span>
          </div>
          <Link
            href="/admin"
            style={{
              fontSize: 12, color: '#534AB7', textDecoration: 'none',
              padding: '6px 12px', border: '0.5px solid #e0e0e0',
              borderRadius: 8, background: '#fff',
            }}
          >
            ← Kart görünümü
          </Link>
        </div>
        <SubmissionsGrid />
      </div>
    </main>
  )
}
