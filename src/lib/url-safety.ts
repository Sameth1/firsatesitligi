/** Basit SSRF önlemi: yalnızca http(s) ve loopback olmayan hostlar. */
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
  if (
    h === 'localhost' ||
    h === '0.0.0.0' ||
    h.endsWith('.local') ||
    h.startsWith('127.') ||
    h.startsWith('10.') ||
    h.startsWith('192.168.') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(h)
  ) {
    throw new Error('Yerel / özel ağ adresi engellendi')
  }
  return u
}
