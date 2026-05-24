/*
 * Ensayo keyword chatbot — deterministic, client-side, zero dependencies.
 *
 * Powers chatbots in keyword mode (spec §2.3 TechNova pattern, the minors-safe
 * default). No network, no LLM. Reads its response data from a JSON <script>
 * tag and renders a small chat panel.
 *
 * Usage in a page:
 *   <div data-ensayo-chat></div>
 *   <script type="application/json" id="ensayo-kw-data"> { ...keywords... } </script>
 *   <script src="/ensayo/keyword-chatbot.js"></script>
 */
(function () {
  "use strict";

  function loadData() {
    var el = document.getElementById("ensayo-kw-data");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.error("ensayo: invalid keyword data", e);
      return null;
    }
  }

  function normalise(s) {
    return (s || "").toLowerCase().replace(/[^a-z0-9\s-]/g, " ");
  }

  function bestResponse(data, input) {
    var text = normalise(input);
    var best = null;
    var bestScore = 0;
    (data.rules || []).forEach(function (rule) {
      var score = 0;
      (rule.keywords || []).forEach(function (kw) {
        if (kw && text.indexOf(normalise(kw)) !== -1) score += 1;
      });
      if (score > bestScore) {
        bestScore = score;
        best = rule.response;
      }
    });
    return best || data.fallback || "I'm not sure how to answer that.";
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function mount(container, data) {
    container.classList.add("ensayo-chat");
    var log = el("div", "ensayo-chat-log");
    var form = el("form", "ensayo-chat-form");
    var input = el("input", "ensayo-chat-input");
    input.type = "text";
    input.placeholder = "Ask " + (data.employee || "me") + " a question…";
    input.setAttribute("aria-label", "Chat message");
    var send = el("button", "ensayo-chat-send", "Send");
    send.type = "submit";

    function add(role, text) {
      var msg = el("div", "ensayo-msg ensayo-msg-" + role);
      msg.appendChild(el("span", "ensayo-msg-text", text));
      log.appendChild(msg);
      log.scrollTop = log.scrollHeight;
    }

    add("bot", data.greeting || "Hello. How can I help?");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      if (!q) return;
      add("user", q);
      input.value = "";
      // Tiny delay so the exchange feels conversational.
      setTimeout(function () {
        add("bot", bestResponse(data, q));
      }, 250);
    });

    form.appendChild(input);
    form.appendChild(send);
    container.appendChild(log);
    container.appendChild(form);
  }

  function init() {
    var data = loadData();
    if (!data) return;
    var containers = document.querySelectorAll("[data-ensayo-chat]");
    Array.prototype.forEach.call(containers, function (c) {
      mount(c, data);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
