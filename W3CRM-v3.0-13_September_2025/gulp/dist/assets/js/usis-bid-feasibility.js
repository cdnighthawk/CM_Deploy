/**
 * Optional hook for bid feasibility AI offcanvas (Plan 2).
 * Lead detail currently calls the API directly; this module is for shared reuse.
 */
(function (global) {
	"use strict";
	global.USISBidFeasibility = {
		post: function (leadUuid, apiBase) {
			var base = (apiBase || window.USIS_API.apiBase()).replace(/\/$/, "");
			return fetch(base + "/api/v1/lead-estimates/" + encodeURIComponent(leadUuid) + "/ai-feasibility", {
				method: "POST",
				headers: Object.assign(
					{ "Content-Type": "application/json", Accept: "application/json" },
					window.USIS_API.actorHeaders()
				),
				credentials: "include",
				body: JSON.stringify({}),
			}).then(function (r) {
				return r.json();
			});
		},
	};
})(typeof window !== "undefined" ? window : this);
