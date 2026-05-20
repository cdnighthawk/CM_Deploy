/**
 * Sets data-project-id on body from URL (?project_id=) or sessionStorage (Plan 1).
 */
(function (global) {
  "use strict";

  var KEY = "usis.activeProjectId";

  function readQuery() {
    try {
      var params = new URLSearchParams(global.location.search);
      return params.get("project_id") || params.get("projectId");
    } catch (e) {
      return null;
    }
  }

  function apply(id) {
    if (!id) return;
    document.body.setAttribute("data-project-id", id);
    try {
      global.sessionStorage.setItem(KEY, id);
    } catch (e) {}
  }

  function apiBase() {
    if (typeof global.usisApiBase === "function") {
      return global.usisApiBase();
    }
    if (typeof global.USIS_API_BASE === "string" && global.USIS_API_BASE.trim()) {
      return global.USIS_API_BASE.trim().replace(/\/$/, "");
    }
    return "";
  }

  function verifyProjectAccess(projectId) {
    var base = apiBase();
    if (!base || !projectId) return;
    fetch(base.replace(/\/$/, "") + "/api/v1/projects/" + encodeURIComponent(projectId), {
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        if (r.status === 404) {
          clear();
          if (/project-detail\.html/i.test(global.location.pathname || "")) {
            global.location.href = "construction/projects.html";
          }
        }
      })
      .catch(function () {});
  }

  function init() {
    if (document.querySelector(".usis-mobile-bottomnav")) {
      document.body.classList.add("usis-has-bottomnav");
    }
    var fromQuery = readQuery();
    if (fromQuery) {
      apply(fromQuery);
      verifyProjectAccess(fromQuery);
      return;
    }
    try {
      var stored = global.sessionStorage.getItem(KEY);
      if (stored) {
        apply(stored);
        verifyProjectAccess(stored);
      }
    } catch (e) {}
  }

  global.USISProjectContext = {
    init: init,
    setProjectId: function (id) {
      apply(id);
    },
    getProjectId: function () {
      return document.body.getAttribute("data-project-id") || null;
    },
    clear: function () {
      document.body.removeAttribute("data-project-id");
      try {
        global.sessionStorage.removeItem(KEY);
      } catch (e) {}
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : this);
