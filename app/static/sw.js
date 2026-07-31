// Camp Points service worker (Stage 10).
//
// Three jobs:
//   1. Cache every same-origin GET (pages, CSS, icons, manifest) as it's
//      visited — stale-while-revalidate — so the installed app can be
//      opened offline and show whatever was last seen, instead of just a
//      bare app shell.
//   2. Queue any same-origin write (POST/PUT/DELETE — creating, editing,
//      or deleting something) that fails because there's no network, and
//      replay it automatically once the connection is back — via
//      Background Sync where supported, and a page-driven fallback
//      (offline-ui.js) everywhere else.
//   3. Receive Web Push events from the backend (pywebpush, VAPID) and
//      show a system notification.
//
// Bump CACHE_NAME/RUNTIME_CACHE on structural changes so clients pick up
// the new worker and drop stale caches.
importScripts("/static/js/offline-core.js");

const SHELL_CACHE = "camp-points-shell-v3";
const RUNTIME_CACHE = "camp-points-runtime-v1";
const OUTBOX_SYNC_TAG = "camp-outbox-sync";

const APP_SHELL = [
  "/",
  "/static/css/style.css",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

// Paths that should never be cached or queued — pure polling data, always
// wants the freshest answer or a quiet failure, never a stale replay.
const LIVE_PATH_PREFIX = "/live/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  const keep = new Set([SHELL_CACHE, RUNTIME_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

// --- GET: stale-while-revalidate for everything same-origin -----------
async function handleGet(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = await cache.match(request);

  const networkFetch = fetch(request)
    .then((response) => {
      if (response && response.ok && response.type === "basic") {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  if (cached) {
    // Don't block on the network — return the cached copy immediately and
    // let the fetch above refresh the cache in the background.
    networkFetch.catch(() => {});
    return cached;
  }

  const fresh = await networkFetch;
  if (fresh) return fresh;

  const shellFallback = await caches.match("/");
  if (shellFallback) return shellFallback;

  return new Response(
    "<!DOCTYPE html><html><body style=\"font-family:sans-serif;text-align:center;padding:40px;\">" +
      "<h1>You're offline</h1><p>Nothing has been cached for this page yet.</p></body></html>",
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

// --- Non-GET: try the network, queue on real network failure ----------
function offlineNavigationResponse(request) {
  const back = request.headers.get("referer") || "/";
  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Saved for later &middot; Camp Points</title>
<link rel="stylesheet" href="/static/css/style.css"></head>
<body class="gc-body">
<div class="gc-page" style="display:flex;align-items:center;justify-content:center;min-height:100vh;">
  <div class="form-card" style="max-width:360px;text-align:center;">
    <h1 style="font-family:var(--font-display);font-size:20px;margin:0 0 10px;">You're offline</h1>
    <p style="color:var(--gc-muted);font-size:14px;line-height:1.6;margin:0;">
      This has been saved on your device and will be sent automatically as soon as
      you're back online &mdash; no need to redo it.
    </p>
    <a href="${back}" class="gc-btn-primary" style="display:inline-block;margin-top:18px;text-decoration:none;">Back</a>
  </div>
</div>
</body></html>`;
  return new Response(html, { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

function offlineJsonResponse() {
  return new Response(JSON.stringify({ queued: true, offline: true }), {
    status: 202,
    headers: { "Content-Type": "application/json" },
  });
}

async function queueWrite(request) {
  const contentType = (request.headers.get("content-type") || "").toLowerCase();
  let bodyKind = "none";
  let body = null;

  if (contentType.includes("form")) {
    const fd = await request.formData();
    bodyKind = "form";
    body = Array.from(fd.entries());
  } else if (request.method !== "GET" && request.method !== "HEAD") {
    const text = await request.text();
    if (text) {
      bodyKind = "text";
      body = text;
    }
  }

  const headers = {};
  request.headers.forEach((value, key) => {
    if (["content-length", "host", "connection"].includes(key)) return;
    headers[key] = value;
  });

  const id = await self.CampOutbox.add({
    url: request.url,
    method: request.method,
    headers,
    bodyKind,
    body,
    createdAt: Date.now(),
    attempts: 0,
    status: "pending",
  });

  self.CampOutbox.emit("queued", { id, url: request.url });

  try {
    if ("sync" in self.registration) {
      await self.registration.sync.register(OUTBOX_SYNC_TAG);
    }
  } catch (err) {
    // Background Sync unsupported/blocked — offline-ui.js's 'online'
    // listener is the fallback that will drain the queue instead.
  }

  return request.mode === "navigate" ? offlineNavigationResponse(request) : offlineJsonResponse();
}

async function handleWrite(request) {
  const clone = request.clone();
  try {
    return await fetch(request);
  } catch (err) {
    // A thrown fetch (not a Response, not even a 4xx/5xx) means a real
    // network failure — offline, DNS down, etc. — not a rejected request.
    return queueWrite(clone);
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // cross-origin (fonts, etc.) — leave to the browser as-is

  if (url.pathname.startsWith(LIVE_PATH_PREFIX)) {
    event.respondWith(
      fetch(request).catch(() => new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }))
    );
    return;
  }

  if (request.method === "GET") {
    event.respondWith(handleGet(request));
    return;
  }

  event.respondWith(handleWrite(request));
});

self.addEventListener("sync", (event) => {
  if (event.tag === OUTBOX_SYNC_TAG) {
    event.waitUntil(self.CampOutbox.drain());
  }
});

// Lets pages ask the worker to drain right now (used as a fallback poke
// alongside the page's own drain, harmless if both run — drain() is
// re-entrant-safe).
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "drain-outbox") {
    event.waitUntil(self.CampOutbox.drain());
  }
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
