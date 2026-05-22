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
			var nextStep = w ? core.nextStepAfterApplication(w) : "i9";
			var savedMsg = document.getElementById("usis-hire-app-saved-ok");
			if (savedMsg && w && core.isStandardPath(w)) {
				savedMsg.textContent =
					"Application saved — HR will review your submission. Watch your email for a job offer, or return here to check status.";
			}
			core.wireApplyNav({
				backHref: "../apply.html",
				onSaveNext: function () {
					core.submitApplication()
						.then(function (nw) {
							window.location.href = core.applyStepHref(nw ? core.nextStepAfterApplication(nw) : nextStep);
						})
						.catch(function (e) {
							var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : (e.message || String(e));
							core.showErr(msg);
							if (window.USISNotify) window.USISNotify.error(msg);
						});
				},
				nextHref: w && core.applicationSaved(w) ? core.applyStepHref(nextStep) : null,
			});
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
