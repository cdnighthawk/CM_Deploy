(function () {
	"use strict";

	var CLOSED_RFP = { awarded: 1, closed: 1, cancelled: 1, canceled: 1, void: 1 };

	function fetchJson(path) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path);
		return fetch(path, { credentials: "include", headers: { Accept: "application/json" } }).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
				return j;
			});
		});
	}

	function fill(id, value) {
		var el = document.getElementById(id);
		if (el) el.textContent = value == null ? "—" : String(value);
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function setQueue(id, html) {
		var el = document.getElementById(id);
		if (el) el.innerHTML = html;
	}

	function emptyRow(text) {
		return '<div class="list-group-item text-muted small">' + esc(text) + "</div>";
	}

	function showSecondary(body) {
		var row = document.getElementById("usis-dash-kpi-secondary");
		if (!row) return;
		var ai = Number(body.aiCritical) || 0;
		var rubber = Number(body.rubberStampSuspectThisWeek) || 0;
		var late = Number(body.poLate) || 0;
		row.classList.toggle("d-none", ai < 1 && rubber < 1 && late < 1);
	}

	function loadKpis() {
		return fetchJson("/api/v1/dashboard/ops-kpis")
			.then(function (body) {
				fill("usis-dash-open-rfps", body.openRfps);
				fill("usis-dash-qc-aging", body.qcAging);
				fill("usis-dash-ai-critical", body.aiCritical);
				fill("usis-dash-po-transit", body.poInTransit);
				fill("usis-dash-po-late", body.poLate);
				fill("usis-dash-sub-overdue", body.submittalsOverdue);
				fill("usis-dash-sub-rubber", body.rubberStampSuspectThisWeek);
				fill("usis-dash-sub-block", body.unreleasedBlockingPos);
				showSecondary(body);
				var n = Number(body.unreleasedBlockingPos) || 0;
				if (n < 1) {
					setQueue("usis-dash-queue-pos", emptyRow("Nothing is blocking buyout."));
				} else {
					setQueue(
						"usis-dash-queue-pos",
						'<a class="list-group-item list-group-item-action" href="usis-procurement.html">' +
							esc(n + " unreleased submittals are holding procurement.") +
							"</a>"
					);
				}
				return body;
			})
			.catch(function () {
				setQueue("usis-dash-queue-pos", emptyRow("Could not load blocking POs."));
			});
	}

	function loadRfps() {
		return fetchJson("/api/v1/rfps")
			.then(function (data) {
				var items = (data.items || []).filter(function (r) {
					return !CLOSED_RFP[String(r.status || "").toLowerCase()];
				});
				items = items.slice(0, 8);
				if (!items.length) {
					setQueue("usis-dash-queue-rfps", emptyRow("No open RFPs."));
					return;
				}
				setQueue(
					"usis-dash-queue-rfps",
					items
						.map(function (r) {
							var href = "usis-rfp-detail.html?id=" + encodeURIComponent(r.id);
							var label = r.title || "RFP";
							var meta = r.status ? " · " + r.status : "";
							return (
								'<a class="list-group-item list-group-item-action py-2" href="' +
								href +
								'"><span class="d-block text-truncate">' +
								esc(label) +
								'</span><span class="small text-muted">' +
								esc((r.due_at || "").slice(0, 10) + meta) +
								"</span></a>"
							);
						})
						.join("")
				);
			})
			.catch(function () {
				setQueue("usis-dash-queue-rfps", emptyRow("Could not load RFPs."));
			});
	}

	function loadSubmittals() {
		return fetchJson("/api/submittals?overdue=1")
			.then(function (data) {
				var items = (data.items || []).slice(0, 8);
				if (!items.length) {
					setQueue("usis-dash-queue-subs", emptyRow("No overdue submittals."));
					return;
				}
				setQueue(
					"usis-dash-queue-subs",
					items
						.map(function (s) {
							var href =
								"construction/submittal-detail.html?id=" + encodeURIComponent(s.id || "");
							var label = s.submittalNumber || s.title || "Submittal";
							var meta = [s.specSection, s.trade].filter(Boolean).join(" · ");
							return (
								'<a class="list-group-item list-group-item-action py-2" href="' +
								href +
								'"><span class="d-block text-truncate">' +
								esc(label) +
								(s.title && s.title !== label ? " — " + esc(s.title) : "") +
								'</span><span class="small text-muted">' +
								esc(meta || s.status || "") +
								"</span></a>"
							);
						})
						.join("")
				);
			})
			.catch(function () {
				setQueue("usis-dash-queue-subs", emptyRow("Could not load submittals."));
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		if (!document.getElementById("usis-dashboard-dark-page")) return;
		loadKpis();
		loadRfps();
		loadSubmittals();
	});
})();
