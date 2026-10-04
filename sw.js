/* The Wheely Unlucky Gambler: lets the app install to a home screen. Always fetches fresh from the network; falls back to the last copy of the page when offline. */
const CACHE = "wug-v1";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", e => {
  const req = e.request;
  if(req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith(fetch(req).then(res => {
    if(req.mode === "navigate"){ const copy = res.clone(); caches.open(CACHE).then(c => c.put("/", copy)); }
    return res;
  }).catch(() => caches.match(req.mode === "navigate" ? "/" : req)));
});
