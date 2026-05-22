(function () {
	"use strict";

	function postPath(hirePath) {
		var core = window.USISHireCore;
		if (!core) return Promise.reject(new Error("Hire wizard not loaded"));
		return fetch(core.apiBase() + "/api/v1/hr/me/hire-wizard/path", {
			method: "POST",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({ hire_path: hirePath }),
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
				return j;
			});
		});
	}

	function choosePath(hirePath) {
		var core = window.USISHireCore;
		postPath(hirePath)
			.then(function () {
				return core.loadWizard();
			})
			.then(function (w) {
				if (!w) return;
				window.location.replace(core.applyStepHref(core.firstAllowedStepId(w)));
			})
			.catch(function (e) {
				var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : (e.message || String(e));
				core.showErr(msg);
				if (window.USISNotify) window.USISNotify.error(msg);
			});
	}

	function init() {
		var core = window.USISHireCore;
		if (!core) return;
		core.checkSession().then(function (w) {
			if (!w) return;
			if (!w.path_selection_required) {
				window.location.replace(core.applyStepHref(core.firstAllowedStepId(w)));
			}
		});
		var yes = document.getElementById("usis-hire-path-yes");
		var no = document.getElementById("usis-hire-path-no");
		if (yes) yes.addEventListener("click", function () {
			choosePath("union_dispatch");
		});
		if (no) no.addEventListener("click", function () {
			choosePath("standard");
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
