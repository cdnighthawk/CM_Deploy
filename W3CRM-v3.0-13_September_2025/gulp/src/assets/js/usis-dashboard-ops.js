(function () {
	"use strict";
	function fetchJson(path) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path);
		return fetch(path, { credentials: "include", headers: { Accept: "application/json" } }).then(function (r) {
			return r.json();
		});
	}
	function fill(id, value) {
		var el = document.getElementById(id);
		if (el) el.textContent = value == null ? "—" : String(value);
	}
	document.addEventListener("DOMContentLoaded", function () {
		fetchJson("/api/v1/dashboard/ops-kpis")
			.then(function (body) {
				fill("usis-dash-open-rfps", body.openRfps);
				fill("usis-dash-qc-aging", body.qcAging);
				fill("usis-dash-ai-critical", body.aiCritical);
				fill("usis-dash-po-transit", body.poInTransit);
				fill("usis-dash-po-late", body.poLate);
				fill("usis-dash-sub-overdue", body.submittalsOverdue);
				fill("usis-dash-sub-qc48", body.qcAging);
				fill("usis-dash-sub-rubber", body.rubberStampSuspectThisWeek);
				fill("usis-dash-sub-block", body.unreleasedBlockingPos);
			})
			.catch(function () {});
	});
})();
