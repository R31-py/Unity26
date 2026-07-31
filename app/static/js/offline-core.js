// UNITY26 — shared offline outbox (Stage 10).
//
// This file is loaded in two different JS contexts with the *same* code:
//   - the service worker (via importScripts), so a request that fails
//     while offline can be queued and, on supporting browsers, replayed
//     later via Background Sync even if no tab is open;
//   - every page (via a normal <script> tag), so browsers without
//     Background Sync (Safari, Firefox) still replay the queue as soon
//     as a tab is open and the connection comes back.
//
// Both contexts expose `self`, `indexedDB`, `fetch` and `BroadcastChannel`,
// so this stays plain and DOM-free to work unmodified in both.
(function (root) {
  "use strict";

  const DB_NAME = "camp-outbox";
  const DB_VERSION = 1;
  const STORE = "requests";

  let dbPromise = null;
  function openDB() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  function add(record) {
    return openDB().then(
      (db) =>
        new Promise((resolve, reject) => {
          const tx = db.transaction(STORE, "readwrite");
          const req = tx.objectStore(STORE).add(record);
          req.onsuccess = () => resolve(req.result);
          req.onerror = () => reject(req.error);
        })
    );
  }

  function getAll() {
    return openDB().then(
      (db) =>
        new Promise((resolve, reject) => {
          const tx = db.transaction(STORE, "readonly");
          const req = tx.objectStore(STORE).getAll();
          req.onsuccess = () => resolve(req.result.sort((a, b) => a.id - b.id));
          req.onerror = () => reject(req.error);
        })
    );
  }

  function remove(id) {
    return openDB().then(
      (db) =>
        new Promise((resolve, reject) => {
          const tx = db.transaction(STORE, "readwrite");
          tx.objectStore(STORE).delete(id);
          tx.oncomplete = () => resolve();
          tx.onerror = () => reject(tx.error);
        })
    );
  }

  function update(id, patch) {
    return openDB().then(
      (db) =>
        new Promise((resolve, reject) => {
          const tx = db.transaction(STORE, "readwrite");
          const store = tx.objectStore(STORE);
          const getReq = store.get(id);
          getReq.onsuccess = () => {
            const existing = getReq.result;
            if (!existing) return resolve();
            store.put(Object.assign(existing, patch));
          };
          tx.oncomplete = () => resolve();
          tx.onerror = () => reject(tx.error);
        })
    );
  }

  function count() {
    return getAll().then((items) => items.length);
  }

  // --- Cross-context notifications ---------------------------------------
  // Lets the page show toasts for things that happen inside the service
  // worker (a request got queued, a background sync just replayed items).
  let channel = null;
  try {
    channel = new BroadcastChannel("camp-outbox-events");
  } catch (err) {
    channel = null; // Safari <15.4 or a very old browser — fine, just no cross-tab toast.
  }
  function emit(type, payload) {
    if (channel) channel.postMessage(Object.assign({ type: type }, payload || {}));
  }
  function onEvent(cb) {
    if (channel) channel.addEventListener("message", (e) => cb(e.data));
  }

  // --- Replay ---------------------------------------------------------
  // Re-issues every queued request in order. Stops (without erroring) the
  // moment one fails for a plain network reason, since that almost always
  // means we're still offline — no point burning through the rest of the
  // queue. Requests the server actively rejects (400/403 — most likely an
  // expired CSRF token after a very long time offline) are marked "failed"
  // instead of retried forever, so the person can be told to redo them.
  let draining = false;
  async function drain() {
    if (draining) return { synced: 0, failed: 0, remaining: 0 };
    draining = true;
    let synced = 0;
    let failed = 0;
    try {
      const items = await getAll();
      for (const item of items) {
        if (item.status === "failed") continue;
        try {
          const init = {
            method: item.method,
            credentials: "same-origin",
            headers: Object.assign({}, item.headers),
          };
          if (item.bodyKind === "form") {
            const fd = new FormData();
            item.body.forEach(([k, v]) => fd.append(k, v));
            init.body = fd;
            delete init.headers["content-type"];
            delete init.headers["Content-Type"];
          } else if (item.bodyKind === "text") {
            init.body = item.body;
          }

          const res = await fetch(item.url, init);
          if (res.ok || (res.status >= 300 && res.status < 400)) {
            await remove(item.id);
            synced += 1;
          } else if (res.status === 400 || res.status === 403) {
            await update(item.id, { status: "failed", attempts: (item.attempts || 0) + 1 });
            failed += 1;
          } else {
            await update(item.id, { attempts: (item.attempts || 0) + 1 });
          }
        } catch (err) {
          // Network failure mid-drain — still offline, stop for now.
          break;
        }
      }
    } finally {
      draining = false;
    }
    const remaining = await count();
    if (synced || failed) emit("outbox-drained", { synced, failed, remaining });
    return { synced, failed, remaining };
  }

  root.CampOutbox = { add, getAll, remove, update, count, drain, emit, onEvent };
})(self);
