// Houdt de schil offline beschikbaar. Gegevens worden altijd vers opgehaald.
const SCHIL = 'coach-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(SCHIL).then(c => c.addAll(['/', '/manifest.webmanifest'])));
  self.skipWaiting();
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(k =>
    Promise.all(k.filter(n => n !== SCHIL).map(n => caches.delete(n)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || e.request.url.includes('/api/')) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
