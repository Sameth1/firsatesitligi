import type { Metadata, Viewport } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import RootAuthHashRedirect from "@/components/RootAuthHashRedirect";
import ServiceWorkerRegistrar from "@/components/pwa/ServiceWorkerRegistrar";
import InstallHint from "@/components/pwa/InstallHint";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "fırsateşitliği — Türkiye'den Yurt Dışı Burs, Staj ve Gönüllülük Fırsatları",
  description:
    "Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu. Burs, gönüllülük, staj, yaz okulu ve değişim programlarını yaşına, bölümüne ve hedef ülkene göre filtrele.",
  keywords: [
    "yurt dışı burs",
    "Türkiye burs",
    "ücretsiz burs",
    "yurt dışı staj",
    "gönüllülük programı",
    "yaz okulu",
    "değişim programı",
    "Erasmus",
    "gençlik projesi",
    "scholarship Turkey",
  ],
  authors: [{ name: "fırsateşitliği" }],
  openGraph: {
    title: "fırsateşitliği — Yurt Dışı Burs ve Fırsatlar",
    description:
      "Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu. Profiline göre burs, staj ve gönüllülük fırsatlarını keşfet.",
    url: "https://firsatesitligi.com",
    siteName: "fırsateşitliği",
    locale: "tr_TR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "fırsateşitliği — Yurt Dışı Burs ve Fırsatlar",
    description:
      "Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
  alternates: {
    canonical: "https://firsatesitligi.com",
  },
  verification: {
    google: "CCtWFTzsam76Ve-zq4EGmiZLMCCbCmqAxKaEvs8ISn0",
  },
  // PWA: manifest'i Next /manifest.webmanifest olarak kendisi yayınlar ve
  // <head>'e link'ini ekler (src/app/manifest.ts). Buradakiler iOS tarafı —
  // Safari manifest'teki ikonları kullanmaz, apple-touch-icon'a bakar.
  appleWebApp: {
    capable: true,
    title: "fırsateşitliği",
    statusBarStyle: "black-translucent",
  },
  icons: {
    apple: [{ url: "/app-icons/apple-touch-icon.png", sizes: "180x180" }],
  },
};

// themeColor bu Next sürümünde metadata'da değil, viewport export'unda.
// Android'de adres çubuğunu, standalone modda durum çubuğunu boyar.
export const viewport: Viewport = {
  themeColor: "#0D0A26",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="tr"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <RootAuthHashRedirect />
        <ServiceWorkerRegistrar />
        <Script
          id="schema-org"
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              "name": "fırsateşitliği",
              "url": "https://firsatesitligi.vercel.app",
              "description": "Türkiye'deki gençler için ücretsiz yurt dışı fırsat arama platformu. Burs, gönüllülük, staj, yaz okulu ve değişim programlarını yaşına, bölümüne ve hedef ülkene göre filtrele.",
              "applicationCategory": "EducationalApplication",
              "operatingSystem": "Web",
              "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "TRY"
              },
              "audience": {
                "@type": "Audience",
                "audienceType": "Turkish students seeking international opportunities"
              },
              "inLanguage": "tr",
              "keywords": "yurt dışı burs, Türkiye burs, staj, gönüllülük, yaz okulu, değişim programı, scholarship Turkey",
              "isAccessibleForFree": true,
              "creator": {
                "@type": "Organization",
                "name": "fırsateşitliği",
                "url": "https://github.com/Sameth1/firsatesitligi"
              }
            })
          }}
        />
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN ? (
          <Script
            defer
            data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN}
            src="https://plausible.io/js/script.js"
          />
        ) : null}
        {children}
        <InstallHint />
      </body>
    </html>
  );
}
