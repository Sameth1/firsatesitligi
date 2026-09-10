'use client'

import Image from 'next/image'
import { useState, type CSSProperties } from 'react'
import { countryNameTr, flagSrc, normalizeCountryCode } from '@/lib/countries'

/**
 * Ülke bayrağı — yerel SVG'den.
 *
 * Emoji bayrak (🇩🇪) kullanmıyoruz: Windows'ta bayrak emojileri render olmuyor,
 * kullanıcı sadece "DE" görüyor. Bunun yerine `public/flags/<kod>.svg` altındaki
 * kendi dosyalarımızı basıyoruz — dış CDN'e runtime bağımlılığı yok.
 *
 * Süslemedir: varsayılan `alt=""`. Ülke adı zaten yanında metin olarak yazılıyor.
 * Adın olmadığı bir yerde kullanacaksan `title` ver; hem tooltip hem erişilebilir
 * ad olarak bağlanır.
 */

export type FlagProps = {
  /** ISO 3166-1 alpha-2. Büyük/küçük harf farketmez, 'DE' de 'de' de olur. */
  code: string | null | undefined
  /** Görünen genişlik (px). Form kartlarında ~22-26, sonuç çiplerinde ~14-16. */
  size?: number
  /**
   * Verilirse tooltip + erişilebilir ad olur (bayrak artık dekoratif sayılmaz).
   * `true` verirsen ülkenin Türkçe adı otomatik kullanılır.
   */
  title?: string | true
  className?: string
  style?: CSSProperties
}

/** Bayrakların tamamı 4:3 (lipis/flag-icons `4x3` seti) — oranı ezmiyoruz. */
const ASPECT = 3 / 4

export default function Flag({ code, size = 22, title, className, style }: FlagProps) {
  const [failed, setFailed] = useState(false)

  const normalized = normalizeCountryCode(code)
  const src = flagSrc(normalized)
  const width = Math.round(size)
  const height = Math.round(size * ASPECT)

  const label = title === true ? countryNameTr(normalized) : title
  const a11y = label ? { title: label, 'aria-label': label, role: 'img' as const } : {}

  // Koyu zeminde kaybolmasın diye içeriden ince bir kenarlık; köşeler hafif yuvarlak.
  const frame: CSSProperties = {
    display: 'inline-block',
    flexShrink: 0,
    verticalAlign: 'middle',
    borderRadius: 3,
    boxShadow: 'inset 0 0 0 1px rgba(255, 255, 255, 0.18)',
    overflow: 'hidden',
    ...style,
  }

  // Yedek: kod bilinmiyor, bozuk ya da dosya yüklenemedi. DB'den beklenmedik bir
  // kod gelebildiği için burada çökmek yok — kodu okunur bir rozet olarak basıyoruz.
  if (!src || failed) {
    const badge = normalized || '??'
    return (
      <span
        {...a11y}
        className={className}
        style={{
          ...frame,
          height,
          minWidth: width,
          padding: '0 3px',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--glass-strong, rgba(255,255,255,0.075))',
          color: 'var(--text-mid, #B3ACDE)',
          fontSize: Math.max(7, Math.round(size * 0.42)),
          fontWeight: 700,
          letterSpacing: '0.04em',
          lineHeight: 1,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {badge}
      </span>
    )
  }

  return (
    <span {...a11y} className={className} style={{ ...frame, width, height, lineHeight: 0 }}>
      <Image
        src={src}
        alt=""
        width={width}
        height={height}
        onError={() => setFailed(true)}
        style={{ display: 'block', width: '100%', height: '100%', objectFit: 'cover' }}
      />
    </span>
  )
}
