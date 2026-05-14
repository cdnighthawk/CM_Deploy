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

  function init() {
    if (document.querySelector(".usis-mobile-bottomnav")) {
      document.body.classList.add("usis-has-bottomnav");
    }
    var fromQuery = readQuery();
    if (fromQuery) {
      apply(fromQuery);
      return;
    }
    try {
      var stored = global.sessionStorage.getItem(KEY);
      if (stored) apply(stored);
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
