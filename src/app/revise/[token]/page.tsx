'use client'

import { use, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

const CATEGORIES = [
  ['scholarship', 'Burs'], ['volunteering', 'Gönüllülük'],
  ['youth_project', 'Gençlik Projesi'], ['internship', 'Staj'],
  ['summer_school', 'Yaz Okulu'], ['exchange', 'Değişim'],
] as const

const FUNDING = [
  ['full', 'Tam Burs'], ['partial', 'Kısmi Burs'],
  ['free', 'Ücretsiz'], ['stipend', 'Harçlık'],
] as const

interface RevisionData {
  title: string
  url: string
  category_slug: string
  host_countries: string[]
  deadline_text: string | null
  funding_type: string | null
  eligibility_notes: string | null
  language_requirement: string | null
  description: string | null
  revision_note: string | null
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 10px', borderRadius: 8,
  border: '1px solid #ddd', fontSize: 13, background: '#fff', color: '#1a1a1a',
}

export default function RevisionPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params)
  const [form, setForm] = useState<RevisionData | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    let active = true
    async function load() {
      const result = await supabase.rpc('get_revision_submission', { p_token: token })
      if (!active) return
      if (result.error) setError(result.error.message)
      else setForm(result.data as RevisionData)
    }
    void load()
    return () => { active = false }
  }, [token])

  function set<K extends keyof RevisionData>(key: K, value: RevisionData[K]) {
    setForm(current => current ? { ...current, [key]: value } : current)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!form) return
    setSaving(true)
    setError('')
    const result = await supabase.rpc('submit_revision', {
      p_token: token,
      p_title: form.title.trim(),
      p_url: form.url.trim(),
      p_category_slug: form.category_slug,
      p_host_countries: form.host_countries,
      p_deadline_text: form.deadline_text ?? '',
      p_funding_type: form.funding_type,
      p_eligibility_notes: form.eligibility_notes ?? '',
      p_language_requirement: form.language_requirement ?? '',
      p_description: form.description ?? '',
    })
    setSaving(false)
    if (result.error) setError(result.error.message)
    else setDone(true)
  }

  return (
    <main style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 600, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 500 }}>
          <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği · Revize
        </h1>
        {done ? (
          <div style={{ background: '#E1F5EE', color: '#085041', padding: 20, borderRadius: 12 }}>
            Revizen alındı. Kayıt yeniden admin onayına gönderildi.
          </div>
        ) : error && !form ? (
          <div style={{ background: '#FDE8E8', color: '#A32D2D', padding: 20, borderRadius: 12 }}>{error}</div>
        ) : !form ? (
          <p style={{ color: '#777' }}>Yükleniyor…</p>
        ) : (
          <form onSubmit={submit} style={{ background: '#fff', padding: 20, borderRadius: 14, border: '1px solid #e5e5e5' }}>
            <div style={{ background: '#FAEEDA', color: '#633806', padding: 12, borderRadius: 8, marginBottom: 16, fontSize: 13 }}>
              <strong>İstenen düzeltme:</strong> {form.revision_note}
            </div>
            <Label text="Başlık *" /><input required value={form.title} onChange={e => set('title', e.target.value)} style={inputStyle} />
            <Label text="Resmi bağlantı *" /><input required type="url" value={form.url} onChange={e => set('url', e.target.value)} style={inputStyle} />
            <Label text="Kategori *" />
            <select required value={form.category_slug} onChange={e => set('category_slug', e.target.value)} style={inputStyle}>
              {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <Label text="Ülkeler (virgülle)" />
            <input value={form.host_countries.join(', ')} onChange={e => set('host_countries', e.target.value.split(',').map(v => v.trim().toUpperCase()).filter(Boolean))} style={inputStyle} />
            <Label text="Son başvuru" /><input value={form.deadline_text ?? ''} onChange={e => set('deadline_text', e.target.value)} style={inputStyle} />
            <Label text="Finansman" />
            <select value={form.funding_type ?? ''} onChange={e => set('funding_type', e.target.value || null)} style={inputStyle}>
              <option value="">Belirtilmedi</option>
              {FUNDING.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <Label text="Kimler başvurabilir" /><textarea value={form.eligibility_notes ?? ''} onChange={e => set('eligibility_notes', e.target.value)} rows={2} style={inputStyle} />
            <Label text="Dil şartı" /><input value={form.language_requirement ?? ''} onChange={e => set('language_requirement', e.target.value)} style={inputStyle} />
            <Label text="Ek not" /><textarea value={form.description ?? ''} onChange={e => set('description', e.target.value)} rows={3} style={inputStyle} />
            {error && <p style={{ color: '#A32D2D', fontSize: 12 }}>{error}</p>}
            <button disabled={saving} style={{ width: '100%', marginTop: 18, padding: 11, border: 0, borderRadius: 9, background: '#534AB7', color: '#fff', fontWeight: 600, cursor: 'pointer' }}>
              {saving ? 'Gönderiliyor…' : 'Revizeyi Gönder'}
            </button>
          </form>
        )}
      </div>
    </main>
  )
}

function Label({ text }: { text: string }) {
  return <div style={{ fontSize: 11, color: '#777', marginTop: 12, marginBottom: 4 }}>{text}</div>
}
