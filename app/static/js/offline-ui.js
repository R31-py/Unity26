// UNITY26 — offline outbox UI (Stage 10).
// Pairs with offline-core.js (must load first) and sw.js.
(function () {
  "use strict";

  if (!window.CampOutbox) return; // offline-core.js failed to load — fail quiet

  let toastBox = null;
  function toast(message, kind) {
    if (!toastBox) {
      toastBox = document.createElement("div");
      toastBox.id = "camp-offline-toasts";
      toastBox.style.cssText =
        "position:fixed;left:0;right:0;bottom:0;z-index:200;display:flex;flex-direction:column;align-items:center;gap:8px;padding:0 16px 16px;pointer-events:none;";
      document.body.appendChild(toastBox);
    }
    const el = document.createElement("div");
    const bg = kind === "error" ? "#e53a3a" : kind === "success" ? "#2eae66" : "#1b1b1f";
    el.textContent = message;
    el.style.cssText =
      "max-width:420px;width:100%;background:" +
      bg +
      ";color:#fff;font-family:system-ui,sans-serif;font-size:13px;font-weight:600;" +
      "padding:12px 16px;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.25);" +
      "opacity:0;transform:translateY(8px);transition:opacity .25s ease,transform .25s ease;";
    toastBox.appendChild(el);
    requestAnimationFrame(() => {
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    });
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(8px)";
      setTimeout(() => el.remove(), 300);
    }, 4200);
  }

  function requestDrain() {
    // Ask both the page-side and worker-side drain to run — CampOutbox.drain()
    // is safe to call redundantly (re-entrant guarded), and poking the SW
    // covers cases where Background Sync didn't fire promptly.
    window.CampOutbox.drain();
    navigator.serviceWorker &&
      navigator.serviceWorker.ready
        .then((reg) => reg.active && reg.active.postMessage({ type: "drain-outbox" }))
        .catch(() => {});
  }

  window.CampOutbox.onEvent((msg) => {
    if (msg.type === "queued") {
      toast("Saved offline — will send once you're back online.");
    } else if (msg.type === "outbox-drained") {
      if (msg.synced) {
        toast(msg.synced === 1 ? "Synced 1 pending change." : `Synced ${msg.synced} pending changes.`, "success");
        document.dispatchEvent(new CustomEvent("camp:outbox-synced"));
      }
      if (msg.failed) {
        toast(
          msg.failed === 1
            ? "1 saved change couldn't be sent — please redo it."
            : `${msg.failed} saved changes couldn't be sent — please redo them.`,
          "error"
        );
      }
    }
  });

  window.addEventListener("online", requestDrain);
  document.addEventListener("DOMContentLoaded", () => {
    // Covers the case where changes were queued last session and the app
    // is reopened already online (no 'online' event fires in that case).
    if (navigator.onLine) requestDrain();
  });
  // Safety net for connections that flap without ever firing a clean
  // 'online' event (some flaky wifi / captive portals).
  setInterval(() => {
    if (navigator.onLine) requestDrain();
  }, 45000);
})();
