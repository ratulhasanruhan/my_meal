/* My Meal — theme toggle, toasts, meal toggling. No dependencies. */

(function () {
  "use strict";

  // --- theme ---------------------------------------------------------------
  var root = document.documentElement;

  function currentTheme() {
    return (
      root.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    );
  }

  function paintThemeIcon() {
    var dark = currentTheme() === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      var sun = btn.querySelector('[data-icon="sun"]');
      var moon = btn.querySelector('[data-icon="moon"]');
      if (sun) sun.hidden = !dark;
      if (moon) moon.hidden = dark;
    });
  }

  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      paintThemeIcon();
    });
  });
  paintThemeIcon();

  // --- toasts --------------------------------------------------------------
  var toasts = document.getElementById("toasts");
  if (toasts) {
    setTimeout(function () {
      toasts.style.transition = "opacity .3s";
      toasts.style.opacity = "0";
      setTimeout(function () { toasts.remove(); }, 320);
    }, 3200);
  }

  // --- meal toggling -------------------------------------------------------
  var app = document.querySelector("[data-toggle-url]");
  if (!app) return;

  var toggleUrl = app.dataset.toggleUrl;
  var currency = app.dataset.currency || "";

  function csrfToken() {
    var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : "";
  }

  function money(n) {
    return currency + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  function postToggle(date, slot) {
    return fetch(toggleUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ date: date, slot: slot }),
    }).then(function (r) {
      if (!r.ok) throw new Error("Request failed");
      return r.json();
    });
  }

  /** Repaint every control bound to one date+slot, plus the month totals. */
  function applyState(data) {
    document
      .querySelectorAll('.slot-toggle[data-date="' + data.date + '"][data-slot="' + data.slot + '"]')
      .forEach(function (btn) { btn.setAttribute("aria-pressed", String(data.active)); });

    var cell = document.querySelector('.cal-day[data-date="' + data.date + '"]');
    if (cell) {
      var dot = cell.querySelector('[data-dot="' + data.slot + '"]');
      if (dot) dot.classList.toggle("cal-day__dot--on-" + data.slot, data.active);
      var cost = cell.querySelector("[data-day-cost]");
      if (cost) cost.textContent = data.day_cost > 0 ? money(data.day_cost) : "";
    }

    var total = document.querySelector("[data-month-cost]");
    if (total) total.textContent = money(data.month_cost);
    var count = document.querySelector("[data-month-meals]");
    if (count) count.textContent = data.month_meals;
  }

  document.addEventListener("click", function (event) {
    var btn = event.target.closest(".slot-toggle");
    if (!btn || btn.disabled) return;

    btn.disabled = true;
    postToggle(btn.dataset.date, btn.dataset.slot)
      .then(applyState)
      .catch(function () { alert("Could not save that meal. Check your connection and try again."); })
      .finally(function () { btn.disabled = false; });
  });

  // --- day editor sheet ----------------------------------------------------
  var sheet = document.getElementById("day-sheet");
  var backdrop = document.getElementById("sheet-backdrop");
  if (!sheet || !backdrop) return;

  var lastFocused = null;

  function openSheet(cell) {
    var date = cell.dataset.date;
    sheet.querySelector("[data-sheet-title]").textContent = cell.dataset.label;
    sheet.querySelector("[data-sheet-sub]").textContent =
      "Tap a slot to mark it taken or skipped.";

    sheet.querySelectorAll(".slot-toggle").forEach(function (btn) {
      var slot = btn.dataset.slot;
      btn.dataset.date = date;
      var dot = cell.querySelector('[data-dot="' + slot + '"]');
      var on = dot ? dot.classList.contains("cal-day__dot--on-" + slot) : false;
      btn.setAttribute("aria-pressed", String(on));
    });

    lastFocused = document.activeElement;
    backdrop.dataset.open = "true";
    sheet.dataset.open = "true";
    sheet.hidden = false;
    sheet.querySelector(".slot-toggle").focus();
  }

  function closeSheet() {
    backdrop.dataset.open = "false";
    sheet.dataset.open = "false";
    if (lastFocused) lastFocused.focus();
  }

  document.addEventListener("click", function (event) {
    var cell = event.target.closest(".cal-day");
    if (cell && !cell.disabled) { openSheet(cell); return; }
    if (event.target.closest("[data-close-sheet]") || event.target === backdrop) closeSheet();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sheet.dataset.open === "true") closeSheet();
  });
})();
