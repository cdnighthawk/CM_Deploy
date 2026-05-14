/**
 * Bootstrap 5 toast helper (Plan 1).
 */
(function (global) {
  "use strict";

  function ensureContainer() {
    var el = document.getElementById("usis-toast-container");
    if (el) return el;
    el = document.createElement("div");
    el.id = "usis-toast-container";
    el.className = "toast-container position-fixed top-0 end-0 p-3";
    el.setAttribute("style", "z-index: 10800;");
    document.body.appendChild(el);
    return el;
  }

  function show(message, variant) {
    if (typeof global.bootstrap === "undefined" || !global.bootstrap.Toast) {
      if (global.console && console.log) console.log("[USIS]", variant, message);
      return;
    }
    variant = variant || "info";
    var wrap = document.createElement("div");
    wrap.className = "toast align-items-center text-bg-" + variant + " border-0";
    wrap.setAttribute("role", "alert");
    wrap.setAttribute("aria-live", "polite");
    wrap.setAttribute("aria-atomic", "true");
    wrap.innerHTML =
      '<div class="d-flex">' +
      '<div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
      "</div>";
    wrap.querySelector(".toast-body").textContent = message;
    var container = ensureContainer();
    container.appendChild(wrap);
    var t = new global.bootstrap.Toast(wrap, { delay: 4000 });
    wrap.addEventListener("hidden.bs.toast", function () {
      wrap.remove();
    });
    t.show();
  }

  global.USISNotify = {
    info: function (m) {
      show(m, "info");
    },
    success: function (m) {
      show(m, "success");
    },
    warning: function (m) {
      show(m, "warning");
    },
    error: function (m) {
      show(m, "danger");
    },
  };
})(typeof window !== "undefined" ? window : this);
