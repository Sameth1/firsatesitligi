'use client'
import { Opportunity } from '@/types'

const FUNDING_LABELS: Record<string, string> = {
  full: 'Tam Burs',
  partial: 'Kısmi Burs',
  free: 'Ücretsiz',
  stipend: 'Harçlık',
}

// Fon türü rozetleri — dolgu + metin aynı aileden, kart üstünde okunur kalsın
const FUNDING_STYLE: Record<string, { bg: string; fg: string; icon: string }> = {
  full:    { bg: 'linear-gradient(120deg, #DFF6EE, #C9F0E2)', fg: '#085041', icon: '💎' },
  partial: { bg: 'linear-gradient(120deg, #FBEEDA, #F7E3C4)', fg: '#633806', icon: '◐' },
  free:    { bg: 'linear-gradient(120deg, #E4F0FC, #D3E7FA)', fg: '#0C447C', icon: '🎁' },
  stipend: { bg: 'linear-gradient(120deg, #ECEAFE, #DEDBFC)', fg: '#3C3489', icon: '💸' },
}

const CATEGORY_ICONS: Record<string, string> = {
  scholarship: '🎓',
  volunteering: '🤝',
  youth_project: '🚀',
  internship: '💼',
  summer_school: '☀️',
  exchange: '🔁',
}

/** Son başvuruya kalan süreyi halka olarak gösterir — sayı + görsel aciliyet. */
function DeadlineRing({ days }: { days: number }) {
  const span = 90                                  // 90 günlük pencere
  const pct = Math.max(0.04, Math.min(1, days / span))
  const urgent = days <= 14
  const soon = days <= 30
  const color = urgent ? '#E24B4A' : soon ? '#D98324' : '#0F8E76'

  return (
    <div style={{
      position: 'relative', width: 54, height: 54, flexShrink: 0,
      borderRadius: '50%',
      background: `conic-gradient(${color} ${pct * 360}deg, rgba(0,0,0,0.06) 0deg)`,
      display: 'grid', placeItems: 'center',
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: '50%', background: '#fff',
        display: 'grid', placeItems: 'center', lineHeight: 1,
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color }}>{days}</span>
        <span style={{ fontSize: 8.5, color: '#8B85A8', fontWeight: 600 }}>GÜN</span>
      </div>
    </div>
  )
}

export default function OpportunityCard({ opp }: { opp: Opportunity }) {
  const days = opp.days_until_deadline
  const urgent = days !== null && days <= 30
  const funding = FUNDING_STYLE[opp.funding_type] ?? FUNDING_STYLE.free
  const icon = CATEGORY_ICONS[opp.category_slug] ?? '✨'

  const deadlineText = opp.deadline
    ? new Date(opp.deadline).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
    : 'Sürekli açık'

  return (
    <article
      className="opp-card"
      style={{
        position: 'relative',
        background: 'rgba(255,255,255,0.86)',
        backdropFilter: 'blur(14px)',
        border: '1px solid rgba(255,255,255,0.9)',
        borderRadius: 20,
        padding: '20px 22px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        boxShadow: '0 20px 40px -30px rgba(35, 28, 82, 0.5), 0 1px 3px rgba(35, 28, 82, 0.06)',
        overflow: 'hidden',
      }}
    >
      {/* kategori rengiyle üst şerit */}
      <span aria-hidden="true" style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 4,
        background: `linear-gradient(90deg, ${opp.category_color}, ${urgent ? '#E24B4A' : '#17A79A'})`,
      }} />

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <span aria-hidden="true" className="opp-icon" style={{
          fontSize: 22, lineHeight: 1, flexShrink: 0,
          width: 44, height: 44, borderRadius: 14,
          display: 'grid', placeItems: 'center',
          background: `${opp.category_color}18`,
          border: `1px solid ${opp.category_color}33`,
        }}>
          {icon}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{
            fontSize: 16, fontWeight: 600, color: '#231C52', lineHeight: 1.35,
            margin: '2px 0 8px', letterSpacing: '-0.015em',
          }}>
            {opp.title}
          </h3>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 10.5, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
              background: `${opp.category_color}1A`, color: opp.category_color,
            }}>
              {opp.category_label_tr}
            </span>
            <span style={{
              fontSize: 10.5, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
              background: funding.bg, color: funding.fg,
            }}>
              {funding.icon} {FUNDING_LABELS[opp.funding_type] || opp.funding_type}
            </span>
            {opp.host_countries.includes('*') ? (
              <span className="opp-meta-chip">🌍 Tüm ülkeler</span>
            ) : opp.host_countries.length > 0 && (
              <span className="opp-meta-chip">
                📍 {opp.host_countries.slice(0, 3).join(', ')}
                {opp.host_countries.length > 3 && ` +${opp.host_countries.length - 3}`}
              </span>
            )}
            {opp.last_url_check_status != null &&
              (opp.last_url_check_status < 200 || opp.last_url_check_status >= 400) && (
              <span
                title={opp.last_url_check_at
                  ? `Son kontrol: ${new Date(opp.last_url_check_at).toLocaleString('tr-TR')}`
                  : undefined}
                style={{
                  fontSize: 10.5, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
                  background: '#FBEEDA', color: '#633806',
                }}
              >
                ⚠ Link sorunlu olabilir
              </span>
            )}
          </div>
        </div>

        {days !== null && <DeadlineRing days={days} />}
      </div>

      {opp.eligibility_notes && (
        <p style={{ fontSize: 12.5, color: '#5F5980', lineHeight: 1.55, margin: 0 }}>
          <span style={{ fontWeight: 600, color: '#3A3556' }}>Kimler başvurabilir: </span>
          {opp.eligibility_notes}
        </p>
      )}

      {opp.documents.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: '#8B85A8', fontWeight: 600, marginRight: 2 }}>
            Belgeler:
          </span>
          {opp.documents.map((doc, i) => (
            <span key={i} className="opp-meta-chip" style={{ fontWeight: 500 }}>
              {doc.name}
            </span>
          ))}
        </div>
      )}

      {/* Alt satır: tarih solda, birincil aksiyon sağ altta */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 12, flexWrap: 'wrap',
        borderTop: '1px solid rgba(83, 74, 183, 0.1)', paddingTop: 13,
      }}>
        <span style={{
          fontSize: 12, fontWeight: 600,
          color: urgent ? '#C0392F' : '#5F5980',
          display: 'inline-flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            background: urgent ? '#E24B4A' : '#0F8E76', display: 'inline-block',
          }} />
          {deadlineText}
        </span>

        <a
          href={opp.official_url}
          target="_blank"
          rel="noopener noreferrer"
          className="apply-link apply-btn"
          style={{
            fontSize: 13, fontWeight: 600, color: '#fff', textDecoration: 'none',
            padding: '10px 20px', borderRadius: 999,
            background: 'linear-gradient(115deg, #4B41B5 0%, #6C4FD0 55%, #17A79A 100%)',
            boxShadow: '0 12px 24px -14px rgba(76, 65, 181, 0.9)',
            display: 'inline-flex', alignItems: 'center', gap: 7, whiteSpace: 'nowrap',
          }}
        >
          Başvuru sayfası <span className="apply-arrow">↗</span>
        </a>
      </div>
    </article>
  )
}
