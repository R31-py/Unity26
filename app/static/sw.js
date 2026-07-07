// Eagles of Hope — Service Worker
// Cache-first për asete statike, network-first për faqe HTML, me kthim te
// /offline kur s'ka internet dhe faqja s'është e ruajtur në cache.

const CACHE_VERSION = "eoh-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGES_CACHE = `${CACHE_VERSION}-pages`;

const PRECACHE_URLS = [
  "/offline",
  "/static/css/style.css",
  "/static/js/push.js",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("eoh-") && key !== STATIC_CACHE && key !== PAGES_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/static/");
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // mos e prek POST/PUT (CSRF, forma, etj.)

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (isStaticAsset(url)) {
    // Cache-first për CSS/JS/ikona
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((res) => {
        const clone = res.clone();
        caches.open(STATIC_CACHE).then((cache) => cache.put(req, clone));
        return res;
      }))
    );
    return;
  }

  // Network-first për faqet HTML, me fallback te cache dhe pastaj /offline
  event.respondWith(
    fetch(req)
      .then((res) => {
        const clone = res.clone();
        caches.open(PAGES_CACHE).then((cache) => cache.put(req, clone));
        return res;
      })
      .catch(() =>
        caches.match(req).then((cached) => cached || caches.match("/offline"))
      )
  );
});

// --- Push notifications ---
self.addEventListener("push", (event) => {
  let data = { title: "Eagles of Hope", body: "Ke një njoftim të ri.", url: "/" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (e) {
    /* payload jo-JSON, përdor default */
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
      data: { url: data.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsArr) => {
      const existing = clientsArr.find((c) => c.url.includes(targetUrl));
      if (existing) return existing.focus();
      return self.clients.openWindow(targetUrl);
    })
  );
});
