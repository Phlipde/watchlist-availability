// Service worker: the app opens offline with what it saved last. Served from /sw.js so it controls every page.
//  - fonts, icons and posters: answered from the cache at once, refreshed in the background
//  - scripts and styles: network first, the saved copy offline
//  - pages and the data they read (/api/latest, favorites, marks, abroad): network first, the saved copy when the network is gone (marked X-From-Cache)
const VERSION = 'v1';
const STATIC = `static-${VERSION}`;
const PAGES = `pages-${VERSION}`;
const IMAGES = `images-${VERSION}`;
const MAX_IMAGES = 300;

self.addEventListener('install', event => { event.waitUntil(self.skipWaiting()); });
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (![STATIC, PAGES, IMAGES].includes(name)) await caches.delete(name);
    await self.clients.claim();
  })());
});

async function staleWhileRevalidate(request, cacheName, limit = 0) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const fresh = fetch(request).then(async response => {
    if (response.ok || response.type === 'opaque') {
      await cache.put(request, response.clone());
      if (limit) { const keys = await cache.keys(); for (const key of keys.slice(0, Math.max(0, keys.length - limit))) await cache.delete(key); }
    }
    return response;
  }).catch(() => cached);
  return cached || fresh;
}

async function networkFirst(request, cacheName = PAGES) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (!cached) return new Response('You are offline and this page was not saved yet.', {status: 503, headers: {'Content-Type': 'text/plain'}});
    const headers = new Headers(cached.headers);
    headers.set('X-From-Cache', '1');
    return new Response(await cached.blob(), {status: cached.status, headers});
  }
}

// A profile switch: the saved pages and data belong to the old profile.
self.addEventListener('message', event => {
  if (event.data?.type !== 'clear-pages') return;
  event.waitUntil(caches.delete(PAGES).then(() => event.ports[0]?.postMessage('done')));
});

self.addEventListener('fetch', event => {
  const {request} = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin === location.origin) {
    // Scripts and styles load as one set (modules import each other): newest from the network, the saved set offline.
    if (/\.(js|css)$/.test(url.pathname) && url.pathname.startsWith('/static/')) { event.respondWith(networkFirst(request, STATIC)); return; }
    if (url.pathname.startsWith('/static/')) { event.respondWith(staleWhileRevalidate(request, STATIC)); return; }
    // The data the pages read: online it is always fresh and saved, offline the last saved copy shows (favorites and marks too).
    if (['/api/latest', '/api/favorites', '/api/flags', '/api/abroad', '/api/greyouts'].includes(url.pathname) || request.mode === 'navigate') { event.respondWith(networkFirst(request)); return; }
    return;
  }
  if (url.hostname === 'image.tmdb.org') event.respondWith(staleWhileRevalidate(request, IMAGES, MAX_IMAGES));
});
