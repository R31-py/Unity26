// Live-update polling (Stage 9).
//
// Any element on the page can opt in with:
//   <div data-live-key="messages" data-live-version="{{ server_computed_signal }}">
//     ...content that should refresh without a manual reload...
//   </div>
//
// A container can also depend on more than one signal at once (e.g. a
// dashboard's card row shows Messages, Points, and Requests together) by
// listing them comma-separated:
//   <div data-live-key="messages,points,requests"
//        data-live-version="{{ messages_version }}|{{ points_version }}|{{ requests_version }}">
// The two attributes must list/join signals in the same order — the
// combined string is just there so the client can tell "did any of these
// change" with one comparison, not because the joined value itself means
// anything.
//
// Every POLL_INTERVAL_MS this polls /live/version (one lightweight request
// covering every domain the current user can see). For each data-live-key
// present on the page, if the combined signal for that key no longer
// matches what we last saw, we re-fetch the *current page* itself, pull
// out the matching [data-live-key="X"] node from the response, and swap
// it in place of the one in the live DOM — same content, no full reload,
// no flicker, scroll position untouched.
//
// This deliberately reuses the exact markup the page already renders
// server-side (no separate "fragment" templates to keep in sync) — the
// polling response IS the same HTML a manual refresh would give you.

(function () {
  "use strict";

  const POLL_INTERVAL_MS = 10000;

  function liveContainers() {
    return Array.from(document.querySelectorAll("[data-live-key]"));
  }

  // Seed known combined versions from what the server already rendered,
  // so the very first poll doesn't think everything just changed.
  const knownVersions = {};
  liveContainers().forEach((el) => {
    const key = el.getAttribute("data-live-key");
    knownVersions[key] = el.getAttribute("data-live-version") || "";
  });

  if (Object.keys(knownVersions).length === 0) {
    // Nothing on this page opted in — don't even start polling.
    return;
  }

  let refreshing = false;

  async function refreshContainersFor(keys) {
    if (refreshing) return;
    refreshing = true;
    try {
      const res = await fetch(window.location.href, {
        headers: { "X-Live-Poll": "1" },
      });
      if (!res.ok) return;
      const html = await res.text();
      const parsed = new DOMParser().parseFromString(html, "text/html");

      keys.forEach((key) => {
        const selector = `[data-live-key="${key}"]`;
        const fresh = parsed.querySelector(selector);
        const current = document.querySelector(selector);
        if (!fresh || !current) return;

        // If the user is mid-drag on a carousel inside this container,
        // swapping the DOM out from under them would orphan the pointer
        // capture the drag holds (the element it was set on is gone), so
        // the browser never fires pointerup/pointercancel and the page is
        // left stuck as if still dragging. Leave it alone this cycle —
        // the next poll will pick up the change once the drag ends.
        const draggingWrap = current.querySelector(".cx-carousel-wrap.grabbing");
        if (draggingWrap) return;

        // Remember which card (if any) is currently focused in each
        // carousel here, by position, so the swap-in below can restore it
        // instead of always snapping back to the first card.
        const focusIndexByWrap = Array.from(current.querySelectorAll(".cx-carousel-wrap")).map((wrap) => {
          const items = Array.from(wrap.querySelectorAll(".cx-item"));
          const idx = items.findIndex((el) => el.classList.contains("cx-focused"));
          return idx;
        });

        current.replaceWith(fresh);
        knownVersions[key] = fresh.getAttribute("data-live-version") || "";

        // Swapped-in markup is brand new DOM — any carousel inside it
        // needs its listeners re-wired (see carousel.js).
        if (typeof window.reinitCarousel === "function") {
          fresh.querySelectorAll(".cx-carousel-wrap").forEach((wrap, i) => {
            const focusIndex = focusIndexByWrap[i];
            window.reinitCarousel(wrap, focusIndex >= 0 ? { focusIndex } : undefined);
          });
        }
      });
    } catch (err) {
      console.warn("Live refresh failed:", err);
    } finally {
      refreshing = false;
    }
  }

  async function poll() {
    if (document.hidden) return; // don't burn requests on a backgrounded tab
    try {
      const res = await fetch("/live/version");
      if (!res.ok) return;
      const versions = await res.json();

      const changedKeys = Object.keys(knownVersions).filter((key) => {
        const parts = key.split(",");
        const combined = parts.map((p) => versions[p]).join("|");
        return combined !== knownVersions[key];
      });

      if (changedKeys.length > 0) {
        await refreshContainersFor(changedKeys);
      }
    } catch (err) {
      console.warn("Live poll failed:", err);
    }
  }

  setInterval(poll, POLL_INTERVAL_MS);

  // Catch up immediately when the tab becomes visible again, instead of
  // waiting out whatever's left of the current interval.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) poll();
  });
})();
