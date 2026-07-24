// Live header clock + verse-card date for the redesigned main dashboards
// (user/staff/admin). Pure client-side — the server already renders which
// verse to show (see app/verses.py); this just formats "now" for display,
// the same way any phone lock screen would, and re-runs once a minute.
(function () {
  "use strict";

  const WEEKDAYS = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"];
  const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  function render() {
    const now = new Date();

    const timeEl = document.getElementById("gc-clock-time");
    const ampmEl = document.getElementById("gc-clock-ampm");
    if (timeEl && ampmEl) {
      let hours = now.getHours();
      const ampm = hours >= 12 ? "PM" : "AM";
      hours = hours % 12;
      if (hours === 0) hours = 12;
      timeEl.textContent = pad(hours) + ":" + pad(now.getMinutes());
      ampmEl.textContent = " " + ampm;
    }

    const dateEl = document.getElementById("gc-verse-date");
    if (dateEl) {
      dateEl.textContent =
        WEEKDAYS[now.getDay()] + "\n" +
        pad(now.getDate()) + " " + MONTHS[now.getMonth()] + " " + now.getFullYear();
    }
  }

  render();
  setInterval(render, 15000);
})();
