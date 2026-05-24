/*
 * Ensayo booking gate — unlock an employee's chat after booking an appointment
 * (CloudCore pattern, spec §6.3). Calls the Ensayo booking API. The chat content
 * sits in a sibling [data-ensayo-chat-wrap] that starts hidden; once the student
 * has a booking whose start time has passed ("attended"), it is revealed.
 *
 * API origin: window.ENSAYO_API_BASE ("" = same origin). Simulation slug:
 * window.ENSAYO_SIM_SLUG. Both are emitted by the theme's layout.
 *
 * Note: this is a UX gate, not a security boundary — server-enforced gating is
 * done with visibility rules. Suitable for low-stakes teaching.
 */
(function () {
  "use strict";

  var API = (window.ENSAYO_API_BASE || "").replace(/\/$/, "");
  var SLUG = window.ENSAYO_SIM_SLUG || "";

  function api(path) { return API + path; }
  function key(emp) { return "ensayo_booking_" + SLUG + "_" + emp; }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function fmt(iso) {
    var d = new Date(iso);
    return d.toLocaleString([], { weekday: "short", day: "numeric", month: "short",
      hour: "2-digit", minute: "2-digit" });
  }

  function reveal(gate, wrap) {
    if (wrap) wrap.hidden = false;
    gate.style.display = "none";
  }

  function setup(gate) {
    var emp = gate.getAttribute("data-employee");
    var name = gate.getAttribute("data-employee-name") || "this person";
    var wrap = gate.parentElement.querySelector("[data-ensayo-chat-wrap]");

    var stored = null;
    try { stored = JSON.parse(localStorage.getItem(key(emp))); } catch (e) {}
    if (stored && stored.slot_start) {
      if (new Date(stored.slot_start) <= new Date()) { reveal(gate, wrap); return; }
      renderBooked(gate, name, stored.slot_start);
      return;
    }
    renderForm(gate, emp, name, wrap);
  }

  function renderBooked(gate, name, slot) {
    gate.innerHTML = "";
    var card = el("div", "card");
    card.appendChild(el("h3", null, "Appointment booked"));
    card.appendChild(el("p", "muted",
      "Your appointment with " + name + " is booked for " + fmt(slot) +
      ". Come back at that time to chat."));
    gate.appendChild(card);
  }

  function renderForm(gate, emp, name, wrap) {
    gate.innerHTML = "";
    var card = el("div", "card");
    card.appendChild(el("h3", null, "Book an appointment to chat with " + name));
    card.appendChild(el("p", "muted small",
      "Pick a day, choose a time, and you'll be able to chat once your appointment begins."));

    var date = el("input"); date.type = "date";
    date.className = "ensayo-chat-input"; date.style.maxWidth = "200px";
    date.value = new Date().toISOString().slice(0, 10);
    var find = el("button", "btn btn-ghost", "Find times"); find.type = "button";
    var row = el("div"); row.style.display = "flex"; row.style.gap = "0.5rem"; row.style.margin = "0.6rem 0";
    row.appendChild(date); row.appendChild(find);
    card.appendChild(row);

    var slots = el("div"); slots.style.display = "flex"; slots.style.flexWrap = "wrap"; slots.style.gap = "0.4rem";
    card.appendChild(slots);

    var nameI = el("input"); nameI.type = "text"; nameI.placeholder = "Your name"; nameI.className = "ensayo-chat-input"; nameI.style.marginTop = "0.6rem";
    var mailI = el("input"); mailI.type = "email"; mailI.placeholder = "Your email (optional)"; mailI.className = "ensayo-chat-input"; mailI.style.marginTop = "0.4rem";
    card.appendChild(nameI); card.appendChild(mailI);

    var note = el("p", "muted small"); note.style.marginTop = "0.5rem"; card.appendChild(note);
    gate.appendChild(card);

    find.addEventListener("click", function () {
      note.textContent = "Loading available times…"; slots.innerHTML = "";
      fetch(api("/api/v1/sims/" + SLUG + "/availability?employee=" + encodeURIComponent(emp) +
                "&date=" + date.value))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          note.textContent = "";
          var list = (d && d.slots) || [];
          if (!list.length) { note.textContent = "No times available that day."; return; }
          list.forEach(function (s) {
            var b = el("button", "btn btn-ghost", new Date(s.slot_start).toLocaleTimeString([],
              { hour: "2-digit", minute: "2-digit" }));
            b.type = "button";
            b.addEventListener("click", function () { book(emp, s.slot_start, nameI.value, mailI.value, note, gate, wrap, name); });
            slots.appendChild(b);
          });
        })
        .catch(function () { note.textContent = "Could not load times. Try again."; });
    });
  }

  function book(emp, slot, sname, smail, note, gate, wrap, name) {
    note.textContent = "Booking…";
    fetch(api("/api/v1/sims/" + SLUG + "/bookings"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_slug: emp, slot_start: slot,
        student_name: sname || "", student_email: smail || "" })
    }).then(function (r) {
      if (!r.ok) { return r.json().then(function (d) { throw new Error(d.detail || "Booking failed"); }); }
      return r.json();
    }).then(function () {
      localStorage.setItem(key(emp), JSON.stringify({ slot_start: slot }));
      if (new Date(slot) <= new Date()) reveal(gate, wrap);
      else renderBooked(gate, name, slot);
    }).catch(function (e) { note.textContent = e.message; });
  }

  function init() {
    if (!SLUG) return;
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-ensayo-booking-gate]"), setup);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
