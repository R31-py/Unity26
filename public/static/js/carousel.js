/**
 * Generic vertical carousel — operates on whatever `.cx-item` elements are
 * already in the DOM (server-rendered by Jinja), rather than re-rendering
 * content from a JS data structure. Each `.cx-item` contains both a
 * collapsed `.cx-chip` and an expanded `.cx-card` (a real `<a>` — normal
 * navigation, no JS needed to "open" it once focused).
 *
 * Behaviour (unchanged from the approved nav-concept.html mockup):
 *  - Tap a collapsed chip -> focuses it (does not navigate)
 *  - Tap the already-focused card -> navigates normally (real link)
 *  - Drag up/down -> live-follows the pointer, snaps to nearest on release
 *  - Mouse wheel / arrow keys -> step focus by one
 */
(function () {
  function initCarousel(wrap) {
    var track = wrap.querySelector(".cx-track");
    var items = Array.prototype.slice.call(wrap.querySelectorAll(".cx-item"));
    if (!items.length) return;
    if (track) track.classList.remove("js-pending");

    var focusIndex = items.findIndex(function (el) {
      return el.dataset.initialFocus === "true";
    });
    if (focusIndex < 0) focusIndex = 0;

    var dots = [];

    function buildDots() {
      dots.forEach(function (d) { d.remove(); });
      dots = items.map(function () {
        var dot = document.createElement("div");
        dot.className = "cx-dot";
        track.appendChild(dot);
        return dot;
      });
    }
    buildDots();

    function layout(liveOffset, dragTargetIndex) {
      liveOffset = liveOffset || 0;
      var focusedH = 190, chipH = 56, gap = 14;

      items.forEach(function (el, i) {
        var dist = i - focusIndex;
        var isFocused = dist === 0;
        var offset, opacity, height;

        if (isFocused) {
          offset = 0; opacity = 1; height = focusedH;
        } else {
          var dir = dist > 0 ? 1 : -1;
          var d = Math.abs(dist);
          offset = dir * (focusedH / 2 + gap + (chipH + gap) * (d - 1) + chipH / 2);
          opacity = d === 1 ? 0.85 : (d === 2 ? 0.4 : 0);
          height = chipH;
        }
        offset += liveOffset;

        el.style.top = "50%";
        el.style.height = height + "px";
        el.style.transform = "translate(0,-50%) translateY(" + offset + "px)";
        el.style.opacity = opacity;
        el.style.zIndex = isFocused ? 3 : (2 - Math.min(Math.abs(dist), 2));
        el.style.pointerEvents = opacity < 0.05 ? "none" : "auto";
        el.classList.toggle("cx-focused", isFocused);
        el.classList.toggle("cx-drag-target", dragTargetIndex === i);

        var chip = el.querySelector(".cx-chip");
        var card = el.querySelector(".cx-card");
        if (chip) chip.style.display = isFocused ? "none" : "flex";
        if (card) card.style.display = isFocused ? "block" : "none";

        var dot = dots[i];
        dot.style.top = "calc(50% + " + offset + "px)";
        dot.style.opacity = opacity < 0.15 ? 0.15 : 1;
        dot.classList.toggle("focused", isFocused);
      });
    }

    function setFocus(i) {
      if (i < 0 || i >= items.length) return;
      focusIndex = i;
      layout();
    }

    var dragging = false, wasDrag = false, dragStartY = 0, dragOffsetPx = 0, activePointerId = null;
    var downIndex = null, pressedEl = null;
    var DRAG_STEP = 84;

    function targetFromOffset(offsetPx) {
      var candidate = focusIndex - Math.round(offsetPx / DRAG_STEP);
      return Math.max(0, Math.min(items.length - 1, candidate));
    }

    wrap.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      var itemEl = e.target.closest(".cx-item");
      downIndex = itemEl ? items.indexOf(itemEl) : null;
      pressedEl = itemEl;
      if (pressedEl) pressedEl.classList.add("cx-pressed");

      dragging = true;
      wasDrag = false;
      dragStartY = e.clientY;
      dragOffsetPx = 0;
      activePointerId = e.pointerId;
      wrap.setPointerCapture(activePointerId);
      wrap.classList.add("grabbing");
    });

    wrap.addEventListener("pointermove", function (e) {
      if (!dragging || e.pointerId !== activePointerId) return;
      var dy = e.clientY - dragStartY;
      if (!wasDrag && Math.abs(dy) > 4) {
        wasDrag = true;
        if (pressedEl) { pressedEl.classList.remove("cx-pressed"); pressedEl = null; }
        track.classList.add("dragging");
        // Once a real drag starts, suppress the click that would otherwise
        // fire on the focused card's <a> when the pointer is released.
        items.forEach(function (el) {
          var card = el.querySelector(".cx-card");
          if (card) card.dataset.suppressClick = "true";
        });
      }
      if (!wasDrag) return;
      if (focusIndex === 0 && dy > 0) dy *= 0.35;
      if (focusIndex === items.length - 1 && dy < 0) dy *= 0.35;
      dragOffsetPx = dy;
      layout(dragOffsetPx, targetFromOffset(dragOffsetPx));
    });

    function endDrag() {
      if (!dragging) return;
      dragging = false;
      wrap.classList.remove("grabbing");
      track.classList.remove("dragging");
      if (pressedEl) { pressedEl.classList.remove("cx-pressed"); pressedEl = null; }

      if (wasDrag) {
        var target = targetFromOffset(dragOffsetPx);
        dragOffsetPx = 0;
        setFocus(target);
      } else if (downIndex !== null) {
        setFocus(downIndex);
      }
      downIndex = null;
      setTimeout(function () {
        wasDrag = false;
        items.forEach(function (el) {
          var card = el.querySelector(".cx-card");
          if (card) delete card.dataset.suppressClick;
        });
      }, 0);
    }
    wrap.addEventListener("pointerup", endDrag);
    wrap.addEventListener("pointercancel", endDrag);
    wrap.addEventListener("pointerleave", function (e) {
      if (dragging && e.pointerId === activePointerId) endDrag();
    });

    // A focused card is a real <a href="...">. If a drag just happened,
    // swallow the click so releasing a drag on top of it doesn't navigate.
    items.forEach(function (el) {
      var card = el.querySelector(".cx-card");
      if (!card) return;
      card.addEventListener("click", function (e) {
        if (card.dataset.suppressClick === "true") {
          e.preventDefault();
        }
      });
    });

    var wheelLock = false;
    wrap.addEventListener("wheel", function (e) {
      e.preventDefault();
      if (wheelLock) return;
      wheelLock = true;
      setFocus(focusIndex + (e.deltaY > 0 ? 1 : -1));
      setTimeout(function () { wheelLock = false; }, 260);
    }, { passive: false });

    wrap.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); setFocus(focusIndex + 1); }
      if (e.key === "ArrowUp") { e.preventDefault(); setFocus(focusIndex - 1); }
    });

    window.addEventListener("resize", function () { layout(); });
    layout();
  }

  document.querySelectorAll(".cx-carousel-wrap").forEach(initCarousel);

  // --- Avatar bottom sheet: shared by every carousel page ---
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
