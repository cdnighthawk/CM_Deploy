(function () {
	"use strict";
	function fetchJson(path) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path);
		return fetch(path, { credentials: "include", headers: { Accept: "application/json" } }).then(function (r) {
			return r.json();
		});
	}
	document.addEventListener("DOMContentLoaded", function () {
		fetchJson("/api/submittals/dashboard-summary")
			.then(function (body) {
				var map = {
					"usis-dash-sub-overdue": body.overdue,
					"usis-dash-sub-qc48": body.inQcOver48h,
					"usis-dash-sub-rubber": body.rubberStampSuspectThisWeek,
					"usis-dash-sub-block": body.unreleasedBlockingPos,
				};
				Object.keys(map).forEach(function (id) {
					var el = document.getElementById(id);
					if (el) el.textContent = map[id] == null ? "—" : String(map[id]);
				});
			})
			.catch(function () {});
	});
})();
