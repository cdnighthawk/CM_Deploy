(function () {
	"use strict";

	function init() {
		var core = window.USISHireCore;
		if (!core) return;

		core.checkSession().then(function (w) {
			if (!w) return;
			core.renderStepPrereqBanner(w, "offer");
			if (!core.canAccessStep("offer", w)) {
				core.redirectToStep(core.firstAllowedStepId(w));
				return;
			}

			var workspace = document.getElementById("usis-hire-offer-workspace");
			var frame = document.getElementById("usis-hire-offer-frame");
			var acceptBtn = document.getElementById("usis-hire-offer-accept");
			var acceptedBanner = document.getElementById("usis-hire-offer-accepted");
			var i9Link = document.getElementById("usis-hire-offer-i9");
			var offer = w.offer || {};
			var accepted = !!offer.accepted_at;

			if (workspace) workspace.classList.remove("d-none");
			if (frame) frame.src = core.apiBase() + "/api/v1/hr/me/job-offer/preview";
			if (acceptedBanner) acceptedBanner.classList.toggle("d-none", !accepted);
			if (acceptBtn) acceptBtn.classList.toggle("d-none", accepted);
			if (i9Link) i9Link.classList.toggle("d-none", !accepted);

			if (acceptBtn && !acceptBtn._wired) {
				acceptBtn._wired = true;
				acceptBtn.addEventListener("click", function () {
					acceptBtn.disabled = true;
					fetch(core.apiBase() + "/api/v1/hr/me/job-offer/accept", {
						method: "POST",
						credentials: "include",
						headers: { Accept: "application/json" },
					})
						.then(function (r) {
							return r.json().then(function (j) {
								if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
								return j;
							});
						})
						.then(function () {
							if (window.USISNotify) window.USISNotify.success("Job offer accepted.");
							return core.loadWizard();
						})
						.then(function (nw) {
							if (!nw) return;
							window.location.href = core.applyStepHref("i9");
						})
						.catch(function (e) {
							acceptBtn.disabled = false;
							var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : (e.message || String(e));
							core.showErr(msg);
							if (window.USISNotify) window.USISNotify.error(msg);
						});
				});
			}
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
