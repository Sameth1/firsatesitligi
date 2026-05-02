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
        marginBottom: 20,
      }}>
        <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
          <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {rightSlot}
          <button
            onClick={() => setShowModal(true)}
            style={{
              fontSize: 12, fontWeight: 500, padding: '6px 14px', borderRadius: 20,
              background: 'transparent', color: '#534AB7',
              border: '1px solid #534AB7',
              cursor: 'pointer', whiteSpace: 'nowrap',
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={e => {
              (e.target as HTMLButtonElement).style.background = '#534AB7';
              (e.target as HTMLButtonElement).style.color = '#fff'
            }}
            onMouseLeave={e => {
              (e.target as HTMLButtonElement).style.background = 'transparent';
              (e.target as HTMLButtonElement).style.color = '#534AB7'
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
