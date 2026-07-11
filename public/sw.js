// Camp Points service worker (Stage 7).
//
// Two jobs:
//   1. Cache a small offline app-shell so the installed app doesn't show
//      the browser's default offline page if a request drops.
//   2. Receive Web Push events from the backend (pywebpush, VAPID) and
//      show a system notification — this is what makes "New message"
//      pushes and event reminders (Stage 8) show up even when the app
//      isn't in an open tab.
//
// Bump this on any change below so clients pick up the new worker.
const CACHE_NAME = "camp-points-shell-v1";

const APP_SHELL = [
  "/",
  "/static/css/style.css",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

// Network-first for navigations/API calls (this app is mostly live data),
// falling back to the cached shell only when the network is unreachable.
// Static assets (css/icons/manifest) are cache-first since they rarely change.
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  const isStaticAsset = url.pathname.startsWith("/static/");

  if (isStaticAsset) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
    return;
  }

  event.respondWith(
    fetch(request).catch(() =>
      caches.match(request).then((cached) => cached || caches.match("/"))
    )
  );
});

// --- Web Push ---------------------------------------------------------
// Payload shape sent from app/push.py: { title, body, url }
self.addEventListener("push", (event) => {
  let data = { title: "Camp Points", body: "You have a new update." };
  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (err) {
      data.body = event.data.text() || data.body;
    }
  }

  const options = {
    body: data.body,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    data: { url: data.url || "/" },
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            client.navigate(targetUrl);
            return client.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }
      })
  );
});
