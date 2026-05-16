/**
 * Construction — Pricing: project takeoff lines with L/M/E/S/O cost types.
 * URL: construction/construction-pricing.html?project_id=<uuid>
 */
(function () {
	"use strict";

	var PL = window.USISPricingLines;
	if (!PL) return;

	var projectId = null;
	var lines = [];
	var pendingSection = "";
	var feePct = null;

	function showErr(msg) {
		var el = document.getElementById("usis-cp-error");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function getMarkupPct() {
		var inp = document.getElementById("usis-cp-markup-pct");
		if (!inp || inp.value === "") return 0;
		var n = Number(String(inp.value).replace(",", "."));
		return isNaN(n) ? 0 : n;
	}

	function refreshUi() {
		PL.renderTableBody(lines, {
			tbodyId: "usis-cp-lines-tbody",
			colSpan: 10,
			markupPct: getMarkupPct(),
			inputClass: "usis-cp-inp",
		});
		PL.renderRollup(lines, {
			idPrefix: "usis-cp-roll",
			feePct: feePct,
			markupPct: getMarkupPct(),
		});
	}

	function loadLines() {
		if (!projectId) return Promise.resolve();
		showErr("");
		return PL.loadProjectLines(projectId)
			.then(function (data) {
				lines = data.items || [];
				refreshUi();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
				lines = [];
				refreshUi();
			});
	}

	function addLine(sectionOverride) {
		if (!projectId) {
			if (window.USISNotify) window.USISNotify.warning("Add project_id to the URL.");
			return;
		}
		var sec = sectionOverride != null ? sectionOverride : pendingSection;
		var body = {
			description: "New line",
			quantity: 1,
			unit: "EA",
			unit_cost: 0,
			cost_type: "M",
		};
		if (sec) body.section = String(sec).trim().slice(0, 120);
		PL.createProjectLine(projectId, body)
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Line added");
				return loadLines();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
				if (window.USISNotify) window.USISNotify.error(String(e.message || e));
			});
	}

	function promptSectionAndAdd() {
		var name = window.prompt("Section name", pendingSection || "");
		if (name == null) return;
		pendingSection = String(name).trim();
		var secInp = document.getElementById("usis-cp-section-default");
		if (secInp) secInp.value = pendingSection;
		addLine(pendingSection || undefined);
	}

	function init() {
		var q = new URLSearchParams(window.location.search);
		projectId = (q.get("project_id") || "").trim() || null;

		var root = document.getElementById("usis-cp-root");
		var noProj = document.getElementById("usis-cp-no-project");
		if (!projectId) {
			if (root) root.classList.add("d-none");
			if (noProj) noProj.classList.remove("d-none");
			return;
		}
		if (root) root.classList.remove("d-none");
		if (noProj) noProj.classList.add("d-none");

		var back = document.getElementById("usis-cp-back");
		if (back) back.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(projectId));

		var idline = document.getElementById("usis-cp-project-idline");
		if (idline) idline.textContent = "Project " + projectId;

		PL.wireTable({
			tbodyId: "usis-cp-lines-tbody",
			inputClass: "usis-cp-inp",
			getMarkupPct: getMarkupPct,
			onLinePatched: function () {
				loadLines();
			},
			onReload: loadLines,
			onError: showErr,
		});

		var addBtn = document.getElementById("usis-cp-add-line");
		if (addBtn) addBtn.addEventListener("click", function () { addLine(); });

		var addSec = document.getElementById("usis-cp-add-section");
		if (addSec) addSec.addEventListener("click", promptSectionAndAdd);

		var refreshBtn = document.getElementById("usis-cp-refresh");
		if (refreshBtn) refreshBtn.addEventListener("click", loadLines);

		var markupInp = document.getElementById("usis-cp-markup-pct");
		if (markupInp) {
			markupInp.addEventListener("input", refreshUi);
			markupInp.addEventListener("change", refreshUi);
		}

		var secInp = document.getElementById("usis-cp-section-default");
		if (secInp) {
			secInp.addEventListener("change", function () {
				pendingSection = String(secInp.value || "").trim();
			});
		}

		loadLines();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
