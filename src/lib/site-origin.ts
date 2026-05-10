/**
 * Magic link `emailRedirectTo` için kullanılacak kamuya açık origin.
 *
 * Vercel / prod: `NEXT_PUBLIC_SITE_URL` (Vercel env) veya build’de `next.config.ts` içinden
 * `VERCEL_URL` → `https://…vercel.app` (Dashboard’da ayrıca tanımlaman gerekmez).
 * Özel domainde env ile açıkça ver. `redirect_to` Supabase allow list’te olmalı.
 *
 * Env yoksa `window.location.origin` (localhost dahil) kullanılır.
 */
export function getPublicSiteOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/+$/, '') ?? ''
  if (fromEnv) return fromEnv
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin
  }
  return ''
}
