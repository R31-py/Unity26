/**
 * Avatar bottom sheet — shared by base.html (Groups/Rooms/Points/admin
 * CRUD pages, still pending their own card-UI redesign) and referenced
 * defensively here in case a cached page still has the old markup.
 *
 * The vertical drag-carousel this file used to implement doesn't exist
 * on any page anymore as of the Messages redesign — every page now
 * either uses the static card grid (dashboard_light_base.html) or the
 * plain list/table layout (base.html), so that code was removed rather
 * than kept around unused.
 */
(function () {
  var avatarBtn = document.getElementById("cx-avatar-btn");
  var backdrop = document.getElementById("cx-backdrop");
  var sheetClose = document.getElementById("cx-sheet-close");
  if (avatarBtn && backdrop) {
    function openSheet() {
      backdrop.classList.add("open");
      avatarBtn.setAttribute("aria-expanded", "true");
    }
    function closeSheet() {
      backdrop.classList.remove("open");
      avatarBtn.setAttribute("aria-expanded", "false");
    }
    avatarBtn.addEventListener("click", openSheet);
    if (sheetClose) sheetClose.addEventListener("click", closeSheet);
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) closeSheet();
    });
  }
})();
