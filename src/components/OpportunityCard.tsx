'use client'
import { Opportunity } from '@/types'

const FUNDING_LABELS: Record<string, string> = {
  full: 'Tam Burs',
  partial: 'Kısmi Burs',
  free: 'Ücretsiz',
  stipend: 'Harçlık',
}

const FUNDING_COLORS: Record<string, string> = {
  full: '#E1F5EE',
  partial: '#FAEEDA',
  free: '#E6F1FB',
  stipend: '#EEEDFE',
}

const FUNDING_TEXT: Record<string, string> = {
  full: '#085041',
  partial: '#633806',
  free: '#0C447C',
  stipend: '#3C3489',
}

function DeadlineBadge({ days, deadline }: { days: number | null; deadline: string | null }) {
  if (!deadline) return (
    <span style={{ fontSize: 11, color: '#888', fontStyle: 'italic' }}>Sürekli açık</span>
  )

  const date = new Date(deadline).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
  const urgent = days !== null && days <= 30

  return (
    <span style={{
      fontSize: 11,
      fontWeight: 500,
      color: urgent ? '#A32D2D' : '#444',
      display: 'flex',
      alignItems: 'center',
      gap: 4,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: urgent ? '#E24B4A' : '#639922',
        display: 'inline-block', flexShrink: 0,
      }} />
      {date}
      {urgent && days !== null && (
        <span style={{ color: '#E24B4A', marginLeft: 2 }}>({days} gün kaldı)</span>
      )}
    </span>
  )
}

export default function OpportunityCard({ opp }: { opp: Opportunity }) {
  const urgent = opp.days_until_deadline !== null && opp.days_until_deadline <= 30

  return (
    <div style={{
      background: '#fff',
      border: `0.5px solid ${urgent ? '#F09595' : '#e0e0e0'}`,
      borderLeft: `3px solid ${urgent ? '#E24B4A' : opp.category_color}`,
      borderRadius: 12,
      padding: '16px 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>

      {/* Üst satır: başlık + rozet */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 500, color: '#1a1a1a', lineHeight: 1.4 }}>
          {opp.title}
        </span>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <span style={{
            fontSize: 10, fontWeight: 500, padding: '3px 8px', borderRadius: 20,
            background: opp.category_color + '22',
            color: opp.category_color,
            border: `0.5px solid ${opp.category_color}44`,
            whiteSpace: 'nowrap',
          }}>
            {opp.category_label_tr}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 500, padding: '3px 8px', borderRadius: 20,
            background: FUNDING_COLORS[opp.funding_type] || '#f5f5f5',
            color: FUNDING_TEXT[opp.funding_type] || '#444',
            whiteSpace: 'nowrap',
          }}>
            {FUNDING_LABELS[opp.funding_type] || opp.funding_type}
          </span>
        </div>
      </div>

      {/* Meta: deadline + ülkeler */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <DeadlineBadge days={opp.days_until_deadline} deadline={opp.deadline} />
        {opp.host_countries.length > 0 && !opp.host_countries.includes('*') && (
          <span style={{ fontSize: 11, color: '#555' }}>
            {opp.host_countries.slice(0, 4).join(', ')}
            {opp.host_countries.length > 4 && ` +${opp.host_countries.length - 4}`}
          </span>
        )}
        {opp.host_countries.includes('*') && (
          <span style={{ fontSize: 11, color: '#555' }}>Tüm ülkeler</span>
        )}
      </div>

      {/* Belgeler */}
      {opp.documents.length > 0 && (
        <div style={{ borderTop: '0.5px solid #f0f0f0', paddingTop: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 500, color: '#555', marginBottom: 6 }}>
            İstenen belgeler
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {opp.documents.map((doc, i) => (
              <span key={i} style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 20,
                background: doc.is_required ? '#f0f0f0' : '#fafafa',
                color: '#555',
                border: '0.5px solid #e0e0e0',
              }}>
                {doc.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Şartlar */}
      {opp.eligibility_notes && (
        <div style={{ fontSize: 11, color: '#666', lineHeight: 1.5 }}>
          <span style={{ fontWeight: 500, color: '#333' }}>Kimler başvurabilir: </span>
          {opp.eligibility_notes}
        </div>
      )}

      {/* Link */}
      <a
        href={opp.official_url}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          fontSize: 12, color: '#534AB7', fontWeight: 500,
          textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
          marginTop: 2,
        }}
      >
        Resmi başvuru sayfasına git ↗
      </a>
    </div>
  )
}
