(function () {
	"use strict";

	function core() {
		return window.USISHireCore;
	}

	function currentSection1() {
		var c = core();
		if (!window.USISHrI9) return c.state.section1 || {};
		var w = c.state.wizard || {};
		var i9 = w.i9 || {};
		return window.USISHrI9.mergePrefill(i9.prefill, c.state.section1 || i9.draft);
	}

	function wireI9DocPhotos(root) {
		if (!root || !window.USISHrI9Docs) return;
		var c = core();
		var i9 = (c.state.wizard && c.state.wizard.i9) || {};
		window.USISHrI9Docs.wire(root, {
			locked: !!i9.locked,
			apiBase: c.apiBase,
			documents: i9.documents || [],
			onChange: function () {
				if (c.state.wizard && c.state.wizard.i9 && window.USISHrI9Docs.getAll) {
					c.state.wizard.i9.documents = window.USISHrI9Docs.getAll();
				}
			},
		});
	}

	function updateI9Ui() {
		var c = core();
		var w = c.state.wizard || {};
		var st = w.steps || {};
		var i9 = w.i9 || {};
		var appDone = c.applicationSaved ? c.applicationSaved(w) : !!(st.application && st.application.completed) || !!(w.application && w.application.submitted_at);
		var signed = i9.status === "signed" || (st.i9 && st.i9.signed_at);
		var completed = i9.status === "completed" || i9.status === "signed" || i9.completed_at;
		var locked = c.isWizardLocked && c.isWizardLocked(w);

		var startBtn = document.getElementById("usis-i9-start-btn");
		var reviewBtn = document.getElementById("usis-i9-review-btn");
		var reviewPanel = document.getElementById("usis-i9-review-panel");
		var signedBanner = document.getElementById("usis-i9-signed-banner");
		var signBar = document.getElementById("usis-i9-sign-bar");

		if (startBtn) {
			startBtn.disabled = locked || !appDone || signed;
			startBtn.textContent = completed && !signed ? "Edit I-9 questionnaire" : "Start / continue I-9";
		}
		if (reviewBtn) reviewBtn.classList.toggle("d-none", !completed || signed);
		if (reviewPanel) reviewPanel.classList.toggle("d-none", !completed && !signed);
		if (signedBanner) {
			if (signed) {
				signedBanner.textContent =
					"I-9 Section 1 signed on " + (st.i9.signed_at || i9.signed_at || "file") + ". Section is locked.";
				signedBanner.classList.remove("d-none");
			} else {
				signedBanner.classList.add("d-none");
			}
		}
		if (signBar) signBar.classList.toggle("d-none", signed || !completed);
		if (completed && !signed && reviewPanel && !reviewPanel.classList.contains("d-none")) {
			renderReviewPanel();
		}
		if (c.renderStepPrereqBanner) c.renderStepPrereqBanner(w, "i9");
	}

	function renderReviewPanel() {
		var root = document.getElementById("usis-i9-review-root");
		if (!root || !window.USISHrI9) return;
		var c = core();
		var locked = (c.state.wizard && c.state.wizard.i9 && c.state.wizard.i9.locked) || false;
		window.USISHrI9.renderForm(root, currentSection1(), { reviewMode: true, locked: locked });
		wireI9DocPhotos(root);
	}

	function openI9Modal() {
		var root = document.getElementById("usis-i9-modal-root");
		var c = core();
		if (!root || !window.USISHrI9) {
			if (!window.USISHrI9) c.showErr("I-9 form module did not load. Hard-refresh the page.");
			return;
		}
		var i9 = (c.state.wizard && c.state.wizard.i9) || {};
		window.USISHrI9.renderForm(root, currentSection1(), { reviewMode: false, locked: !!i9.locked });
		wireI9DocPhotos(root);
		var err = document.getElementById("usis-i9-modal-err");
		if (err) {
			err.classList.add("d-none");
			err.textContent = "";
		}
		var el = document.getElementById("usis-i9-modal");
		if (el && window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(el).show();
	}

	function saveSection1(markComplete, fromReview) {
		var c = core();
		var root = fromReview ? document.getElementById("usis-i9-review-root") : document.getElementById("usis-i9-modal-root");
		if (!root || !window.USISHrI9) return Promise.reject(new Error("Form not ready"));
		var data = window.USISHrI9.collectFromForm(root);
		var v = window.USISHrI9.validate(data);
		if (!v.ok) {
			var msg = v.errors.join("; ");
			if (fromReview) c.showErr(msg);
			else {
				var errEl = document.getElementById("usis-i9-modal-err");
				if (errEl) {
					errEl.textContent = msg;
					errEl.classList.remove("d-none");
				}
			}
			return Promise.reject(new Error(msg));
		}
		c.state.section1 = data;
		return fetch(c.apiBase() + "/api/v1/hr/me/i9-section1", {
			method: "POST",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({ section1: data, mark_complete: !!markComplete }),
		}).then(function (r) {
			if (!r.ok) {
				return r.json().then(function (j) {
					var det = j.details && j.details.length ? ": " + j.details.join("; ") : "";
					throw new Error((j.error || "Save failed") + det);
				});
			}
			return r.json();
		});
	}

	var signCanvas = null;
	var signCtx = null;
	var signActive = false;

	function initSignCanvas() {
		signCanvas = document.getElementById("usis-i9-sign-canvas");
		if (!signCanvas) return;
		signCtx = signCanvas.getContext("2d");
		signCtx.strokeStyle = "#111";
		signCtx.lineWidth = 2;
		signCtx.lineCap = "round";
		function pos(e) {
			var r = signCanvas.getBoundingClientRect();
			var x = (e.clientX != null ? e.clientX : e.touches[0].clientX) - r.left;
			var y = (e.clientY != null ? e.clientY : e.touches[0].clientY) - r.top;
			return { x: x * (signCanvas.width / r.width), y: y * (signCanvas.height / r.height) };
		}
		function down(e) {
			e.preventDefault();
			signActive = true;
			core().state.signDrawing = true;
			var p = pos(e);
			signCtx.beginPath();
			signCtx.moveTo(p.x, p.y);
		}
		function move(e) {
			if (!signActive) return;
			e.preventDefault();
			var p = pos(e);
			signCtx.lineTo(p.x, p.y);
			signCtx.stroke();
		}
		function up() {
			signActive = false;
		}
		signCanvas.onmousedown = down;
		signCanvas.onmousemove = move;
		signCanvas.onmouseup = up;
		signCanvas.onmouseleave = up;
		signCanvas.ontouchstart = down;
		signCanvas.ontouchmove = move;
		signCanvas.ontouchend = up;
	}

	function clearSignCanvas() {
		if (!signCanvas || !signCtx) return;
		signCtx.clearRect(0, 0, signCanvas.width, signCanvas.height);
		core().state.signDrawing = false;
	}

	function signaturePngBase64() {
		var typed = (document.getElementById("usis-i9-sign-typed-input") || {}).value || "";
		var activeTab = document.getElementById("usis-i9-pane-draw");
		var useDraw = activeTab && activeTab.classList.contains("show") && activeTab.classList.contains("active");
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
		if (signCanvas) return signCanvas.toDataURL("image/png");
		return "";
	}

	function submitI9Sign() {
		var c = core();
		var errEl = document.getElementById("usis-i9-sign-err");
		if (errEl) {
			errEl.classList.add("d-none");
			errEl.textContent = "";
		}
		var cert = document.getElementById("usis-i9-sign-cert");
		var nameEl = document.getElementById("usis-i9-sign-fullname");
		if (!cert || !cert.checked) {
			if (errEl) {
				errEl.textContent = "Check the certification box to continue.";
				errEl.classList.remove("d-none");
			}
			return;
		}
		var png = signaturePngBase64();
		if (!png || png.length < 100) {
			if (errEl) {
				errEl.textContent = "Draw or type your signature first.";
				errEl.classList.remove("d-none");
			}
			return;
		}
		fetch(c.apiBase() + "/api/v1/hr/me/i9-section1/sign", {
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
				return r.json();
			})
			.then(function () {
				var modal = document.getElementById("usis-i9-sign-modal");
				if (modal && window.bootstrap && window.bootstrap.Modal) {
					var inst = window.bootstrap.Modal.getInstance(modal);
					if (inst) inst.hide();
				}
				if (window.USISNotify) window.USISNotify.success("I-9 signed.");
				return c.loadWizard().then(function () {
					if (c.i9Complete(c.state.wizard)) window.location.href = "w4.html";
				});
			})
			.catch(function (e) {
				if (errEl) {
					errEl.textContent = e.message || String(e);
					errEl.classList.remove("d-none");
				}
				c.showErr(e.message || String(e));
			});
	}

	function wireEvents() {
		var c = core();
		var startI9 = document.getElementById("usis-i9-start-btn");
		if (startI9) startI9.addEventListener("click", openI9Modal);
		var reviewBtn = document.getElementById("usis-i9-review-btn");
		if (reviewBtn) {
			reviewBtn.addEventListener("click", function () {
				var panel = document.getElementById("usis-i9-review-panel");
				if (panel) panel.classList.remove("d-none");
				renderReviewPanel();
			});
		}
		var editBtn = document.getElementById("usis-i9-edit-btn");
		if (editBtn) editBtn.addEventListener("click", openI9Modal);
		var saveReview = document.getElementById("usis-i9-save-review-btn");
		if (saveReview) {
			saveReview.addEventListener("click", function () {
				saveSection1(true, true)
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("I-9 saved.");
						return c.loadWizard();
					})
					.catch(function () {});
			});
		}
		var completeBtn = document.getElementById("usis-i9-modal-complete");
		if (completeBtn) {
			completeBtn.addEventListener("click", function () {
				saveSection1(true, false)
					.then(function () {
						var modal = document.getElementById("usis-i9-modal");
						if (modal && window.bootstrap && window.bootstrap.Modal) {
							var inst = window.bootstrap.Modal.getInstance(modal);
							if (inst) inst.hide();
						}
						if (window.USISNotify) window.USISNotify.success("Section 1 complete — review and sign.");
						return c.loadWizard().then(function () {
							var panel = document.getElementById("usis-i9-review-panel");
							if (panel) panel.classList.remove("d-none");
							renderReviewPanel();
						});
					})
					.catch(function () {});
			});
		}
		var openSign = document.getElementById("usis-i9-open-sign-btn");
		if (openSign) {
			openSign.addEventListener("click", function () {
				clearSignCanvas();
				var u = (c.state.wizard && c.state.wizard.user) || {};
				var nm = [u.first_name, u.last_name].filter(Boolean).join(" ");
				var nameEl = document.getElementById("usis-i9-sign-fullname");
				if (nameEl && !nameEl.value) nameEl.value = nm;
				var el = document.getElementById("usis-i9-sign-modal");
				if (el && window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(el).show();
			});
		}
		var signSubmit = document.getElementById("usis-i9-sign-submit");
		if (signSubmit) signSubmit.addEventListener("click", submitI9Sign);
		var signClear = document.getElementById("usis-i9-sign-clear");
		if (signClear) signClear.addEventListener("click", clearSignCanvas);
		var typedIn = document.getElementById("usis-i9-sign-typed-input");
		var typedPrev = document.getElementById("usis-i9-sign-typed-preview");
		if (typedIn && typedPrev) typedIn.addEventListener("input", function () { typedPrev.textContent = typedIn.value; });
		initSignCanvas();
	}

	function init() {
		var c = core();
		if (!c) return;
		wireEvents();
		c.checkSession().then(function () {
			c.wireApplyNav({
				backHref: "union.html",
				nextHref: c.i9Complete(c.state.wizard) ? "w4.html" : null,
			});
		});
	}

	window.USISHireI9 = {
		afterWizardLoad: updateI9Ui,
		init: init,
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
