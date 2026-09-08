'use client'
import Image from 'next/image'
import { useRef } from 'react'
import { Opportunity } from '@/types'
import { CATEGORY_ICON_SRC } from '@/lib/category-assets'

const FUNDING_LABELS: Record<string, string> = {
  full: 'Tam Burs',
  partial: 'Kısmi Burs',
  free: 'Ücretsiz',
  stipend: 'Harçlık',
}

// Fon türü rozetleri — koyu zeminde okunur kalsın diye dolgu düşük opaklıkta,
// metin ve kenarlık aynı renk ailesinden.
const FUNDING_STYLE: Record<string, { tint: string; fg: string; icon: string }> = {
  full:    { tint: '43, 224, 200', fg: '#7BF0DC', icon: '💎' },
  partial: { tint: '255, 181, 71', fg: '#FFD08A', icon: '◐' },
  free:    { tint: '92, 158, 255', fg: '#A8C8FF', icon: '🎁' },
  stipend: { tint: '124, 92, 255', fg: '#C4B2FF', icon: '💸' },
}

/** Son başvuruya kalan süreyi halka olarak gösterir — sayı + görsel aciliyet. */
function DeadlineRing({ days }: { days: number }) {
  const span = 90                                  // 90 günlük pencere
  const pct = Math.max(0.04, Math.min(1, days / span))
  const urgent = days <= 14
  const soon = days <= 30
  const color = urgent ? '#FF6B6B' : soon ? '#FFB547' : '#2BE0C8'

  return (
    <div
      title={`Son başvuruya ${days} gün`}
      style={{
        position: 'relative', width: 58, height: 58, flexShrink: 0,
        borderRadius: '50%',
        background: `conic-gradient(${color} ${pct * 360}deg, rgba(255,255,255,0.10) 0deg)`,
        display: 'grid', placeItems: 'center',
        boxShadow: `0 0 22px -6px ${color}`,
      }}
    >
      <div style={{
        width: 47, height: 47, borderRadius: '50%',
        background: 'rgba(13, 10, 38, 0.92)',
        display: 'grid', placeItems: 'center', lineHeight: 1,
      }}>
        <span style={{ fontSize: 16, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>
          {days}
        </span>
        <span style={{ fontSize: 8, color: 'var(--text-low)', fontWeight: 700, letterSpacing: '0.06em' }}>
          GÜN
        </span>
      </div>
    </div>
  )
}

export default function OpportunityCard({ opp }: { opp: Opportunity }) {
  const cardRef = useRef<HTMLElement>(null)
  const days = opp.days_until_deadline
  const urgent = days !== null && days <= 30
  const funding = FUNDING_STYLE[opp.funding_type] ?? FUNDING_STYLE.free
  const iconSrc = CATEGORY_ICON_SRC[opp.category_slug]

  const deadlineText = opp.deadline
    ? new Date(opp.deadline).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
    : 'Sürekli açık'

  // İmleci takip eden ışık — CSS ::after gradyanının merkezini besler.
  function handleMove(e: React.MouseEvent<HTMLElement>) {
    const el = cardRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    el.style.setProperty('--mx', `${e.clientX - rect.left}px`)
    el.style.setProperty('--my', `${e.clientY - rect.top}px`)
  }

  return (
    <article
      ref={cardRef}
      onMouseMove={handleMove}
      className="opp-card glass-panel"
      style={{
        padding: '22px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 15,
        borderRadius: 22,
      }}
    >
      {/* kategori rengiyle üst şerit */}
      <span aria-hidden="true" style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 3,
        background: `linear-gradient(90deg, ${opp.category_color}, ${urgent ? '#FF6B6B' : '#2BE0C8'})`,
        opacity: 0.9,
      }} />

      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', position: 'relative' }}>
        <span aria-hidden="true" className="opp-icon" style={{
          flexShrink: 0,
          width: 52, height: 52, borderRadius: 16,
          display: 'grid', placeItems: 'center',
          background: `${opp.category_color}1F`,
          border: `1px solid ${opp.category_color}44`,
        }}>
          {iconSrc
            ? <Image src={iconSrc} alt="" width={34} height={34} style={{ objectFit: 'contain' }} />
            : <span style={{ fontSize: 22, lineHeight: 1 }}>✨</span>}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{
            fontSize: 16.5, fontWeight: 600, color: 'var(--text-hi)', lineHeight: 1.35,
            margin: '2px 0 9px', letterSpacing: '-0.015em',
          }}>
            {opp.title}
          </h3>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 10.5, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
              background: `${opp.category_color}26`,
              border: `1px solid ${opp.category_color}55`,
              color: '#fff',
            }}>
              {opp.category_label_tr}
            </span>
            <span style={{
              fontSize: 10.5, fontWeight: 600, padding: '4px 10px', borderRadius: 999,
              background: `rgba(${funding.tint}, 0.16)`,
              border: `1px solid rgba(${funding.tint}, 0.42)`,
              color: funding.fg,
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
                  background: 'rgba(255, 181, 71, 0.14)',
                  border: '1px solid rgba(255, 181, 71, 0.4)',
                  color: '#FFD08A',
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
        <p style={{ fontSize: 12.5, color: 'var(--text-mid)', lineHeight: 1.6, margin: 0 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-hi)' }}>Kimler başvurabilir: </span>
          {opp.eligibility_notes}
        </p>
      )}

      {opp.documents.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text-low)', fontWeight: 600, marginRight: 2 }}>
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
        gap: 12, flexWrap: 'wrap', marginTop: 'auto',
        borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 14,
      }}>
        <span style={{
          fontSize: 12, fontWeight: 600,
          color: urgent ? '#FF9B9B' : 'var(--text-mid)',
          display: 'inline-flex', alignItems: 'center', gap: 7,
        }}>
          <span className={urgent ? 'fx-pulse-dot' : undefined} style={{
            width: 7, height: 7, borderRadius: '50%',
            background: urgent ? '#FF6B6B' : '#2BE0C8', display: 'inline-block',
            boxShadow: `0 0 10px ${urgent ? '#FF6B6B' : '#2BE0C8'}`,
          }} />
          {deadlineText}
        </span>

        <a
          href={opp.official_url}
          target="_blank"
          rel="noopener noreferrer"
          className="apply-link apply-btn"
          style={{
            fontSize: 13, fontWeight: 600, color: '#150F35', textDecoration: 'none',
            padding: '11px 21px', borderRadius: 999,
            background: 'var(--grad-brand)',
            boxShadow: '0 14px 28px -14px rgba(124, 92, 255, 0.95)',
            display: 'inline-flex', alignItems: 'center', gap: 7, whiteSpace: 'nowrap',
          }}
        >
          Başvuru sayfası <span className="apply-arrow">↗</span>
        </a>
      </div>
    </article>
  )
}
