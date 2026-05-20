(function () {
	"use strict";

	function init() {
		var core = window.USISHireCore;
		if (!core) return;
		var saveBtn = document.getElementById("usis-hire-submit-app");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				core.submitApplication().catch(function (e) {
					core.showErr(e.message || String(e));
					if (window.USISNotify) window.USISNotify.error(e.message || String(e));
				});
			});
		}
		core.checkSession().then(function () {
			core.wireApplyNav({
				backHref: "../apply.html",
				onSaveNext: function () {
					core.submitApplication()
						.then(function () {
							window.location.href = "union.html";
						})
						.catch(function (e) {
							core.showErr(e.message || String(e));
							if (window.USISNotify) window.USISNotify.error(e.message || String(e));
						});
				},
				nextHref: core.applicationComplete(core.state.wizard) ? "union.html" : null,
			});
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
