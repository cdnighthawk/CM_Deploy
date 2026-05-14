/**
 * Optional hook for bid feasibility AI offcanvas (Plan 2).
 * Lead detail currently calls the API directly; this module is for shared reuse.
 */
(function (global) {
	"use strict";
	global.USISBidFeasibility = {
		post: function (leadUuid, apiBase) {
			var base = (apiBase || "").replace(/\/$/, "");
			return fetch(base + "/api/v1/lead-estimates/" + encodeURIComponent(leadUuid) + "/ai-feasibility", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				credentials: "omit",
				body: JSON.stringify({}),
			}).then(function (r) {
				return r.json();
			});
		},
	};
})(typeof window !== "undefined" ? window : this);
