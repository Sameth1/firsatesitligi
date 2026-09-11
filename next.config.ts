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

/**
 * Güvenlik başlıkları. Canlıda yalnız HSTS vardı; admin paneli iframe'e
 * alınabiliyordu (clickjacking). CSP bilinçli olarak YOK: Next'in inline
 * script'leri ve three.js/GSAP için nonce altyapısı gerekir — onu eklemeden
 * CSP yazmak siteyi bozar. Aşağıdakiler bozmadan kazanç sağlayanlar.
 */
const securityHeaders = [
  // Siteyi hiçbir iframe'e sokma — admin panelinde clickjacking'i keser.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  // Tarayıcı MIME türünü tahmin etmesin.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Dış sitelere tam URL (arama parametreleri dâhil) sızmasın.
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Kullanılmayan güçlü API'leri kapat.
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_SITE_URL: publicSiteUrlForBuild(),
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
