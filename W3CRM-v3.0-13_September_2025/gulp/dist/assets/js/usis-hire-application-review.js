(function () {
	"use strict";

	var reviewI9Data = null;
	var reviewW4Data = null;
	var i9Canvas = null;
	var i9Ctx = null;
	var w4Canvas = null;
	var w4Ctx = null;

	function core() {
		return window.USISHireCore;
	}

	function showReviewErr(msg) {
		var el = document.getElementById("usis-hire-review-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function canSignForms(w) {
		var c = core();
		if (c.isWizardLocked && c.isWizardLocked(w)) return false;
		if (c.isUnionPath && c.isUnionPath(w)) return !!(w.application && w.application.submitted_at);
		if (c.isStandardPath && c.isStandardPath(w)) return c.offerAccepted(w);
		return false;
	}

	function formsSigned(w) {
		var c = core();
		return c.i9Complete(w) && c.w4Complete(w);
	}

	function canOpenReviewModal(w) {
		var c = core();
		if (c.isWizardLocked && c.isWizardLocked(w)) return false;
		if (c.isUnionPath && c.isUnionPath(w)) return c.applicationSaved(w);
		if (c.isStandardPath && c.isStandardPath(w)) return c.offerAccepted(w) || formsSigned(w);
		return false;
	}

	function updateSignedBanner(w) {
		var ok = document.getElementById("usis-hire-forms-signed-ok");
		var reviewBtn = document.getElementById("usis-hire-review-sign-btn");
		var taxNote = document.getElementById("usis-hire-tax-later-note");
		if (ok) ok.classList.toggle("d-none", !formsSigned(w));
		if (taxNote) {
			taxNote.textContent =
				w && core().isStandardPath(w)
					? "Social Security number, date of birth, citizenship status, and tax withholding are collected on Form I-9 and Form W-4 after you accept a job offer."
					: "Social Security number, date of birth, citizenship status, and tax withholding are collected on Form I-9 and Form W-4 in the next steps — not on this employment application.";
		}
		if (reviewBtn) {
			reviewBtn.classList.toggle("d-none", !canOpenReviewModal(w));
			reviewBtn.disabled = !!(w && (w.review || {}).wizard_locked);
			if (formsSigned(w)) reviewBtn.textContent = "Review signed forms";
			else reviewBtn.textContent = "Review and Sign";
		}
	}

	function currentI9(w) {
		w = w || (core().state.wizard || {});
		if (!window.USISHrI9) return reviewI9Data || {};
		return window.USISHrI9.mergePrefill((w.i9 && w.i9.prefill) || {}, reviewI9Data || (w.i9 && w.i9.draft) || {});
	}

	function currentW4(w) {
		w = w || (core().state.wizard || {});
		if (!window.USISHrW4) return reviewW4Data || {};
		return window.USISHrW4.mergePrefill((w.w4 && w.w4.prefill) || {}, reviewW4Data || (w.w4 && w.w4.draft) || {});
	}

	function renderI9Tab(w) {
		var root = document.getElementById("usis-hire-review-i9-root");
		if (!root || !window.USISHrI9) return;
		var i9 = (w && w.i9) || {};
		window.USISHrI9.renderForm(root, currentI9(w), { reviewMode: false, locked: !!i9.locked });
		if (window.USISHrI9.wireConditionals) window.USISHrI9.wireConditionals(root);
		if (window.USISHrI9Docs) {
			window.USISHrI9Docs.wire(root, {
				locked: !!i9.locked,
				apiBase: core().apiBase,
				documents: i9.documents || [],
			});
		}
	}

	function renderW4Tab(w) {
		var root = document.getElementById("usis-hire-review-w4-root");
		if (!root || !window.USISHrW4) return;
		var w4 = (w && w.w4) || {};
		window.USISHrW4.renderForm(root, currentW4(w), { reviewMode: false, locked: !!w4.locked });
		if (window.USISHrW4Docs) {
			window.USISHrW4Docs.wire(root, {
				locked: !!w4.locked,
				apiBase: core().apiBase,
				documents: w4.documents || [],
			});
		}
	}

	function renderSummaryTab(w) {
		var dl = document.getElementById("usis-hire-review-summary-dl");
		if (!dl || !window.USISHireFormMappings) return;
		var payload = (w.application && w.application.payload) || core().gatherApplicationPayload();
		window.USISHireFormMappings.renderSummary(dl, payload, w.user || {});
	}

	function renderSignStatus(w) {
		var root = document.getElementById("usis-hire-review-sign-status");
		if (!root) return;
		var c = core();
		var i9Done = c.i9Complete(w);
		var w4Done = c.w4Complete(w);
		var eligible = canSignForms(w);
		var html =
			'<div class="list-group list-group-flush border rounded">' +
			'<div class="list-group-item d-flex justify-content-between"><span>Form I-9</span><span class="' +
			(i9Done ? "text-success" : "text-muted") +
			'">' +
			(i9Done ? "Signed" : "Not signed") +
			"</span></div>" +
			'<div class="list-group-item d-flex justify-content-between"><span>Form W-4</span><span class="' +
			(w4Done ? "text-success" : "text-muted") +
			'">' +
			(w4Done ? "Signed" : "Not signed") +
			"</span></div></div>";
		if (!eligible && !formsSigned(w)) {
			html +=
				'<p class="text-muted small mt-2 mb-0">On the standard hire path, Form I-9 and W-4 signing unlock after you accept your job offer. You can still review and save prefilled forms here.</p>';
		}
		root.innerHTML = html;
		var i9Btn = document.getElementById("usis-hire-review-sign-i9-btn");
		var w4Btn = document.getElementById("usis-hire-review-sign-w4-btn");
		if (i9Btn) i9Btn.disabled = !eligible || i9Done;
		if (w4Btn) w4Btn.disabled = !eligible || w4Done || !i9Done;
	}

	function collectReviewForms() {
		var i9Root = document.getElementById("usis-hire-review-i9-root");
		var w4Root = document.getElementById("usis-hire-review-w4-root");
		if (window.USISHrI9 && i9Root) reviewI9Data = window.USISHrI9.collectFromForm(i9Root);
		if (window.USISHrW4 && w4Root) reviewW4Data = window.USISHrW4.collectFromForm(w4Root);
	}

	function saveReviewForms() {
		showReviewErr("");
		collectReviewForms();
		var c = core();
		var i9Val = window.USISHrI9 ? window.USISHrI9.validate(reviewI9Data) : { ok: true };
		var w4Val = window.USISHrW4 ? window.USISHrW4.validate(reviewW4Data) : { ok: true };
		if (!i9Val.ok) {
			showReviewErr("Form I-9: " + (i9Val.errors || []).join("; "));
			return Promise.reject(new Error("I-9 validation failed"));
		}
		if (!w4Val.ok) {
			showReviewErr("Form W-4: " + (w4Val.errors || []).join("; "));
			return Promise.reject(new Error("W-4 validation failed"));
		}
		return fetch(c.apiBase() + "/api/v1/hr/me/i9-section1", {
			method: "POST",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({ section1: reviewI9Data, mark_complete: true }),
		})
			.then(function (r) {
				if (r.status === 403) {
					return r.json().then(function (j) {
						throw new Error(j.message || j.error || "I-9 save not available yet");
					});
				}
				if (!r.ok) {
					return r.json().then(function (j) {
						throw new Error((j.details && j.details.join("; ")) || j.error || "I-9 save failed");
					});
				}
				return fetch(c.apiBase() + "/api/v1/hr/me/w4", {
					method: "POST",
					credentials: "include",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: JSON.stringify({ w4: reviewW4Data, mark_complete: true }),
				});
			})
			.then(function (r) {
				if (r.status === 403) {
					return r.json().then(function (j) {
						throw new Error(j.message || j.error || "W-4 save not available yet");
					});
				}
				if (!r.ok) {
					return r.json().then(function (j) {
						throw new Error((j.details && j.details.join("; ")) || j.error || "W-4 save failed");
					});
				}
				if (window.USISNotify) window.USISNotify.success("Form I-9 and W-4 saved.");
				return c.loadWizard();
			})
			.then(function (w) {
				renderAllTabs(w);
				updateSignedBanner(w);
			});
	}

	function renderAllTabs(w) {
		renderSummaryTab(w);
		renderI9Tab(w);
		renderW4Tab(w);
		renderSignStatus(w);
	}

	function openReviewModal() {
		var c = core();
		showReviewErr("");
		return c
			.submitApplication()
			.then(function (w) {
				reviewI9Data = null;
				reviewW4Data = null;
				renderAllTabs(w);
				var modal = document.getElementById("usis-hire-review-sign-modal");
				if (modal && window.bootstrap && window.bootstrap.Modal) {
					window.bootstrap.Modal.getOrCreateInstance(modal).show();
				}
				updateSignedBanner(w);
				return w;
			});
	}

	function wireSignatureCanvas(canvas, ctxHolder) {
		if (!canvas) return;
		var ctx = canvas.getContext("2d");
		ctx.strokeStyle = "#111";
		ctx.lineWidth = 2;
		ctx.lineCap = "round";
		var active = false;
		function pos(e) {
			var r = canvas.getBoundingClientRect();
			var x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
			var y = (e.touches ? e.touches[0].clientY : e.clientY) - r.top;
			return { x: x * (canvas.width / r.width), y: y * (canvas.height / r.height) };
		}
		function down(e) {
			e.preventDefault();
			active = true;
			var p = pos(e);
			ctx.beginPath();
			ctx.moveTo(p.x, p.y);
		}
		function move(e) {
			if (!active) return;
			e.preventDefault();
			var p = pos(e);
			ctx.lineTo(p.x, p.y);
			ctx.stroke();
		}
		function up() {
			active = false;
		}
		canvas.onmousedown = down;
		canvas.onmousemove = move;
		canvas.onmouseup = up;
		canvas.onmouseleave = up;
		canvas.ontouchstart = down;
		canvas.ontouchmove = move;
		canvas.ontouchend = up;
		ctxHolder.ctx = ctx;
		ctxHolder.canvas = canvas;
	}

	function signaturePng(canvas, typedInputId, drawPaneId) {
		var typed = (document.getElementById(typedInputId) || {}).value || "";
		var drawPane = document.getElementById(drawPaneId);
		var useDraw = drawPane && drawPane.classList.contains("show") && drawPane.classList.contains("active");
		if (!useDraw && typed.trim()) {
			var c = document.createElement("canvas");
			c.width = 640;
			c.height = 160;
			var cx = c.getContext("2d");
			cx.fillStyle = "#fff";
			cx.fillRect(0, 0, c.width, c.height);
			cx.fillStyle = "#111";
			cx.font = '48px "Segoe Script", "Brush Script MT", cursive';
			cx.fillText(typed.trim(), 24, 100);
			return c.toDataURL("image/png");
		}
		if (canvas) return canvas.toDataURL("image/png");
		return "";
	}

	function submitSign(kind) {
		var c = core();
		var isI9 = kind === "i9";
		var cert = document.getElementById(isI9 ? "usis-hire-review-i9-cert" : "usis-hire-review-w4-cert");
		var nameEl = document.getElementById(isI9 ? "usis-hire-review-i9-fullname" : "usis-hire-review-w4-fullname");
		var errEl = document.getElementById("usis-hire-review-sign-err");
		if (errEl) errEl.classList.add("d-none");
		if (!cert || !cert.checked) {
			if (errEl) {
				errEl.textContent = "Check the certification box to continue.";
				errEl.classList.remove("d-none");
			}
			return;
		}
		var png = signaturePng(
			isI9 ? i9Canvas : w4Canvas,
			isI9 ? "usis-hire-review-i9-typed" : "usis-hire-review-w4-typed",
			isI9 ? "usis-hire-review-i9-draw" : "usis-hire-review-w4-draw"
		);
		if (!png || png.length < 100) {
			if (errEl) {
				errEl.textContent = "Draw or type your signature first.";
				errEl.classList.remove("d-none");
			}
			return;
		}
		var url = isI9 ? "/api/v1/hr/me/i9-section1/sign" : "/api/v1/hr/me/w4/sign";
		fetch(c.apiBase() + url, {
			method: "POST",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({
				certify: true,
				typed_full_name: nameEl ? nameEl.value.trim() : "",
				signature_png_base64: png,
			}),
		})
			.then(function (r) {
				if (!r.ok) {
					return r.json().then(function (j) {
						throw new Error(j.error || "Sign failed");
					});
				}
				return c.loadWizard();
			})
			.then(function (w) {
				if (window.USISNotify) window.USISNotify.success(isI9 ? "Form I-9 signed." : "Form W-4 signed.");
				var modalId = isI9 ? "usis-hire-review-i9-sign-modal" : "usis-hire-review-w4-sign-modal";
				var modal = document.getElementById(modalId);
				if (modal && window.bootstrap && window.bootstrap.Modal) {
					var inst = window.bootstrap.Modal.getInstance(modal);
					if (inst) inst.hide();
				}
				renderAllTabs(w);
				updateSignedBanner(w);
			})
			.catch(function (e) {
				if (errEl) {
					errEl.textContent = e.message || String(e);
					errEl.classList.remove("d-none");
				}
			});
	}

	function init() {
		i9Canvas = document.getElementById("usis-hire-review-i9-canvas");
		w4Canvas = document.getElementById("usis-hire-review-w4-canvas");
		wireSignatureCanvas(i9Canvas, { canvas: i9Canvas, ctx: i9Ctx });
		wireSignatureCanvas(w4Canvas, { canvas: w4Canvas, ctx: w4Ctx });

		var reviewBtn = document.getElementById("usis-hire-review-sign-btn");
		if (reviewBtn) {
			reviewBtn.addEventListener("click", function () {
				var c = core();
				var msg = c.validateApplicationForm();
				if (msg) {
					c.showErr(msg);
					if (window.USISNotify) window.USISNotify.error(msg);
					return;
				}
				openReviewModal().catch(function (e) {
					var text = c.friendlyFetchError ? c.friendlyFetchError(e) : e.message || String(e);
					c.showErr(text);
					if (window.USISNotify) window.USISNotify.error(text);
				});
			});
		}

		var saveBtn = document.getElementById("usis-hire-review-save-forms");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				saveReviewForms().catch(function (e) {
					showReviewErr(e.message || String(e));
				});
			});
		}

		var signI9 = document.getElementById("usis-hire-review-sign-i9-btn");
		if (signI9) {
			signI9.addEventListener("click", function () {
				var modal = document.getElementById("usis-hire-review-i9-sign-modal");
				var fn = document.getElementById("usis-hire-review-i9-fullname");
				var sigName = document.getElementById("usis-hire-sig-name");
				if (fn && sigName && sigName.value) fn.value = sigName.value;
				if (modal && window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(modal).show();
			});
		}
		var signW4 = document.getElementById("usis-hire-review-sign-w4-btn");
		if (signW4) {
			signW4.addEventListener("click", function () {
				var modal = document.getElementById("usis-hire-review-w4-sign-modal");
				var fn = document.getElementById("usis-hire-review-w4-fullname");
				var sigName = document.getElementById("usis-hire-sig-name");
				if (fn && sigName && sigName.value) fn.value = sigName.value;
				if (modal && window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(modal).show();
			});
		}

		var i9Submit = document.getElementById("usis-hire-review-i9-sign-submit");
		if (i9Submit) i9Submit.addEventListener("click", function () {
			submitSign("i9");
		});
		var w4Submit = document.getElementById("usis-hire-review-w4-sign-submit");
		if (w4Submit) w4Submit.addEventListener("click", function () {
			submitSign("w4");
		});

		var i9Clear = document.getElementById("usis-hire-review-i9-clear");
		if (i9Clear && i9Canvas) {
			i9Clear.addEventListener("click", function () {
				var ctx = i9Canvas.getContext("2d");
				ctx.clearRect(0, 0, i9Canvas.width, i9Canvas.height);
			});
		}
		var w4Clear = document.getElementById("usis-hire-review-w4-clear");
		if (w4Clear && w4Canvas) {
			w4Clear.addEventListener("click", function () {
				var ctx = w4Canvas.getContext("2d");
				ctx.clearRect(0, 0, w4Canvas.width, w4Canvas.height);
			});
		}
	}

	window.USISHireApplicationReview = {
		afterWizardLoad: updateSignedBanner,
		openReviewModal: openReviewModal,
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
