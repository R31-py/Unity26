// Schedule page: tapping an event preview card opens a full-detail
// overlay cloned from that card's <template>; tapping the overlay
// (anywhere — it's a "tap to close" surface, same as the mockup) closes
// it again. Pure progressive enhancement: without JS the cards are still
// readable, they just won't expand.
(function () {
  "use strict";

  const overlay = document.getElementById("sch-overlay");
  const overlayCard = document.getElementById("sch-overlay-card");
  if (!overlay || !overlayCard) return;

  function openFor(templateId) {
    const tpl = document.getElementById(templateId);
    if (!tpl) return;
    overlayCard.innerHTML = "";
    overlayCard.appendChild(tpl.content.cloneNode(true));
    overlay.classList.add("open");
  }

  function close() {
    overlay.classList.remove("open");
  }

  document.querySelectorAll("[data-open-overlay]").forEach((card) => {
    card.addEventListener("click", () => openFor(card.getAttribute("data-open-overlay")));
  });

  overlay.addEventListener("click", close);
})();
