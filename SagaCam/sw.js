// Saga door display: the smallest service worker that lets Chrome install
// the page as an app (full screen, no address bar). It only passes the
// app's own files through to the network: no caching, and the webhook and
// websocket traffic to /api is never touched.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method === "GET" && u.origin === location.origin && u.pathname.startsWith("/local/saga-cam/"))
    e.respondWith(fetch(e.request));
});
