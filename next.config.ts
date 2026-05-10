import type { NextConfig } from "next";

/**
 * Magic link `emailRedirectTo` için kamuya açık kök URL.
 * - `NEXT_PUBLIC_SITE_URL` (Vercel env veya .env) varsa o kullanılır (özel domain vb.).
 * - Yoksa Vercel build’de `VERCEL_URL` → `https://…vercel.app` otomatik (Dashboard’da bu değişkeni eklemen gerekmez).
 */
function publicSiteUrlForBuild(): string {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/+$/, "") ?? ""
  if (explicit) return explicit
  const vercel = process.env.VERCEL_URL?.trim() ?? ""
  if (vercel) return `https://${vercel}`
  return ""
}

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_SITE_URL: publicSiteUrlForBuild(),
  },
};

export default nextConfig;
