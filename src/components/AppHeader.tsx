'use client'

import { useState } from 'react'
import SuggestOpportunityModal from './SuggestOpportunityModal'

interface AppHeaderProps {
  searchSnapshot?: Record<string, unknown>
  rightSlot?: React.ReactNode
}

export default function AppHeader({ searchSnapshot, rightSlot }: AppHeaderProps) {
  const [showModal, setShowModal] = useState(false)

  return (
    <>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        gap: 12, marginBottom: 22, flexWrap: 'wrap',
      }}>
        <div style={{
          fontSize: 22, fontWeight: 600, letterSpacing: '-0.025em',
          color: 'var(--text-hi)',
        }}>
          <span style={{
            background: 'var(--grad-brand)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}>fırsat</span>eşitliği
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {rightSlot}
          <button
            onClick={() => setShowModal(true)}
            className="pill-btn"
            style={{
              fontSize: 12, fontWeight: 600, padding: '8px 16px', borderRadius: 999,
              background: 'rgba(255,255,255,0.05)',
              color: 'var(--text-mid)',
              border: '1px solid rgba(255,255,255,0.14)',
              cursor: 'pointer', whiteSpace: 'nowrap',
              backdropFilter: 'blur(10px)',
            }}
            onMouseEnter={e => {
              const b = e.currentTarget
              b.style.background = 'rgba(124, 92, 255, 0.20)'
              b.style.borderColor = 'rgba(124, 92, 255, 0.6)'
              b.style.color = '#fff'
            }}
            onMouseLeave={e => {
              const b = e.currentTarget
              b.style.background = 'rgba(255,255,255,0.05)'
              b.style.borderColor = 'rgba(255,255,255,0.14)'
              b.style.color = 'var(--text-mid)'
            }}
          >
            + Fırsat Öner
          </button>
        </div>
      </div>

      {showModal && (
        <SuggestOpportunityModal
          searchSnapshot={searchSnapshot}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  )
}
