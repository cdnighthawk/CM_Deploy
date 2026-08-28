(function () {
	"use strict";

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	function fetchJson(path, opts) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path, opts || {});
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || r.status);
				return j;
			});
		});
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function severityDot(sev) {
		if (!sev) return "—";
		if (window.USISUi && window.USISUi.severityChip) {
			return window.USISUi.severityChip(sev);
		}
		var color = { critical: "#B42318", major: "#C47B17", minor: "#1F4E5F", info: "#1F4E5F" }[String(sev).toLowerCase()] || "#5C6B76";
		return '<span title="' + esc(sev) + '" class="usis-status-dot" style="background:' + color + '"></span> ' + esc(sev);
	}

	function load() {
		var qs = new URLSearchParams();
		var pid = new URLSearchParams(location.search).get("project_id");
		if (pid) qs.set("project_id", pid);
		var st = document.getElementById("usis-sub-f-status");
		var tr = document.getElementById("usis-sub-f-trade");
		var sp = document.getElementById("usis-sub-f-spec");
		if (st && st.value) qs.set("status", st.value);
		if (tr && tr.value) qs.set("trade", tr.value);
		if (sp && sp.value) qs.set("spec_section", sp.value);
		if (document.getElementById("usis-sub-f-overdue") && document.getElementById("usis-sub-f-overdue").checked) qs.set("overdue", "1");
		if (document.getElementById("usis-sub-f-rubber") && document.getElementById("usis-sub-f-rubber").checked) qs.set("rubber_stamp", "1");
		fetchJson("/api/submittals?" + qs.toString()).then(function (body) {
			var tb = document.getElementById("usis-sub-tbody");
			if (!tb) return;
			tb.innerHTML = "";
			(body.items || []).forEach(function (row) {
				var trEl = document.createElement("tr");
				var href = "construction/submittal-detail.html?id=" + encodeURIComponent(row.projectId || "") + "&submittal=" + encodeURIComponent(row.id);
				trEl.innerHTML =
					"<td>" + esc(row.submittalNumber) + "</td><td><a href=\"" + href + "\">" + esc(row.title) + "</a></td><td>" +
					esc(row.specSection) + "</td><td>" + esc(row.trade) + "</td><td>" + esc(row.vendorName) + "</td><td>" +
					(window.USISUi ? window.USISUi.statusChip(row.status) : esc(row.status)) +
					(row.isOverdue ? (window.USISUi ? " " + window.USISUi.statusChip("Overdue") : ' <span class="badge bg-danger">Overdue</span>') : "") +
					(row.rubberStampSuspect ? (window.USISUi ? " " + window.USISUi.statusChip("Warning", { label: "Rubber" }) : ' <span class="badge bg-warning text-dark">Rubber</span>') : "") +
					"</td><td>" + esc(row.revision) + "</td><td>" + esc(row.neededByDate) + "</td><td>" +
					esc(row.reviewerName) + "</td><td>" + severityDot(row.aiMaxSeverity) + "</td><td>" +
					(row.packageComplete ? t("Yes") : t("No")) + '</td><td><a class="btn btn-link btn-sm" href="' + href + '">' + t("View") + "</a></td>";
				tb.appendChild(trEl);
			});
			if (!(body.items || []).length) {
				tb.innerHTML = '<tr><td colspan="12">' +
					(window.USISUi ? window.USISUi.emptyState({ title: t("No submittals"), body: t("Create a package to start internal QC.") }) : '<span class="text-muted">' + t("No submittals.") + "</span>") +
					"</td></tr>";
			}
		}).catch(function (e) {
			if (window.USISNotify) window.USISNotify.error(String(e.message || e));
		});
	}

	function create() {
		var err = document.getElementById("usis-sub-create-err");
		if (err) {
			err.classList.add("d-none");
			err.textContent = "";
		}
		fetchJson("/api/submittals", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: {
				project_id: document.getElementById("usis-sub-c-project").value,
				title: document.getElementById("usis-sub-c-title").value,
				spec_section: document.getElementById("usis-sub-c-spec").value,
				trade: document.getElementById("usis-sub-c-trade").value,
				needed_by_date: document.getElementById("usis-sub-c-needed").value || null,
			},
		}).then(function (body) {
			var item = body.item || {};
			location.href = "construction/submittal-detail.html?id=" + encodeURIComponent(item.projectId || item.project_id || "") + "&submittal=" + encodeURIComponent(item.id);
		}).catch(function (e) {
			if (err) {
				err.classList.remove("d-none");
				err.textContent = String(e.message || e);
			}
		});
	}

	document.addEventListener("DOMContentLoaded", function () {
		var pid = new URLSearchParams(location.search).get("project_id");
		var proj = document.getElementById("usis-sub-c-project");
		if (proj && pid) proj.value = pid;
		var logBtn = document.getElementById("usis-sub-log");
		if (logBtn) logBtn.addEventListener("click", function () {
			if (window.bootstrap) new window.bootstrap.Modal(document.getElementById("usis-sub-create-modal")).show();
		});
		var save = document.getElementById("usis-sub-c-save");
		if (save) save.addEventListener("click", create);
		var filter = document.getElementById("usis-sub-filter");
		if (filter) filter.addEventListener("click", load);
		load();
	});
})();
