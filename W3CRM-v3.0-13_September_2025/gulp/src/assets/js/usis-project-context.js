/**
 * Sets data-project-id on body from URL (?project_id=) or sessionStorage (Plan 1).
 */
(function (global) {
  "use strict";

  var KEY = "usis.activeProjectId";

  function readQuery() {
    try {
      var params = new URLSearchParams(global.location.search);
      var pid = params.get("project_id") || params.get("projectId");
      if (pid) return pid;
      var path = (global.location.pathname || "").toLowerCase();
      if (/project-detail\.html/.test(path)) {
        return params.get("id");
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  function stampRfiLinks(projectId) {
    if (!projectId) return;
    var createIds = [
      "usis-rfi-open-create",
      "usis-lead-rfi-open-create",
      "usis-estd-rfi-open-create",
      "usis-rfi-create-link",
    ];
    createIds.forEach(function (id) {
      var a = document.getElementById(id);
      if (a) {
        a.setAttribute(
          "href",
          "construction/rfi-create.html?project_id=" + encodeURIComponent(projectId)
        );
        a.classList.remove("d-none");
      }
    });
    var logIds = [
      "usis-rfi-open-log",
      "usis-lead-rfi-open-log",
      "usis-estd-rfi-open-log",
    ];
    logIds.forEach(function (id) {
      var log = document.getElementById(id);
      if (log) {
        log.setAttribute(
          "href",
          "construction/rfis.html?project_id=" + encodeURIComponent(projectId)
        );
        log.classList.remove("d-none");
      }
    });
  }

  function apply(id) {
    if (!id) return;
    document.body.setAttribute("data-project-id", id);
    try {
      global.sessionStorage.setItem(KEY, id);
    } catch (e) {}
    stampRfiLinks(id);
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
