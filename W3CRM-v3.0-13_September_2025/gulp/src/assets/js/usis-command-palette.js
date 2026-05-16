/**
 * Ctrl+K command palette — search + AI placeholder (Plan 1).
 * Uses GET /api/v1/search when backend exposes it.
 */
(function (global) {
  "use strict";

  function apiBase() {
    if (typeof global.usisApiBase === "function") return global.usisApiBase();
    if (typeof global.USIS_API_BASE === "string") {
      return global.USIS_API_BASE.trim().replace(/\/$/, "");
    }
    return "http://127.0.0.1:5000";
  }

  function ensureModal() {
    var existing = document.getElementById("usis-command-palette-modal");
    if (existing) return existing;
    var wrap = document.createElement("div");
    wrap.className = "modal fade";
    wrap.id = "usis-command-palette-modal";
    wrap.tabIndex = -1;
    wrap.setAttribute("aria-hidden", "true");
    wrap.innerHTML =
      '<div class="modal-dialog modal-dialog-centered modal-lg">' +
      '<div class="modal-content">' +
      '<div class="modal-header py-2">' +
      '<h5 class="modal-title">Command palette</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
      '</div>' +
      '<div class="modal-body">' +
      '<input type="search" class="form-control form-control-lg mb-2" id="usis-cmd-q" placeholder="Search projects, leads, documents… (Ctrl+K)" autocomplete="off">' +
      '<div id="usis-cmd-results" class="list-group small"></div>' +
      '<p class="text-muted small mb-0 mt-2">AI chat routes can plug in here when <code>/api/v1/ai/*</code> is available.</p>' +
      "</div>" +
      "</div>" +
      "</div>";
    document.body.appendChild(wrap);
    return wrap;
  }

  function renderResults(container, items) {
    container.innerHTML = "";
    if (!items || !items.length) {
      container.innerHTML =
        '<div class="list-group-item text-muted">No results — try another query or check API.</div>';
      return;
    }
    items.forEach(function (row) {
      var a = document.createElement("a");
      a.className = "list-group-item list-group-item-action";
      a.href = row.href || "#";
      a.textContent = row.label || row.title || JSON.stringify(row);
      container.appendChild(a);
    });
  }

  function runSearch(q, outEl) {
    outEl.innerHTML = '<div class="list-group-item text-muted">Searching…</div>';
    var url = apiBase().replace(/\/$/, "") + "/api/v1/search?q=" + encodeURIComponent(q);
    fetch(url, { credentials: "include", headers: { Accept: "application/json" } })
      .then(function (r) {
        if (r.status === 404) throw new Error("no_search_endpoint");
        if (!r.ok) throw new Error("http_" + r.status);
        return r.json();
      })
      .then(function (data) {
        var items = data.items || data.results || data;
        if (!Array.isArray(items)) items = [];
        renderResults(outEl, items);
      })
      .catch(function () {
        renderResults(outEl, [
          { label: "Open Leads", href: "construction/leads.html" },
          { label: "Open Projects", href: "construction/projects.html" },
          { label: "Dashboard", href: "usis-dashboard.html" },
        ]);
      });
  }

  function open() {
    if (typeof global.bootstrap === "undefined" || !global.bootstrap.Modal) return;
    var el = ensureModal();
    var modal = global.bootstrap.Modal.getOrCreateInstance(el);
    modal.show();
    setTimeout(function () {
      var input = document.getElementById("usis-cmd-q");
      var out = document.getElementById("usis-cmd-results");
      if (input) {
        input.value = "";
        input.focus();
        input.oninput = function () {
          var q = (input.value || "").trim();
          if (q.length < 2) {
            out.innerHTML = '<div class="list-group-item text-muted">Type at least 2 characters…</div>';
            return;
          }
          runSearch(q, out);
        };
      }
    }, 200);
  }

  function init() {
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        open();
      }
    });
  }

  global.USISCommandPalette = { init: init, open: open };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : this);
