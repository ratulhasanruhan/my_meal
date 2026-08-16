/* My Meal — theme, toasts, meal quantities and the day editor. No dependencies. */

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

  // --- meal editing --------------------------------------------------------
  var app = document.querySelector("[data-set-meal-url]");
  if (!app) return;

  var setMealUrl = app.dataset.setMealUrl;
  var currency = app.dataset.currency || "";
  var maxQty = parseInt(app.dataset.maxQty, 10) || 20;

  var sheet = document.getElementById("day-sheet");
  var backdrop = document.getElementById("sheet-backdrop");

  function csrfToken() {
    var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : "";
  }

  function money(n) {
    return currency + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  /** The scope chosen in the sheet; controls outside the sheet are always one-off. */
  function scopeFor(slotEl) {
    if (!sheet || !sheet.contains(slotEl)) return "once";
    var picked = sheet.querySelector('input[name="scope"]:checked');
    return picked ? picked.value : "once";
  }

  function paintSlot(slotEl, qty) {
    slotEl.dataset.qty = qty;
    slotEl.classList.toggle("is-on", qty > 0);
    var main = slotEl.querySelector("[data-slot-toggle]");
    if (main) main.setAttribute("aria-pressed", String(qty > 0));
    var value = slotEl.querySelector("[data-qty-value]");
    if (value) value.textContent = qty;
    var hint = slotEl.querySelector("[data-slot-hint]");
    if (hint) hint.textContent = qty ? qty + " meal" + (qty === 1 ? "" : "s") : "Skipped";
    var minus = slotEl.querySelector('[data-step="-1"]');
    if (minus) minus.disabled = qty <= 0;
    var plus = slotEl.querySelector('[data-step="1"]');
    if (plus) plus.disabled = qty >= maxQty;
  }

  /** Repaint the calendar and the month totals from the server's response. */
  function applyResponse(data) {
    document
      .querySelectorAll('.slot[data-date="' + data.date + '"][data-slot="' + data.slot + '"]')
      .forEach(function (el) { paintSlot(el, data.quantity); });

    (data.days || []).forEach(function (d) {
      var cell = document.querySelector('.cal-day[data-date="' + d.date + '"]');
      if (!cell) return;
      cell.dataset.lunch = d.lunch;
      cell.dataset.dinner = d.dinner;
      var lunchDot = cell.querySelector('[data-dot="lunch"]');
      if (lunchDot) lunchDot.classList.toggle("cal-day__dot--on-lunch", d.lunch > 0);
      var dinnerDot = cell.querySelector('[data-dot="dinner"]');
      if (dinnerDot) dinnerDot.classList.toggle("cal-day__dot--on-dinner", d.dinner > 0);
      var cost = cell.querySelector("[data-day-cost]");
      if (cost) cost.textContent = d.cost > 0 ? money(d.cost) : "";
    });

    var total = document.querySelector("[data-month-cost]");
    if (total) total.textContent = Number(data.month_cost).toLocaleString(undefined, { maximumFractionDigits: 0 });
    var count = document.querySelector("[data-month-meals]");
    if (count) count.textContent = data.month_meals;
    var due = document.querySelector("[data-month-due]");
    if (due) due.textContent = Number(data.month_due).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  var pending = false;

  function submit(slotEl, quantity) {
    if (pending) return;
    pending = true;
    slotEl.classList.add("is-saving");

    fetch(setMealUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({
        date: slotEl.dataset.date,
        slot: slotEl.dataset.slot,
        quantity: quantity,
        scope: scopeFor(slotEl),
      }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (e) { throw new Error(e.error || "Failed"); });
        return r.json();
      })
      .then(applyResponse)
      .catch(function (err) { alert(err.message || "Could not save. Check your connection."); })
      .finally(function () {
        pending = false;
        slotEl.classList.remove("is-saving");
      });
  }

  document.addEventListener("click", function (event) {
    var step = event.target.closest("[data-step]");
    if (step) {
      var slotEl = step.closest(".slot");
      var next = parseInt(slotEl.dataset.qty, 10) + parseInt(step.dataset.step, 10);
      next = Math.max(0, Math.min(maxQty, next));
      paintSlot(slotEl, next);
      submit(slotEl, next);
      return;
    }

    var toggle = event.target.closest("[data-slot-toggle]");
    if (toggle) {
      var el = toggle.closest(".slot");
      var qty = parseInt(el.dataset.qty, 10) > 0 ? 0 : 1;
      paintSlot(el, qty);
      submit(el, qty);
      return;
    }

    var opener = event.target.closest("[data-open-sheet]");
    if (opener) {
      var cell = document.querySelector('.cal-day[data-date="' + opener.dataset.openSheet + '"]');
      if (cell) openSheet(cell);
      return;
    }

    var day = event.target.closest(".cal-day");
    if (day && !day.disabled && !suppressClick) { openSheet(day); return; }

    if (event.target.closest("[data-close-sheet]") || event.target === backdrop) closeSheet();
  });

  // --- day editor sheet ----------------------------------------------------
  if (!sheet || !backdrop) return;

  var lastFocused = null;
  var suppressClick = false;

  function openSheet(cell, presetScope) {
    sheet.querySelector("[data-sheet-title]").textContent = cell.dataset.label;
    sheet.querySelector("[data-sheet-sub]").textContent = cell.dataset.date > todayISO()
      ? "A future day — changes here become part of your plan."
      : "Adjust the meals, then choose how far the change should reach.";

    var weekdayLabel = sheet.querySelector("[data-scope-weekday]");
    if (weekdayLabel) weekdayLabel.textContent = "Every " + cell.dataset.weekdayName;

    var scopeInput = sheet.querySelector(
      'input[name="scope"][value="' + (presetScope || "once") + '"]'
    );
    if (scopeInput) scopeInput.checked = true;

    sheet.querySelectorAll(".slot").forEach(function (slotEl) {
      slotEl.dataset.date = cell.dataset.date;
      paintSlot(slotEl, parseInt(cell.dataset[slotEl.dataset.slot], 10) || 0);
    });

    lastFocused = document.activeElement;
    backdrop.dataset.open = "true";
    sheet.dataset.open = "true";
    sheet.hidden = false;
    var first = sheet.querySelector("[data-slot-toggle]");
    if (first) first.focus();
  }

  function closeSheet() {
    backdrop.dataset.open = "false";
    sheet.dataset.open = "false";
    if (lastFocused) lastFocused.focus();
  }

  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sheet.dataset.open === "true") closeSheet();
  });

  // Long-press a day (or a slot) to jump straight to the recurring options.
  var pressTimer = null;

  function startPress(event) {
    var target = event.target.closest(".cal-day, .slot");
    if (!target) return;
    pressTimer = setTimeout(function () {
      suppressClick = true;
      if (navigator.vibrate) navigator.vibrate(12);
      var cell = target.classList.contains("cal-day")
        ? target
        : document.querySelector('.cal-day[data-date="' + target.dataset.date + '"]');
      if (cell) openSheet(cell, "onward");
      pressTimer = null;
    }, 550);
  }

  function endPress() {
    if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
    setTimeout(function () { suppressClick = false; }, 60);
  }

  document.addEventListener("pointerdown", startPress);
  document.addEventListener("pointerup", endPress);
  document.addEventListener("pointercancel", endPress);
  document.addEventListener("pointermove", function () {
    if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; }
  });
  document.addEventListener("contextmenu", function (event) {
    if (event.target.closest(".cal-day, .slot")) event.preventDefault();
  });
})();
