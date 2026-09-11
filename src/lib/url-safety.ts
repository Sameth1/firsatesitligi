/**
 * SSRF önlemi: yalnızca herkese açık http(s) adresleri.
 *
 * NEDEN SIKI: buraya giren URL yalnız kaydedilmiyor — `validate_submissions.py`
 * ajanı onu SERVİS ANAHTARIYLA çalışırken indiriyor. Yani zayıf bir süzgeç,
 * saldırganın ajana istediği iç adresi getirtmesi demek; getirilen metin de
 * kayda (ve onaylanırsa herkese açık fırsat satırına) düşebiliyor.
 *
 * Ölçülen eski açıklar (hepsi bu sürümde kapalı):
 *   • 169.254.169.254  → bulut metadata servisi (AWS/GCP/Azure kimlik bilgileri)
 *   • [::1] ve fc00::/7 → IPv6 loopback / özel ağ
 *   • metadata.google.internal ve *.internal → iç DNS adları
 */

/** IPv4 sekizlisini sayıya çevirir; IPv4 değilse null. */
function ipv4Parts(host: string): number[] | null {
  const m = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/)
  if (!m) return null
  const parts = m.slice(1).map(Number)
  return parts.every(n => n >= 0 && n <= 255) ? parts : null
}

/** RFC1918 + loopback + link-local + CGNAT + 0.0.0.0/8 */
function isPrivateIpv4(parts: number[]): boolean {
  const [a, b] = parts
  return (
    a === 0 ||                                   // 0.0.0.0/8
    a === 10 ||                                  // 10/8
    a === 127 ||                                 // loopback
    (a === 100 && b >= 64 && b <= 127) ||        // CGNAT 100.64/10
    (a === 169 && b === 254) ||                  // link-local + bulut metadata
    (a === 172 && b >= 16 && b <= 31) ||         // 172.16/12
    (a === 192 && b === 168) ||                  // 192.168/16
    a >= 224                                     // multicast + ayrılmış
  )
}

/**
 * IPv6 literal'ini 8 hextet'e açar. Geçersizse null.
 * Gerek var çünkü WHATWG URL `[::ffff:127.0.0.1]`'i `[::ffff:7f00:1]` hex
 * biçimine normalize ediyor; metin eşlemesi bu yüzden yetmiyor.
 */
function expandIpv6(ip: string): number[] | null {
  const [head, tail] = ip.split('::')
  const parse = (chunk: string) =>
    chunk ? chunk.split(':').filter(Boolean).map(h => parseInt(h, 16)) : []
  let left: number[]
  let right: number[]
  try {
    left = parse(head)
    right = tail === undefined ? [] : parse(tail)
  } catch {
    return null
  }
  if (tail === undefined) {
    if (left.length !== 8) return null
    return left.some(Number.isNaN) ? null : left
  }
  const fill = 8 - left.length - right.length
  if (fill < 0) return null
  const full = [...left, ...Array(fill).fill(0), ...right]
  return full.some(n => Number.isNaN(n) || n < 0 || n > 0xffff) ? null : full
}

/** `[::1]`, `[fc00::1]`, `[::ffff:7f00:1]` gibi IPv6 literal'leri. */
function isPrivateIpv6(host: string): boolean {
  if (!host.startsWith('[') || !host.endsWith(']')) return false
  const raw = host.slice(1, -1).toLowerCase().split('%')[0]

  // IPv4-mapped'in noktalı yazımı (normalize edilmemiş hâli)
  const dotted = raw.match(/^::ffff:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/)
  if (dotted) {
    const parts = ipv4Parts(dotted[1])
    return parts ? isPrivateIpv4(parts) : true
  }

  const h = expandIpv6(raw)
  if (!h) return true                          // çözemediysek güvenli tarafta kal

  // :: (unspecified) ve ::1 (loopback)
  if (h.slice(0, 7).every(x => x === 0) && (h[7] === 0 || h[7] === 1)) return true
  // fc00::/7 unique-local, fe80::/10 link-local
  if ((h[0] & 0xfe00) === 0xfc00) return true
  if ((h[0] & 0xffc0) === 0xfe80) return true
  // IPv4-mapped ::ffff:a.b.c.d → IPv4 kurallarıyla denetle
  if (h.slice(0, 5).every(x => x === 0) && h[5] === 0xffff) {
    const parts = [h[6] >> 8, h[6] & 0xff, h[7] >> 8, h[7] & 0xff]
    return isPrivateIpv4(parts)
  }
  return false
}

/** Ağ adı olarak iç/altyapı adresleri. */
const BLOCKED_HOSTNAMES = new Set([
  'localhost',
  'metadata.google.internal',
  'metadata',
  'instance-data',
])

export function assertPublicHttpUrl(raw: string): URL {
  let u: URL
  try {
    u = new URL(raw.trim())
  } catch {
    throw new Error('Geçersiz URL')
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    throw new Error('Yalnızca http/https')
  }

  const h = u.hostname.toLowerCase()

  if (BLOCKED_HOSTNAMES.has(h) || h.endsWith('.local') || h.endsWith('.internal')
      || h.endsWith('.localhost')) {
    throw new Error('Yerel / özel ağ adresi engellendi')
  }
  if (isPrivateIpv6(h)) {
    throw new Error('Yerel / özel ağ adresi engellendi')
  }
  const parts = ipv4Parts(h)
  if (parts && isPrivateIpv4(parts)) {
    throw new Error('Yerel / özel ağ adresi engellendi')
  }

  return u
}
