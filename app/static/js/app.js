// Camp Points — Stage 7 client script.
// Handles: service worker registration, the "Install app" prompt, and the
// "Enable notifications" push subscription flow. Everything here is a
// progressive enhancement — the server-rendered app works fine without it.

(function () {
  "use strict";

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  // --- Service worker registration --------------------------------------
  let swRegistration = null;

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return null;
    try {
      swRegistration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      return swRegistration;
    } catch (err) {
      console.warn("Service worker registration failed:", err);
      return null;
    }
  }

  // --- Install prompt ------------------------------------------------
  let deferredInstallPrompt = null;

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    const btn = document.getElementById("install-app-btn");
    if (btn) btn.hidden = false;
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    const btn = document.getElementById("install-app-btn");
    if (btn) btn.hidden = true;
  });

  function wireInstallButton() {
    const btn = document.getElementById("install-app-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      if (!deferredInstallPrompt) return;
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
      btn.hidden = true;
    });
  }

  // --- Push notifications ------------------------------------------------
  function pushSupported() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  function setNotifBtnState(state) {
    // state: 'unsupported' | 'denied' | 'off' | 'on' | 'busy'
    const btn = document.getElementById("notif-toggle-btn");
    if (!btn) return;
    const labels = {
      unsupported: "Notifications not supported",
      unconfigured: "Push not set up yet",
      denied: "Notifications blocked",
      off: "Enable notifications",
      on: "Notifications on",
      busy: "Working…",
    };
    btn.textContent = labels[state] || labels.off;
    btn.disabled =
      state === "unsupported" ||
      state === "unconfigured" ||
      state === "denied" ||
      state === "busy";
    btn.classList.toggle("is-on", state === "on");
  }

  async function refreshNotifState() {
    if (!pushSupported()) {
      setNotifBtnState("unsupported");
      return;
    }
    if (!window.VAPID_PUBLIC_KEY) {
      setNotifBtnState("unconfigured");
      return;
    }
    if (Notification.permission === "denied") {
      setNotifBtnState("denied");
      return;
    }
    const reg = swRegistration || (await navigator.serviceWorker.ready.catch(() => null));
    if (!reg) {
      setNotifBtnState("off");
      return;
    }
    const existing = await reg.pushManager.getSubscription();
    setNotifBtnState(existing ? "on" : "off");
  }

  async function subscribeToPush() {
    const vapidKey = window.VAPID_PUBLIC_KEY;
    if (!vapidKey) {
      alert("Push notifications aren't configured on the server yet (missing VAPID key).");
      return;
    }
    setNotifBtnState("busy");

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setNotifBtnState(permission === "denied" ? "denied" : "off");
      return;
    }

    const reg = swRegistration || (await navigator.serviceWorker.ready);
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey),
    });

    const res = await fetch("/push/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(subscription.toJSON()),
    });

    if (!res.ok) {
      console.warn("Failed to save push subscription on the server.");
    }
    await refreshNotifState();
  }

  async function unsubscribeFromPush() {
    setNotifBtnState("busy");
    const reg = swRegistration || (await navigator.serviceWorker.ready.catch(() => null));
    const existing = reg ? await reg.pushManager.getSubscription() : null;

    if (existing) {
      const endpoint = existing.endpoint;
      await existing.unsubscribe();
      await fetch("/push/unsubscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({ endpoint }),
      });
    }
    await refreshNotifState();
  }

  function wireNotifButton() {
    const btn = document.getElementById("notif-toggle-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const reg = swRegistration || (await navigator.serviceWorker.ready.catch(() => null));
      const existing = reg ? await reg.pushManager.getSubscription() : null;
      if (existing) {
        await unsubscribeFromPush();
      } else {
        await subscribeToPush();
      }
    });
  }

  // --- Boot ---------------------------------------------------------
  // Note: the avatar bottom-sheet (open/close) and the account carousel
  // itself are wired in carousel.js, which is loaded on every page now
  // that there's no separate sidebar shell.
  document.addEventListener("DOMContentLoaded", async () => {
    await registerServiceWorker();
    wireInstallButton();
    wireNotifButton();
    refreshNotifState();
  });
})();
