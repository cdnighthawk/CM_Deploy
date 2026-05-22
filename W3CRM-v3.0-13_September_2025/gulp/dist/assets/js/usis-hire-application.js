(function () {
	"use strict";

	function init() {
		var core = window.USISHireCore;
		if (!core) return;
		var saveBtn = document.getElementById("usis-hire-submit-app");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				core.submitApplication().catch(function (e) {
					var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : (e.message || String(e));
					core.showErr(msg);
					if (window.USISNotify) window.USISNotify.error(msg);
				});
			});
		}
		core.checkSession().then(function (w) {
			if (w && core.applicationSaved(w)) {
				var ok = document.getElementById("usis-hire-app-saved-ok");
				if (ok) ok.classList.remove("d-none");
			}
			core.wireApplyNav({
				backHref: "../apply.html",
				onSaveNext: function () {
					core.submitApplication()
						.then(function () {
							window.location.href = core.applyStepHref("i9");
						})
						.catch(function (e) {
							var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : (e.message || String(e));
							core.showErr(msg);
							if (window.USISNotify) window.USISNotify.error(msg);
						});
				},
				nextHref: w && core.applicationSaved(w) ? core.applyStepHref("i9") : null,
			});
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
