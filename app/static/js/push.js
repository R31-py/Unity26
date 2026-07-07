// Eagles of Hope — regjistrimi i push notifications
// Kërkon leje nga përdoruesi, merr çelësin publik VAPID nga backend,
// dhe ruan abonimin te /api/push/subscribe.

(function () {
  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i++) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  async function subscribeToPush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      return; // Shfletuesi s'e mbështet push (p.sh. disa versione iOS jo-standalone)
    }

    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return;

      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();

      if (!subscription) {
        const res = await fetch("/api/push/vapid-public-key");
        const { publicKey } = await res.json();
        if (!publicKey) return; // Push i çaktivizuar te serveri (s'ka çelësa VAPID)

        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
      }

      await fetch("/api/push/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(subscription.toJSON()),
      });
    } catch (err) {
      console.warn("Push subscription failed:", err);
    }
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.ready.then(subscribeToPush);
  }
})();
