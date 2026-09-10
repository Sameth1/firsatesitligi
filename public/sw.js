/* eslint-disable no-restricted-globals */
/**
 * fırsateşitliği — service worker.
 *
 * TASARIM KARARLARI (özensiz bir SW siteyi kalıcı bozabilir, bu yüzden dar):
 *
 *  • Supabase ASLA önbelleğe alınmaz. Farklı origin olduğu için "yalnız kendi
 *    origin'imiz" kuralı bunu zaten dışarıda bırakıyor. Son başvuru tarihleri
 *    bayatlarsa kullanıcı kaçırdığı bir fırsatı fark edemez — veri hep ağdan.
 *
 *  • Sayfa gezinmeleri ağ-önce. Böylece yeni bir yayın çıktığında kullanıcı
 *    eski HTML'e çakılmaz; ağ yoksa önbellek, o da yoksa /offline.
 *
 *  • Statik varlıklar önbellek-önce. /_next/static içerik-hash'li, bayraklar ve
 *    ikonlar değişmez; ağa çıkmaya gerek yok.
 *
 *  • Sürüm değişince eski cache'ler siliniyor, skipWaiting + clients.claim ile
 *    yeni SW hemen devralıyor. Bozuk bir sürüm yayınlanırsa bir sonraki yayın
 *    kullanıcıyı kilitli bırakmadan kurtarabilsin diye.
 */

const VERSION = 'v1';
const SHELL_CACHE = `fe-shell-${VERSION}`;
const ASSET_CACHE = `fe-assets-${VERSION}`;
const OFFLINE_URL = '/offline';

// Önbellek-önce davranacak yollar. Hepsi ya içerik-hash'li ya da değişmez.
const STATIC_PREFIXES = ['/_next/static/', '/icons/', '/flags/', '/app-icons/', '/hero/'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll([OFFLINE_URL, '/app-icons/icon-192.png']))
      // Çevrimdışı sayfası bir sebeple çekilemezse kurulum yine de sürsün:
      // SW'siz kalmaktansa önbelleksiz bir SW yeğdir.
      .catch(() => undefined)
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((k) => k.startsWith('fe-') && k !== SHELL_CACHE && k !== ASSET_CACHE)
          .map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

function isStaticAsset(url) {
  return STATIC_PREFIXES.some((p) => url.pathname.startsWith(p));
}

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Yalnız GET. POST/PATCH (Supabase yazmaları, form gönderimleri) dokunulmaz.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Yalnız kendi origin'imiz. Supabase, Google Fonts, Plausible → ağa bırakılır.
  if (url.origin !== self.location.origin) return;

  // Admin ekranları oturuma bağlı; önbelleklenirse yanlış kullanıcıya yanlış
  // sayfa gösterme riski var. Tamamen dışarıda.
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/api')) return;

  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((res) => {
        // Yalnız sağlam yanıtlar saklanır; opaque/hatalı yanıt önbelleğe girmez.
        if (res && res.ok && res.type === 'basic') {
          const copy = res.clone();
          caches.open(ASSET_CACHE).then((c) => c.put(request, copy)).catch(() => undefined);
        }
        return res;
      })),
    );
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(SHELL_CACHE).then((c) => c.put(request, copy)).catch(() => undefined);
          }
          return res;
        })
        .catch(() => caches.match(request)
          .then((hit) => hit || caches.match(OFFLINE_URL))
          .then((hit) => hit || Response.error())),
    );
  }
});
