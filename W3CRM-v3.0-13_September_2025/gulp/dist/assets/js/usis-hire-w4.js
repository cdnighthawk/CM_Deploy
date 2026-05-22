(function () {
	"use strict";

	var w4ReviewOpened = false;

	function core() {
		return window.USISHireCore;
	}

	function currentW4() {
		var c = core();
		if (!window.USISHrW4) return c.state.w4Data || {};
		var w = c.state.wizard || {};
		var w4 = w.w4 || {};
		return window.USISHrW4.mergePrefill(w4.prefill, c.state.w4Data || w4.draft);
	}

	function wireW4DocPhotos(root) {
		if (!root || !window.USISHrW4Docs) return;
		var c = core();
		var w4 = (c.state.wizard && c.state.wizard.w4) || {};
		window.USISHrW4Docs.wire(root, {
			locked: !!w4.locked,
			apiBase: c.apiBase,
			documents: w4.documents || [],
			onChange: function () {
				if (c.state.wizard && c.state.wizard.w4 && window.USISHrW4Docs.getAll) {
					c.state.wizard.w4.documents = window.USISHrW4Docs.getAll();
				}
			},
		});
	}

	function updateW4Ui() {
		var c = core();
		var w = c.state.wizard || {};
		var st = w.steps || {};
		var w4 = w.w4 || {};
		var i9 = w.i9 || {};
		var i9Signed = i9.status === "signed" || (st.i9 && st.i9.signed_at);
		var signed = w4.status === "signed" || (st.w4 && st.w4.signed_at);
		var completed = w4.status === "completed" || w4.status === "signed" || w4.completed_at;
		var locked = c.isWizardLocked && c.isWizardLocked(w);

		var startBtn = document.getElementById("usis-w4-start-btn");
		var reviewBtn = document.getElementById("usis-w4-review-btn");
		var reviewPanel = document.getElementById("usis-w4-review-panel");
		var signedBanner = document.getElementById("usis-w4-signed-banner");
		var readyBanner = document.getElementById("usis-w4-ready-banner");
		var signBar = document.getElementById("usis-w4-sign-bar");

		if (startBtn) {
			startBtn.disabled = locked || !i9Signed || signed;
			startBtn.textContent = completed && !signed ? "Edit W-4 questionnaire" : "Start / continue W-4";
		}
		if (reviewBtn) {
			reviewBtn.classList.toggle("d-none", !completed || signed);
			reviewBtn.textContent = w4ReviewOpened && !signed ? "Review W-4 again" : "Review W-4";
		}
		if (reviewPanel) {
			reviewPanel.classList.toggle("d-none", signed ? false : !w4ReviewOpened);
		}
		if (readyBanner) {
			readyBanner.classList.toggle("d-none", !completed || signed || w4ReviewOpened);
		}
		if (signedBanner) {
			if (signed) {
				signedBanner.textContent =
					"Form W-4 signed on " + (st.w4.signed_at || w4.signed_at || "file") + ". Section is locked.";
				signedBanner.classList.remove("d-none");
			} else {
				signedBanner.classList.add("d-none");
			}
		}
		if (signBar) signBar.classList.toggle("d-none", signed || !completed || !w4ReviewOpened);
		if ((w4ReviewOpened && !signed) || signed) {
			renderW4ReviewPanel();
		}
		if (c.renderStepPrereqBanner) c.renderStepPrereqBanner(w, "w4");
	}

	function renderW4ReviewPanel() {
		var root = document.getElementById("usis-w4-review-root");
		if (!root || !window.USISHrW4) return;
		var c = core();
		var w = c.state.wizard || {};
		var w4 = w.w4 || {};
		var st = w.steps || {};
		var signed = w4.status === "signed" || (st.w4 && st.w4.signed_at);
		var render = window.USISHrW4.renderFilledReview || window.USISHrW4.renderForm;
		render.call(window.USISHrW4, root, currentW4(), {
			reviewMode: true,
			locked: true,
			signature_png: signed ? w4.signature_png : null,
			signed_at: st.w4 && st.w4.signed_at ? st.w4.signed_at : w4.signed_at,
		});
		wireW4DocPhotos(root);
	}

	function openW4Review() {
		w4ReviewOpened = true;
		var panel = document.getElementById("usis-w4-review-panel");
		if (panel) panel.classList.remove("d-none");
		renderW4ReviewPanel();
		updateW4Ui();
		if (panel && panel.scrollIntoView) panel.scrollIntoView({ behavior: "smooth", block: "start" });
	}

	function openW4Modal() {
		var root = document.getElementById("usis-w4-modal-root");
		var c = core();
		if (!root || !window.USISHrW4) {
			if (!window.USISHrW4) c.showErr("W-4 form module did not load. Hard-refresh the page.");
			return;
		}
		var w4 = (c.state.wizard && c.state.wizard.w4) || {};
		window.USISHrW4.renderForm(root, currentW4(), { reviewMode: false, locked: !!w4.locked });
		wireW4DocPhotos(root);
		var err = document.getElementById("usis-w4-modal-err");
		if (err) {
			err.classList.add("d-none");
			err.textContent = "";
		}
		var el = document.getElementById("usis-w4-modal");
		if (el && window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(el).show();
	}

	function saveW4(markComplete, fromReview) {
		var c = core();
		var root = fromReview ? document.getElementById("usis-w4-review-root") : document.getElementById("usis-w4-modal-root");
		if (!root || !window.USISHrW4) return Promise.reject(new Error("Form not ready"));
		var data = window.USISHrW4.collectFromForm(root);
		var v = window.USISHrW4.validate(data);
		if (!v.ok) {
			var msg = v.errors.join("; ");
			if (fromReview) c.showErr(msg);
			else {
				var errEl = document.getElementById("usis-w4-modal-err");
				if (errEl) {
					errEl.textContent = msg;
					errEl.classList.remove("d-none");
				}
			}
			return Promise.reject(new Error(msg));
		}
		c.state.w4Data = data;
		return fetch(c.apiBase() + "/api/v1/hr/me/w4", {
			method: "POST",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({ w4: data, mark_complete: !!markComplete }),
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

	var w4SignCanvas = null;
	var w4SignCtx = null;
	var w4SignActive = false;

	function initW4SignCanvas() {
		w4SignCanvas = document.getElementById("usis-w4-sign-canvas");
		if (!w4SignCanvas) return;
		w4SignCtx = w4SignCanvas.getContext("2d");
		w4SignCtx.strokeStyle = "#111";
		w4SignCtx.lineWidth = 2;
		w4SignCtx.lineCap = "round";
		function pos(e) {
			var r = w4SignCanvas.getBoundingClientRect();
			var x = (e.clientX != null ? e.clientX : e.touches[0].clientX) - r.left;
			var y = (e.clientY != null ? e.clientY : e.touches[0].clientY) - r.top;
			return { x: x * (w4SignCanvas.width / r.width), y: y * (w4SignCanvas.height / r.height) };
		}
		function down(e) {
			e.preventDefault();
			w4SignActive = true;
			core().state.w4SignDrawing = true;
			var p = pos(e);
			w4SignCtx.beginPath();
			w4SignCtx.moveTo(p.x, p.y);
		}
		function move(e) {
			if (!w4SignActive) return;
			e.preventDefault();
			var p = pos(e);
			w4SignCtx.lineTo(p.x, p.y);
			w4SignCtx.stroke();
		}
		function up() {
			w4SignActive = false;
		}
		w4SignCanvas.onmousedown = down;
		w4SignCanvas.onmousemove = move;
		w4SignCanvas.onmouseup = up;
		w4SignCanvas.onmouseleave = up;
		w4SignCanvas.ontouchstart = down;
		w4SignCanvas.ontouchmove = move;
		w4SignCanvas.ontouchend = up;
	}

	function clearW4SignCanvas() {
		if (!w4SignCanvas || !w4SignCtx) return;
		w4SignCtx.clearRect(0, 0, w4SignCanvas.width, w4SignCanvas.height);
		core().state.w4SignDrawing = false;
	}

	function w4SignaturePngBase64() {
		var typed = (document.getElementById("usis-w4-sign-typed-input") || {}).value || "";
		var activeTab = document.getElementById("usis-w4-pane-draw");
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
		if (w4SignCanvas) return w4SignCanvas.toDataURL("image/png");
		return "";
	}

	function submitW4Sign() {
		var c = core();
		var errEl = document.getElementById("usis-w4-sign-err");
		if (errEl) {
			errEl.classList.add("d-none");
			errEl.textContent = "";
		}
		var cert = document.getElementById("usis-w4-sign-cert");
		var nameEl = document.getElementById("usis-w4-sign-fullname");
		if (!cert || !cert.checked) {
			if (errEl) {
				errEl.textContent = "Check the certification box to continue.";
				errEl.classList.remove("d-none");
			}
			return;
		}
		var png = w4SignaturePngBase64();
		if (!png || png.length < 100) {
			if (errEl) {
				errEl.textContent = "Draw or type your signature first.";
				errEl.classList.remove("d-none");
			}
			return;
		}
		fetch(c.apiBase() + "/api/v1/hr/me/w4/sign", {
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
				var modal = document.getElementById("usis-w4-sign-modal");
				if (modal && window.bootstrap && window.bootstrap.Modal) {
					var inst = window.bootstrap.Modal.getInstance(modal);
					if (inst) inst.hide();
				}
				if (window.USISNotify) window.USISNotify.success("W-4 signed.");
				return c.loadWizard().then(function () {
					window.location.href = c.applyStepHref("union");
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
		var startW4 = document.getElementById("usis-w4-start-btn");
		if (startW4) startW4.addEventListener("click", openW4Modal);
		var reviewW4 = document.getElementById("usis-w4-review-btn");
		if (reviewW4) reviewW4.addEventListener("click", openW4Review);
		var editW4 = document.getElementById("usis-w4-edit-btn");
		if (editW4) editW4.addEventListener("click", openW4Modal);
		var completeW4 = document.getElementById("usis-w4-modal-complete");
		if (completeW4) {
			completeW4.addEventListener("click", function () {
				saveW4(true, false)
					.then(function () {
						var modal = document.getElementById("usis-w4-modal");
						if (modal && window.bootstrap && window.bootstrap.Modal) {
							var inst = window.bootstrap.Modal.getInstance(modal);
							if (inst) inst.hide();
						}
						w4ReviewOpened = false;
						if (window.USISNotify) window.USISNotify.success("W-4 saved — review your answers, then sign.");
						return c.loadWizard().then(function () {
							updateW4Ui();
						});
					})
					.catch(function () {});
			});
		}
		var openW4Sign = document.getElementById("usis-w4-open-sign-btn");
		if (openW4Sign) {
			openW4Sign.addEventListener("click", function () {
				clearW4SignCanvas();
				var u = (c.state.wizard && c.state.wizard.user) || {};
				var nm = [u.first_name, u.last_name].filter(Boolean).join(" ");
				var nameEl = document.getElementById("usis-w4-sign-fullname");
				if (nameEl && !nameEl.value) nameEl.value = nm;
				var el = document.getElementById("usis-w4-sign-modal");
				if (el && window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(el).show();
			});
		}
		var w4SignSubmit = document.getElementById("usis-w4-sign-submit");
		if (w4SignSubmit) w4SignSubmit.addEventListener("click", submitW4Sign);
		var w4SignClear = document.getElementById("usis-w4-sign-clear");
		if (w4SignClear) w4SignClear.addEventListener("click", clearW4SignCanvas);
		var w4TypedIn = document.getElementById("usis-w4-sign-typed-input");
		var w4TypedPrev = document.getElementById("usis-w4-sign-typed-preview");
		if (w4TypedIn && w4TypedPrev) w4TypedIn.addEventListener("input", function () { w4TypedPrev.textContent = w4TypedIn.value; });
		initW4SignCanvas();
	}

	function init() {
		var c = core();
		if (!c) return;
		wireEvents();
		c.checkSession().then(function () {
			c.wireApplyNav({
				backHref: c.applyStepHref("i9"),
				nextHref: c.w4Complete(c.state.wizard) ? c.applyStepHref("union") : null,
			});
		});
	}

	window.USISHireW4 = {
		afterWizardLoad: updateW4Ui,
		init: init,
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
