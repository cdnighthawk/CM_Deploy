(function () {
	"use strict";

	function wireUnionDocPhotos() {
		var core = window.USISHireCore;
		if (!core || !window.USISHrUnionDocs) return;
		var wizard = core.state.wizard || {};
		var union = wizard.union || {};
		var tasks = wizard.tasks || [];
		var cardTask = tasks.filter(function (t) {
			return t.key === "union_card";
		})[0];
		var taskLocked = cardTask && cardTask.locked && cardTask.status !== "complete";
		var wrap = document.getElementById("usis-hire-workspace");
		if (!wrap) return;
		window.USISHrUnionDocs.wire(wrap, {
			locked: !!union.locked || !!taskLocked,
			apiBase: core.apiBase,
			documents: union.documents || [],
			onChange: function () {
				if (core.state.wizard && core.state.wizard.union && window.USISHrUnionDocs.getAll) {
					core.state.wizard.union.documents = window.USISHrUnionDocs.getAll();
				}
				return core.loadWizard();
			},
		});
	}

	function init() {
		var core = window.USISHireCore;
		if (!core) return;
		core.checkSession().then(function () {
			core.wireApplyNav({
				backHref: core.applyStepHref("application"),
				nextHref: core.unionComplete(core.state.wizard) ? core.applyStepHref("i9") : null,
			});
			var next = document.getElementById("usis-apply-next");
			if (next) {
				next.addEventListener("click", function (e) {
					if (!core.unionComplete(core.state.wizard)) {
						e.preventDefault();
						core.showErr("Upload union card and dispatch photos before continuing.");
					}
				});
			}
		});
	}

	window.USISHireUnion = {
		afterWizardLoad: wireUnionDocPhotos,
		init: init,
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
