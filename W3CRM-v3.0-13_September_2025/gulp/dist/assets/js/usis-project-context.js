/**
 * Sets data-project-id on body from URL (?project_id=) or sessionStorage (Plan 1).
 * Stamps Home / Active projects / [number — name] only on pages that are actually
 * about that job. Company-wide lists (Projects, Estimate, Leads, dashboard) keep
 * the last job in session for defaults, but do not show it in the breadcrumb.
 */
(function (global) {
  "use strict";

  if (global.USISProjectContext) return;

  var KEY = "usis.activeProjectId";
  var crumbState = { projectId: null, item: null, inflight: null };

  function projectIdFromQuery() {
    try {
      var params = new URLSearchParams(global.location.search);
      var pid = (params.get("project_id") || params.get("projectId") || "").trim();
      if (pid) return pid;
      var path = (global.location.pathname || "").toLowerCase();
      if (/project-detail\.html/.test(path)) {
        return (params.get("id") || "").trim() || null;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  function readQuery() {
    return projectIdFromQuery();
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

  function stampPunchLinks(projectId) {
    if (!projectId) return;
    var a = document.getElementById("usis-punch-gc-add");
    if (a) {
      a.setAttribute(
        "href",
        "construction/punch-create.html?project_id=" + encodeURIComponent(projectId)
      );
      a.classList.remove("d-none");
    }
  }

  function stampSubmittalLinks(projectId) {
    if (!projectId) return;
    var a = document.getElementById("usis-submittal-open-create");
    if (a) {
      a.setAttribute(
        "href",
        "construction/submittal-create.html?project_id=" + encodeURIComponent(projectId)
      );
      a.classList.remove("d-none");
    }
  }

  function stampPoLinks(projectId) {
    if (!projectId) return;
    var a = document.getElementById("usis-po-open-create");
    if (a) {
      a.setAttribute(
        "href",
        "construction/purchase-order-create.html?project_id=" + encodeURIComponent(projectId)
      );
      a.classList.remove("d-none");
    }
  }

  function apiBase() {
    if (typeof global.usisApiBase === "function") {
      return global.usisApiBase();
    }
    if (typeof global.USIS_API_BASE === "string") {
      return global.USIS_API_BASE.trim().replace(/\/$/, "");
    }
    return "";
  }

  function crumbLabel(item) {
    var num = item && item.number != null ? String(item.number).trim() : "";
    var name = item && item.name != null ? String(item.name).trim() : "";
    if (num && name) return num + " — " + name;
    return num || name || "";
  }

  function breadcrumbList() {
    return document.querySelector(".page-title .breadcrumb");
  }

  function isCompanyWideListPage() {
    var path = (global.location.pathname || "").toLowerCase();
    return /(^|\/)(projects|estimate|leads|lead-goldenstate-planroom|usis-dashboard(-dark)?|usis-all-pages-index)\.html$/.test(
      path
    );
  }

  function setProjectsCrumbVisible(on) {
    var li = document.getElementById("usis-projects-crumb");
    if (!li) return;
    if (on) li.classList.remove("d-none");
    else li.classList.add("d-none");
  }

  function ensureCrumbs() {
    var ol = breadcrumbList();
    if (!ol) return null;
    var active = ol.querySelector(".breadcrumb-item.active");

    var projectsLi = document.getElementById("usis-projects-crumb");
    if (!projectsLi) {
      projectsLi = document.createElement("li");
      projectsLi.id = "usis-projects-crumb";
      projectsLi.className = "breadcrumb-item d-none";
      var projectsLink = document.createElement("a");
      projectsLink.setAttribute("href", "construction/projects.html");
      projectsLink.setAttribute("data-i18n", "Active projects");
      projectsLink.textContent = "Active projects";
      projectsLi.appendChild(projectsLink);
      if (active) ol.insertBefore(projectsLi, active);
      else ol.appendChild(projectsLi);
    }

    var projectLi =
      document.getElementById("usis-project-crumb") ||
      document.getElementById("usis-dv-project-crumb");
    if (!projectLi) {
      projectLi = document.createElement("li");
      projectLi.id = "usis-project-crumb";
      projectLi.className = "breadcrumb-item d-none";
      var link = document.createElement("a");
      link.id = "usis-project-crumb-link";
      link.setAttribute("href", "construction/projects.html");
      projectLi.appendChild(link);
      if (active) ol.insertBefore(projectLi, active);
      else ol.appendChild(projectLi);
    } else {
      projectLi.id = "usis-project-crumb";
      var existing =
        document.getElementById("usis-project-crumb-link") ||
        document.getElementById("usis-dv-project-crumb-link") ||
        projectLi.querySelector("a");
      if (existing) existing.id = "usis-project-crumb-link";
    }
    return projectLi;
  }

  function applyCrumb(item, projectId) {
    ensureCrumbs();
    var li = document.getElementById("usis-project-crumb");
    var link = document.getElementById("usis-project-crumb-link");
    if (!li || !link) return;
    var label = crumbLabel(item);
    if (!label || !projectId) {
      link.textContent = "";
      link.removeAttribute("title");
      link.setAttribute("href", "construction/projects.html");
      li.classList.add("d-none");
      setProjectsCrumbVisible(false);
      return;
    }
    link.textContent = label;
    link.setAttribute("title", label);
    link.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(projectId));
    li.classList.remove("d-none");
    setProjectsCrumbVisible(true);
  }

  function fetchProject(projectId) {
    if (!breadcrumbList()) return;
    ensureCrumbs();
    if (!projectId) {
      applyCrumb(null, null);
      return;
    }
    if (crumbState.item && crumbState.projectId === projectId) {
      applyCrumb(crumbState.item, projectId);
      return;
    }
    if (crumbState.inflight && crumbState.projectId === projectId) return;

    var base = apiBase();
    var url =
      String(base || "").replace(/\/$/, "") +
      "/api/v1/projects/" +
      encodeURIComponent(projectId);
    crumbState.projectId = projectId;
    crumbState.inflight = fetch(url, {
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        if (r.status === 404) {
          clear();
          applyCrumb(null, null);
          if (/project-detail\.html/i.test(global.location.pathname || "")) {
            global.location.href = "construction/projects.html";
          }
          return null;
        }
        if (!r.ok) return null;
        return r.json();
      })
      .then(function (data) {
        crumbState.inflight = null;
        if (!data) return;
        var item = data.item || data;
        crumbState.item = item;
        applyCrumb(item, projectId);
      })
      .catch(function () {
        crumbState.inflight = null;
      });
  }

  function apply(id, opts) {
    if (!id) return;
    opts = opts || {};
    var showCrumb = opts.showCrumb !== false && !isCompanyWideListPage();
    if (crumbState.projectId && crumbState.projectId !== id) {
      crumbState.item = null;
      crumbState.inflight = null;
    }
    document.body.setAttribute("data-project-id", id);
    try {
      global.sessionStorage.setItem(KEY, id);
    } catch (e) {}
    stampRfiLinks(id);
    stampPunchLinks(id);
    stampSubmittalLinks(id);
    stampPoLinks(id);
    var issuesLink = document.getElementById("usis-issue-open-log");
    if (issuesLink) {
      issuesLink.setAttribute("href", "construction/issues.html?project_id=" + encodeURIComponent(id));
      issuesLink.classList.remove("d-none");
    }
    if (showCrumb) {
      fetchProject(id);
    } else {
      applyCrumb(null, null);
    }
  }

  function clear() {
    document.body.removeAttribute("data-project-id");
    try {
      global.sessionStorage.removeItem(KEY);
    } catch (e) {}
    crumbState.projectId = null;
    crumbState.item = null;
    crumbState.inflight = null;
    applyCrumb(null, null);
  }

  function init() {
    if (document.querySelector(".usis-mobile-bottomnav")) {
      document.body.classList.add("usis-has-bottomnav");
    }
    ensureCrumbs();
    var fromQuery = readQuery();
    if (fromQuery) {
      apply(fromQuery, { showCrumb: !isCompanyWideListPage() });
      return;
    }
    try {
      var stored = global.sessionStorage.getItem(KEY);
      if (stored) {
        apply(stored, { showCrumb: false });
      } else {
        applyCrumb(null, null);
      }
    } catch (e) {
      applyCrumb(null, null);
    }
  }

  global.USISProjectContext = {
    init: init,
    projectIdFromQuery: projectIdFromQuery,
    setProjectId: function (id) {
      apply(id);
    },
    getProjectId: function () {
      return document.body.getAttribute("data-project-id") || projectIdFromQuery();
    },
    clear: clear,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : this);
