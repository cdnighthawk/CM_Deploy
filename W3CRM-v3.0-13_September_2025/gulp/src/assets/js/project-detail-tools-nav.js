/**
 * Project-details tool strip — six split parents. Label = default child tab.
 * Caret = other children. Does not persist last child.
 */
(function () {
	"use strict";

	var TAB_TO_PARENT = {
		"proj-tab-job": "job",
		"proj-tab-correspondence": "job",
		"proj-tab-drawings": "files",
		"proj-tab-specs": "files",
		"proj-tab-estimate": "estimate",
		"proj-tab-takeoff": "estimate",
		"proj-tab-schedule": "field",
		"proj-tab-tasks": "field",
		"proj-tab-safety": "field",
		"proj-tab-procurement": "buyout",
		"proj-tab-submittals": "buyout",
		"proj-tab-rfi": "buyout",
		"proj-tab-contract": "contract",
		"proj-tab-costing": "contract",
		"proj-tab-invoicing": "contract",
	};

	function projectId() {
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim();
	}

	function showTab(tabId) {
		var btn = document.getElementById(tabId);
		if (btn && window.bootstrap && window.bootstrap.Tab) {
			window.bootstrap.Tab.getOrCreateInstance(btn).show();
		}
	}

	function setActive(tabId) {
		var parentKey = TAB_TO_PARENT[tabId];
		var tools = document.querySelector(".usis-project-tools");
		if (!tools || !parentKey) return;
		var parents = tools.querySelectorAll(".usis-project-tool");
		var i;
		for (i = 0; i < parents.length; i++) {
			var on = parents[i].getAttribute("data-usis-parent") === parentKey;
			parents[i].classList.toggle("usis-project-tool--active", on);
		}
		var items = tools.querySelectorAll(".dropdown-item[data-usis-show-tab]");
		for (i = 0; i < items.length; i++) {
			var match = items[i].getAttribute("data-usis-show-tab") === tabId;
			items[i].classList.toggle("active", match);
			if (match) items[i].setAttribute("aria-current", "page");
			else items[i].removeAttribute("aria-current");
		}
	}

	function wireOutbound() {
		var pid = projectId();
		var q = pid ? "?project_id=" + encodeURIComponent(pid) : "";
		var docs = document.getElementById("usis-proj-tool-documents");
		if (docs) docs.setAttribute("href", "usis-documents-hub.html" + q);
		var rfp = document.getElementById("usis-proj-tool-rfp");
		if (rfp) rfp.setAttribute("href", "../usis-rfp-list.html" + q);
	}

	function init() {
		var tools = document.querySelector(".usis-project-tools");
		if (!tools) return;
		wireOutbound();
		tools.addEventListener("click", function (e) {
			var t = e.target.closest("[data-usis-show-tab]");
			if (!t || !tools.contains(t)) return;
			e.preventDefault();
			showTab(t.getAttribute("data-usis-show-tab"));
		});
		var hidden = document.querySelectorAll(".usis-project-tools-tablist [data-bs-toggle='pill']");
		var i;
		for (i = 0; i < hidden.length; i++) {
			hidden[i].addEventListener("shown.bs.tab", function () {
				setActive(this.id);
			});
		}
		var current = document.querySelector(".usis-project-tools-tablist .nav-link.active");
		if (current) setActive(current.id);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
