// What makes the page work without a network. Every same-origin GET is asked of the network
// first, so an online load always shows the latest deploy, and whatever comes back is kept for
// the next time there is no network. The page and its icons are kept at once, when this is
// installed, so that the first visit is enough.

const CACHE = 'striptest';
const KEPT = ['./', 'index.html', 'manifest.webmanifest', 'icon.svg', 'icon-192.png',
  'icon-512.png', 'apple-touch-icon.png'];

addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(KEPT)));
});

addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET' || new URL(request.url).origin !== location.origin) return;
  event.respondWith(fetch(request).then(fresh => {
    // The copy has to be taken here and now: returning the response hands its body away for good,
    // and keeping it has to hold this worker alive, or a reload can outrun the writing
    const copy = fresh.clone();
    if (fresh.ok) event.waitUntil(caches.open(CACHE).then(cache => cache.put(request, copy)));
    return fresh;
  // A page asked for with a query, as a reload past the cache is, is the page all the same
  }).catch(() => caches.match(request, { ignoreSearch: true })));
});
