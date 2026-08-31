/**
 * Project-details tool strip — parents + a visible child row.
 * Parent click = default child. Submittals and RFIs are one-click parents (no child row).
 */
(function () {
	"use strict";

	var PARENT_LABEL = {
		job: "Contract pages",
		files: "Files pages",
		preconstruction: "Preconstruction pages",
		field: "Field pages",
		buyout: "Buyout pages",
	};

	var TAB_TO_PARENT = {
		"proj-tab-job": "job",
		"proj-tab-openitems": "job",
		"proj-tab-contract": "job",
		"proj-tab-costing": "job",
		"proj-tab-invoicing": "job",
		"proj-tab-drawings": "files",
		"proj-tab-specs": "files",
		"proj-tab-estimate": "preconstruction",
		"proj-tab-takeoff": "preconstruction",
		"proj-tab-procurement": "buyout",
		"proj-tab-submittals": "submittals",
		"proj-tab-rfi": "rfi",
		"proj-tab-correspondence": "buyout",
		"proj-tab-transmittals": "buyout",
		"proj-tab-anticipated": "buyout",
		"proj-tab-subinv": "buyout",
		"proj-tab-schedule": "field",
		"proj-tab-tasks": "field",
		"proj-tab-photos": "field",
		"proj-tab-dailylog": "field",
		"proj-tab-meetings": "field",
		"proj-tab-wo": "field",
		"proj-tab-qc": "field",
		"proj-tab-punch": "field",
		"proj-tab-incidents": "field",
		"proj-tab-safety": "field",
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
		var stack = document.querySelector(".usis-project-tools-stack");
		if (!stack || !parentKey) return;
		var parents = stack.querySelectorAll(".usis-project-tool");
		var i;
		for (i = 0; i < parents.length; i++) {
			var on = parents[i].getAttribute("data-usis-parent") === parentKey;
			parents[i].classList.toggle("usis-project-tool--active", on);
		}
		var groups = stack.querySelectorAll(".usis-project-subtools__group");
		var shown = false;
		for (i = 0; i < groups.length; i++) {
			var vis = groups[i].getAttribute("data-usis-parent") === parentKey;
			groups[i].hidden = !vis;
			if (vis) shown = true;
		}
		var sub = stack.querySelector(".usis-project-subtools");
		if (sub) {
			sub.hidden = !shown;
			sub.setAttribute("aria-label", PARENT_LABEL[parentKey] || "Project pages");
		}
		stack.classList.toggle("usis-project-tools-stack--leaf", !shown);
		var items = stack.querySelectorAll(".usis-project-subtool[data-usis-show-tab]");
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
		if (docs) docs.setAttribute("href", "../usis-documents-hub.html" + q);
		var rfp = document.getElementById("usis-proj-tool-rfp");
		if (rfp) rfp.setAttribute("href", "../usis-rfp-list.html" + q);
	}

	function init() {
		var stack = document.querySelector(".usis-project-tools-stack");
		if (!stack) return;
		wireOutbound();
		stack.addEventListener("click", function (e) {
			var t = e.target.closest("[data-usis-show-tab]");
			if (!t || !stack.contains(t)) return;
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
