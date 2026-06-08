'use client'
import { useEffect, useRef, useState } from 'react'
import { registerLicense } from '@syncfusion/ej2-base'
import {
  GridComponent, ColumnsDirective, ColumnDirective, Inject,
  Sort, Filter, Page, Toolbar, ColumnChooser, ExcelExport, Resize,
  type ToolbarItems,
} from '@syncfusion/ej2-react-grids'
import { supabase } from '@/lib/supabase'
import '@syncfusion/ej2-react-grids/styles/tailwind.css'

// Lisans anahtarı varsa kaydet — yoksa POC trial-watermark ile çalışır (işlev
// etkilenmez). Anahtar: kurulu sürüm için Syncfusion panelinden üretilir.
if (process.env.NEXT_PUBLIC_SYNCFUSION_LICENSE) {
  registerLicense(process.env.NEXT_PUBLIC_SYNCFUSION_LICENSE)
}

// /admin/page.tsx'teki Submission ile aynı şekil; Grid'in gösterdiği alt küme.
interface SubmissionRow {
  id: string
  title: string
  url: string
  category_slug: string | null
  host_countries: string[] | null
  deadline_text: string | null
  funding_type: string | null
  status: string
  submitter_nickname: string | null
  submitter_email: string | null
  created_at: string
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Bekliyor', approved: 'Onaylandı',
  needs_revision: 'Revize', rejected: 'Reddedildi',
}

const toolbarOptions: ToolbarItems[] = ['Search', 'ColumnChooser', 'ExcelExport']

export default function SubmissionsGrid() {
  const gridRef = useRef<GridComponent>(null)
  const [rows, setRows] = useState<SubmissionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      const { data, error } = await supabase
        .from('submissions')
        .select('id,title,url,category_slug,host_countries,deadline_text,' +
                'funding_type,status,submitter_nickname,submitter_email,created_at')
        .order('created_at', { ascending: false })
      if (!active) return
      if (error) setError(error.message)
      else setRows((data ?? []) as unknown as SubmissionRow[])
      setLoading(false)
    }
    load()
    return () => { active = false }
  }, [])

  // ExcelExport toolbar düğmesi → grid.excelExport()
  function toolbarClick(args: { item: { id?: string } }) {
    if (args.item.id?.endsWith('_excelexport')) gridRef.current?.excelExport()
  }

  const countryTemplate = (p: SubmissionRow) =>
    <span>{(p.host_countries ?? []).join(', ') || '—'}</span>
  const statusTemplate = (p: SubmissionRow) =>
    <span>{STATUS_LABELS[p.status] ?? p.status}</span>
  const titleTemplate = (p: SubmissionRow) =>
    <a href={`/admin/submissions/${p.id}`} style={{ color: '#534AB7', textDecoration: 'none' }}>{p.title}</a>
  const dateTemplate = (p: SubmissionRow) =>
    <span>{p.created_at ? new Date(p.created_at).toLocaleDateString('tr-TR') : ''}</span>

  if (loading) return <div style={{ padding: 40, color: '#aaa', fontSize: 13 }}>Yükleniyor…</div>
  if (error) return <div style={{ padding: 40, color: '#A32D2D', fontSize: 13 }}>Hata: {error}</div>

  return (
    <GridComponent
      ref={gridRef}
      dataSource={rows}
      allowSorting
      allowFiltering
      allowPaging
      allowResizing
      allowExcelExport
      filterSettings={{ type: 'Menu' }}
      pageSettings={{ pageSize: 20 }}
      toolbar={toolbarOptions}
      toolbarClick={toolbarClick}
      showColumnChooser
    >
      <ColumnsDirective>
        <ColumnDirective field="title" headerText="Başlık" width="240" template={titleTemplate} />
        <ColumnDirective field="status" headerText="Durum" width="120" template={statusTemplate} />
        <ColumnDirective field="category_slug" headerText="Kategori" width="130" />
        <ColumnDirective field="host_countries" headerText="Ülke" width="110" template={countryTemplate} allowFiltering={false} />
        <ColumnDirective field="deadline_text" headerText="Son başvuru" width="150" />
        <ColumnDirective field="funding_type" headerText="Fon" width="110" />
        <ColumnDirective field="submitter_nickname" headerText="Öneren" width="130" />
        <ColumnDirective field="submitter_email" headerText="E-posta" width="190" />
        <ColumnDirective field="created_at" headerText="Tarih" width="120" template={dateTemplate} />
      </ColumnsDirective>
      <Inject services={[Sort, Filter, Page, Toolbar, ColumnChooser, ExcelExport, Resize]} />
    </GridComponent>
  )
}
