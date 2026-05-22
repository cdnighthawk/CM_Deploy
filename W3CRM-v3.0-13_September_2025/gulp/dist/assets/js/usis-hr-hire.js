(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string") {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			if (s) return s;
		}
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (m) {
			var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
			if (c) return c;
		}
		if (window.location.protocol === "file:") return "http://127.0.0.1:5000";
		return "";
	}

	var state = {
		wizard: null,
		authenticated: false,
		selfRegisterEnabled: true,
		section1: null,
		w4Data: null,
		signDrawing: false,
		w4SignDrawing: false,
	};

	var TASK_ORDER = ["account", "application", "i9", "w4", "union_card", "union_dispatch"];

	function loginUrl() {
		return "page-login.html?next=" + encodeURIComponent("usis-hr-hire.html");
	}

	function registerUrl() {
		return "page-register.html?next=" + encodeURIComponent("usis-hr-hire.html");
	}

	function staticGuestTasks() {
		return [
			{
				key: "account",
				title: "Create your USIS account",
				description: "Sign in or register so your progress is saved.",
				status: "not_started",
				locked: false,
			},
			{
				key: "application",
				title: "Employment application",
				description: "Profile, contact, and position details.",
				status: "locked",
				locked: true,
				prerequisite: "account",
			},
			{
				key: "union_card",
				title: "Union card",
				description: "Photo of your union membership card.",
				status: "locked",
				locked: true,
				prerequisite: "application",
			},
			{
				key: "union_dispatch",
				title: "Union dispatch",
				description: "Photo of your union dispatch slip.",
				status: "locked",
				locked: true,
				prerequisite: "application",
			},
			{
				key: "i9",
				title: "Form I-9 — Section 1",
				description: "Employment eligibility and identity.",
				status: "locked",
				locked: true,
				prerequisite: "application",
			},
			{
				key: "w4",
				title: "Form W-4 — withholding",
				description: "Federal income tax withholding.",
				status: "locked",
				locked: true,
				prerequisite: "i9",
			},
		];
	}

	function statusBadgeClass(status) {
		if (status === "complete") return "text-bg-success";
		if (status === "in_progress") return "text-bg-primary";
		if (status === "locked") return "text-bg-secondary";
		return "text-bg-light text-dark border";
	}

	function statusLabel(status) {
		return {
			complete: "Complete",
			in_progress: "In progress",
			not_started: "Not started",
			locked: "Locked",
		}[status] || status;
	}

	function renderProgress(progress) {
		var p = progress || { completed: 0, total: 4, percent: 0 };
		var label = document.getElementById("usis-hire-progress-label");
		var bar = document.getElementById("usis-hire-progress-bar");
		if (label) label.textContent = p.completed + " of " + p.total + " complete";
		if (bar) {
			bar.style.width = (p.percent || 0) + "%";
			bar.setAttribute("aria-valuenow", String(p.percent || 0));
		}
	}

	function renderTaskList(tasks) {
		var ul = document.getElementById("usis-hire-tasks");
		if (!ul) return;
		ul.innerHTML = "";
		(tasks || []).forEach(function (t, idx) {
			var st = t.locked && t.status !== "complete" ? "locked" : t.status;
			var li = document.createElement("li");
			li.className = "list-group-item d-flex flex-wrap justify-content-between align-items-start gap-2";
			li.setAttribute("data-task-key", t.key);
			var openBtn =
				!t.locked || t.key === "account"
					? '<button type="button" class="btn btn-outline-primary btn-sm usis-hire-task-open" data-task-key="' +
					  escAttr(t.key) +
					  '">' +
					  (t.key === "account" && !state.authenticated ? "Sign in / register" : "Open") +
					  "</button>"
					: "";
			li.innerHTML =
				'<div class="me-2"><span class="badge rounded-pill ' +
				statusBadgeClass(st) +
				' me-2">' +
				statusLabel(st) +
				"</span>" +
				'<span class="fw-semibold small">' +
				(idx + 1) +
				". " +
				escHtml(t.title) +
				"</span>" +
				'<p class="text-muted small mb-0 mt-1">' +
				escHtml(t.description || "") +
				"</p></div>" +
				openBtn;
			ul.appendChild(li);
		});
		ul.querySelectorAll(".usis-hire-task-open").forEach(function (btn) {
			btn.addEventListener("click", function () {
				openTask(btn.getAttribute("data-task-key"));
			});
		});
	}

	function escHtml(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function escAttr(s) {
		return escHtml(s).replace(/"/g, "&quot;");
	}

	function openTask(key) {
		if (key === "account" && !state.authenticated) {
			window.location.href = loginUrl();
			return;
		}
		var pane = document.querySelector('[data-hire-task="' + key + '"]');
		if (pane) pane.scrollIntoView({ behavior: "smooth", block: "start" });
	}

	function applyTaskLocks(tasks) {
		var map = {};
		(tasks || []).forEach(function (t) {
			map[t.key] = t;
		});
		document.querySelectorAll("[data-hire-task]").forEach(function (pane) {
			var key = pane.getAttribute("data-hire-task");
			var t = map[key];
			var locked = t && t.locked && t.status !== "complete";
			pane.classList.toggle("opacity-50", !!locked);
			var body = pane.querySelector(".card-body");
			if (body) body.style.pointerEvents = locked ? "none" : "";
		});
	}

	function setAuthGate(visible) {
		var gate = document.getElementById("usis-hire-auth-gate");
		var ws = document.getElementById("usis-hire-workspace");
		if (gate) gate.classList.toggle("d-none", !visible);
		if (ws) ws.classList.toggle("d-none", visible);
		var login = document.getElementById("usis-hire-login-link");
		var reg = document.getElementById("usis-hire-register-link");
		if (login) login.href = loginUrl();
		if (reg) {
			reg.href = registerUrl();
			reg.classList.toggle("d-none", !state.selfRegisterEnabled);
		}
	}

	function showErr(msg) {
		var el = document.getElementById("usis-hire-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}


	function gatherApplicationPayload() {
		return {
			position_applying_for: (document.getElementById("usis-hire-position") || {}).value || "",
			preferred_start_date: (document.getElementById("usis-hire-start") || {}).value || "",
			address_line1: (document.getElementById("usis-hire-addr") || {}).value || "",
			city: (document.getElementById("usis-hire-city") || {}).value || "",
			state: (document.getElementById("usis-hire-state") || {}).value || "",
			postal_code: (document.getElementById("usis-hire-zip") || {}).value || "",
			emergency_contact_name: (document.getElementById("usis-hire-ec-name") || {}).value || "",
			emergency_contact_phone: (document.getElementById("usis-hire-ec-phone") || {}).value || "",
			prior_employer_summary: (document.getElementById("usis-hire-prior") || {}).value || "",
		};
	}

	function currentSection1() {
		if (!window.USISHrI9) return state.section1 || {};
		var w = state.wizard || {};
		var i9 = w.i9 || {};
		return window.USISHrI9.mergePrefill(i9.prefill, state.section1 || i9.draft);
	}

	function wireI9DocPhotos(root) {
		if (!root || !window.USISHrI9Docs) return;
		var i9 = (state.wizard && state.wizard.i9) || {};
		window.USISHrI9Docs.wire(root, {
			locked: !!i9.locked,
			apiBase: apiBase,
			documents: i9.documents || [],
			onChange: function () {
				if (state.wizard && state.wizard.i9 && window.USISHrI9Docs.getAll) {
					state.wizard.i9.documents = window.USISHrI9Docs.getAll();
				}
			},
		});
	}

	function wireUnionDocPhotos() {
		if (!window.USISHrUnionDocs) return;
		var union = (state.wizard && state.wizard.union) || {};
		var tasks = (state.wizard && state.wizard.tasks) || [];
		var cardTask = tasks.filter(function (t) {
			return t.key === "union_card";
		})[0];
		var taskLocked =
			cardTask && cardTask.locked && cardTask.status !== "complete";
		var cardRoot = document.getElementById("usis-union-card-docs-root");
		var dispatchRoot = document.getElementById("usis-union-dispatch-docs-root");
		var parent = cardRoot && cardRoot.parentElement ? cardRoot.parentElement.parentElement : null;
		var wrap = parent || document.getElementById("usis-hire-workspace");
		if (!wrap) return;
		window.USISHrUnionDocs.wire(wrap, {
			locked: !!union.locked || !!taskLocked,
			apiBase: apiBase,
			documents: union.documents || [],
			onChange: function () {
				if (state.wizard && state.wizard.union && window.USISHrUnionDocs.getAll) {
					state.wizard.union.documents = window.USISHrUnionDocs.getAll();
				}
				return loadWizard();
			},
		});
	}

	function updateI9Ui() {
		var w = state.wizard || {};
		var st = w.steps || {};
		var i9 = w.i9 || {};
		var app = w.application || {};
		var appDone = (st.application && st.application.completed) || !!app.submitted_at;
		var signed = i9.status === "signed" || (st.i9 && st.i9.signed_at);
		var completed = i9.status === "completed" || i9.status === "signed" || i9.completed_at;

		var startBtn = document.getElementById("usis-i9-start-btn");
		var reviewBtn = document.getElementById("usis-i9-review-btn");
		var reviewPanel = document.getElementById("usis-i9-review-panel");
		var signedBanner = document.getElementById("usis-i9-signed-banner");
		var signBar = document.getElementById("usis-i9-sign-bar");

		if (startBtn) {
			startBtn.disabled = !appDone || signed;
			startBtn.textContent = completed && !signed ? "Edit I-9 questionnaire" : "Start / continue I-9";
			startBtn.title = !appDone
				? "Save Step 1 (employment application) first"
				: signed
					? "I-9 Section 1 is signed and locked"
					: "";
		}
		if (reviewBtn) {
			reviewBtn.classList.toggle("d-none", !completed || signed);
		}
		if (reviewPanel) {
			reviewPanel.classList.toggle("d-none", !completed && !signed);
		}
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
	}

	function renderReviewPanel() {
		var root = document.getElementById("usis-i9-review-root");
		if (!root || !window.USISHrI9) return;
		var locked = (state.wizard && state.wizard.i9 && state.wizard.i9.locked) || false;
		window.USISHrI9.renderForm(root, currentSection1(), { reviewMode: true, locked: locked });
		wireI9DocPhotos(root);
	}

	function openI9Modal() {
		var root = document.getElementById("usis-i9-modal-root");
		if (!root || !window.USISHrI9) {
			if (!window.USISHrI9) showErr("I-9 form module did not load. Hard-refresh the page.");
			return;
		}
		var i9 = (state.wizard && state.wizard.i9) || {};
		window.USISHrI9.renderForm(root, currentSection1(), { reviewMode: false, locked: !!i9.locked });
		wireI9DocPhotos(root);
		var err = document.getElementById("usis-i9-modal-err");
		if (err) {
			err.classList.add("d-none");
			err.textContent = "";
		}
		var el = document.getElementById("usis-i9-modal");
		if (el && window.bootstrap && window.bootstrap.Modal) {
			window.bootstrap.Modal.getOrCreateInstance(el).show();
		}
	}

	function saveSection1(markComplete, fromReview) {
		var root = fromReview
			? document.getElementById("usis-i9-review-root")
			: document.getElementById("usis-i9-modal-root");
		if (!root || !window.USISHrI9) return Promise.reject(new Error("Form not ready"));
		var data = window.USISHrI9.collectFromForm(root);
		var v = window.USISHrI9.validate(data);
		if (!v.ok) {
			var msg = v.errors.join("; ");
			if (fromReview) showErr(msg);
			else {
				var errEl = document.getElementById("usis-i9-modal-err");
				if (errEl) {
					errEl.textContent = msg;
					errEl.classList.remove("d-none");
				}
			}
			return Promise.reject(new Error(msg));
		}
		state.section1 = data;
		return fetch(apiBase() + "/api/v1/hr/me/i9-section1", {
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

	function currentW4() {
		if (!window.USISHrW4) return state.w4Data || {};
		var w = state.wizard || {};
		var w4 = w.w4 || {};
		return window.USISHrW4.mergePrefill(w4.prefill, state.w4Data || w4.draft);
	}

	function wireW4DocPhotos(root) {
		if (!root || !window.USISHrW4Docs) return;
		var w4 = (state.wizard && state.wizard.w4) || {};
		window.USISHrW4Docs.wire(root, {
			locked: !!w4.locked,
			apiBase: apiBase,
			documents: w4.documents || [],
			onChange: function () {
				if (state.wizard && state.wizard.w4 && window.USISHrW4Docs.getAll) {
					state.wizard.w4.documents = window.USISHrW4Docs.getAll();
				}
			},
		});
	}

	function updateW4Ui() {
		var w = state.wizard || {};
		var st = w.steps || {};
		var w4 = w.w4 || {};
		var i9 = w.i9 || {};
		var i9Signed = i9.status === "signed" || (st.i9 && st.i9.signed_at);
		var signed = w4.status === "signed" || (st.w4 && st.w4.signed_at);
		var completed = w4.status === "completed" || w4.status === "signed" || w4.completed_at;

		var startBtn = document.getElementById("usis-w4-start-btn");
		var reviewBtn = document.getElementById("usis-w4-review-btn");
		var reviewPanel = document.getElementById("usis-w4-review-panel");
		var signedBanner = document.getElementById("usis-w4-signed-banner");
		var signBar = document.getElementById("usis-w4-sign-bar");

		if (startBtn) {
			startBtn.disabled = !i9Signed || signed;
			startBtn.textContent = completed && !signed ? "Edit W-4 questionnaire" : "Start / continue W-4";
			startBtn.title = !i9Signed ? "Complete and sign Form I-9 first" : signed ? "W-4 is signed and locked" : "";
		}
		if (reviewBtn) reviewBtn.classList.toggle("d-none", !completed || signed);
		if (reviewPanel) reviewPanel.classList.toggle("d-none", !completed && !signed);
		if (signedBanner) {
			if (signed) {
				signedBanner.textContent =
					"Form W-4 signed on " + (st.w4.signed_at || w4.signed_at || "file") + ". Section is locked.";
				signedBanner.classList.remove("d-none");
			} else {
				signedBanner.classList.add("d-none");
			}
		}
		if (signBar) signBar.classList.toggle("d-none", signed || !completed);
		if (completed && !signed && reviewPanel && !reviewPanel.classList.contains("d-none")) {
			renderW4ReviewPanel();
		}
	}

	function renderW4ReviewPanel() {
		var root = document.getElementById("usis-w4-review-root");
		if (!root || !window.USISHrW4) return;
		var locked = (state.wizard && state.wizard.w4 && state.wizard.w4.locked) || false;
		window.USISHrW4.renderForm(root, currentW4(), { reviewMode: true, locked: locked });
		wireW4DocPhotos(root);
	}

	function openW4Modal() {
		var root = document.getElementById("usis-w4-modal-root");
		if (!root || !window.USISHrW4) {
			if (!window.USISHrW4) showErr("W-4 form module did not load. Hard-refresh the page.");
			return;
		}
		var w4 = (state.wizard && state.wizard.w4) || {};
		window.USISHrW4.renderForm(root, currentW4(), { reviewMode: false, locked: !!w4.locked });
		wireW4DocPhotos(root);
		var err = document.getElementById("usis-w4-modal-err");
		if (err) {
			err.classList.add("d-none");
			err.textContent = "";
		}
		var el = document.getElementById("usis-w4-modal");
		if (el && window.bootstrap && window.bootstrap.Modal) {
			window.bootstrap.Modal.getOrCreateInstance(el).show();
		}
	}

	function saveW4(markComplete, fromReview) {
		var root = fromReview
			? document.getElementById("usis-w4-review-root")
			: document.getElementById("usis-w4-modal-root");
		if (!root || !window.USISHrW4) return Promise.reject(new Error("Form not ready"));
		var data = window.USISHrW4.collectFromForm(root);
		var v = window.USISHrW4.validate(data);
		if (!v.ok) {
			var msg = v.errors.join("; ");
			if (fromReview) showErr(msg);
			else {
				var errEl = document.getElementById("usis-w4-modal-err");
				if (errEl) {
					errEl.textContent = msg;
					errEl.classList.remove("d-none");
				}
			}
			return Promise.reject(new Error(msg));
		}
		state.w4Data = data;
		return fetch(apiBase() + "/api/v1/hr/me/w4", {
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
			state.w4SignDrawing = true;
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
		state.w4SignDrawing = false;
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
		fetch(apiBase() + "/api/v1/hr/me/w4/sign", {
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
				return loadWizard();
			})
			.catch(function (e) {
				if (errEl) {
					errEl.textContent = e.message || String(e);
					errEl.classList.remove("d-none");
				}
				showErr(e.message || String(e));
			});
	}

	function applyWizardToForm(w) {
		var u = w.user || {};
		var fn = document.getElementById("usis-hire-fn");
		var ln = document.getElementById("usis-hire-ln");
		var ph = document.getElementById("usis-hire-phone");
		if (fn) fn.value = u.first_name || "";
		if (ln) ln.value = u.last_name || "";
		if (ph) ph.value = u.phone || "";
		var app = w.application && w.application.payload;
		if (app && typeof app === "object") {
			function v(id, key) {
				var el = document.getElementById(id);
				if (el && app[key] != null) el.value = String(app[key]);
			}
			v("usis-hire-position", "position_applying_for");
			v("usis-hire-start", "preferred_start_date");
			v("usis-hire-addr", "address_line1");
			v("usis-hire-city", "city");
			v("usis-hire-state", "state");
			v("usis-hire-zip", "postal_code");
			v("usis-hire-ec-name", "emergency_contact_name");
			v("usis-hire-ec-phone", "emergency_contact_phone");
			v("usis-hire-prior", "prior_employer_summary");
		}
		var links = w.official_links || {};
		var a1 = document.getElementById("usis-hire-link-i9-pdf");
		var a2 = document.getElementById("usis-hire-link-i9-help");
		var a3 = document.getElementById("usis-hire-link-w4");
		if (a1 && links.i9_pdf) a1.href = links.i9_pdf;
		if (a2 && links.i9_instructions) a2.href = links.i9_instructions;
		if (a3 && links.w4_pdf) a3.href = links.w4_pdf;
		state.section1 = window.USISHrI9 ? window.USISHrI9.mergePrefill(w.i9 && w.i9.prefill, w.i9 && w.i9.draft) : null;
		state.w4Data = window.USISHrW4 ? window.USISHrW4.mergePrefill(w.w4 && w.w4.prefill, w.w4 && w.w4.draft) : null;

		var tasks = w.tasks || [];
		renderTaskList(tasks);
		renderProgress(w.progress);
		applyTaskLocks(tasks);
		wireUnionDocPhotos();
		updateI9Ui();
		updateW4Ui();

		var status = document.getElementById("usis-hire-status");
		if (status) {
			var prog = w.progress || {};
			status.textContent =
				prog.completed >= prog.total
					? "All hiring tasks are on file. HR may still require original I-9 / W-4 documents outside this app."
					: "Complete each checklist item in order. You can revisit this page to finish later.";
		}
	}

	function loadWizard() {
		return fetch(apiBase() + "/api/v1/hr/me/hire-wizard", { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				if (r.status === 401) throw new Error("unauthorized");
				if (!r.ok) {
					return r.text().then(function (t) {
						throw new Error(t || "HTTP " + r.status);
					});
				}
				return r.json();
			})
			.then(function (w) {
				state.wizard = w;
				var disc = document.getElementById("usis-hire-disclaimer");
				if (disc) disc.textContent = w.disclaimer || "";
				applyWizardToForm(w);
				showErr("");
			});
	}

	function checkSession() {
		return fetch(apiBase() + "/api/v1/auth/status", { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				return r.json();
			})
			.then(function (body) {
				state.authenticated = !!(body && body.authenticated);
				state.selfRegisterEnabled = body && body.self_register_enabled !== false;
				if (!state.authenticated) {
					setAuthGate(true);
					renderTaskList(staticGuestTasks());
					renderProgress({ completed: 0, total: 6, percent: 0 });
					var disc = document.getElementById("usis-hire-disclaimer");
					if (disc)
						disc.textContent =
							"Create a USIS account or sign in to save your employment application, I-9, and W-4 progress.";
					return null;
				}
				setAuthGate(false);
				return loadWizard();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function patchMe() {
		var root = apiBase();
		var body = {
			first_name: (document.getElementById("usis-hire-fn") || {}).value,
			last_name: (document.getElementById("usis-hire-ln") || {}).value,
			phone: (document.getElementById("usis-hire-phone") || {}).value,
		};
		return fetch(root + "/api/v1/me", {
			method: "PATCH",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify(body),
		}).then(function (r) {
			if (!r.ok) {
				return r.json().then(function (j) {
					throw new Error(j.error || "HTTP " + r.status);
				});
			}
			return r.json();
		});
	}

	function submitApplication() {
		showErr("");
		var root = apiBase();
		patchMe()
			.then(function () {
				return fetch(root + "/api/v1/hr/me/hire-application", {
					method: "POST",
					credentials: "include",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: JSON.stringify({ application: gatherApplicationPayload() }),
				});
			})
			.then(function (r) {
				if (!r.ok) {
					return r.json().then(function (j) {
						throw new Error(j.error || "HTTP " + r.status);
					});
				}
				return r.json();
			})
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Application saved.");
				return loadWizard();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
				if (window.USISNotify) window.USISNotify.error(e.message || String(e));
			});
	}

	/* Signature canvas */
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
			state.signDrawing = true;
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
		state.signDrawing = false;
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
		fetch(apiBase() + "/api/v1/hr/me/i9-section1/sign", {
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
				return loadWizard();
			})
			.catch(function (e) {
				if (errEl) {
					errEl.textContent = e.message || String(e);
					errEl.classList.remove("d-none");
				}
				showErr(e.message || String(e));
			});
	}

	function init() {
		var b = document.getElementById("usis-hire-submit-app");
		if (b) b.addEventListener("click", submitApplication);

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
						return loadWizard();
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
						return loadWizard().then(function () {
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
				var u = (state.wizard && state.wizard.user) || {};
				var nm = [u.first_name, u.last_name].filter(Boolean).join(" ");
				var nameEl = document.getElementById("usis-i9-sign-fullname");
				if (nameEl && !nameEl.value) nameEl.value = nm;
				var el = document.getElementById("usis-i9-sign-modal");
				if (el && window.bootstrap && window.bootstrap.Modal) {
					window.bootstrap.Modal.getOrCreateInstance(el).show();
				}
			});
		}

		var signSubmit = document.getElementById("usis-i9-sign-submit");
		if (signSubmit) signSubmit.addEventListener("click", submitI9Sign);

		var signClear = document.getElementById("usis-i9-sign-clear");
		if (signClear) signClear.addEventListener("click", clearSignCanvas);

		var typedIn = document.getElementById("usis-i9-sign-typed-input");
		var typedPrev = document.getElementById("usis-i9-sign-typed-preview");
		if (typedIn && typedPrev) {
			typedIn.addEventListener("input", function () {
				typedPrev.textContent = typedIn.value;
			});
		}

		var startW4 = document.getElementById("usis-w4-start-btn");
		if (startW4) startW4.addEventListener("click", openW4Modal);

		var reviewW4 = document.getElementById("usis-w4-review-btn");
		if (reviewW4) {
			reviewW4.addEventListener("click", function () {
				var panel = document.getElementById("usis-w4-review-panel");
				if (panel) panel.classList.remove("d-none");
				renderW4ReviewPanel();
			});
		}

		var editW4 = document.getElementById("usis-w4-edit-btn");
		if (editW4) editW4.addEventListener("click", openW4Modal);

		var saveW4Review = document.getElementById("usis-w4-save-review-btn");
		if (saveW4Review) {
			saveW4Review.addEventListener("click", function () {
				saveW4(true, true)
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("W-4 saved.");
						return loadWizard();
					})
					.catch(function () {});
			});
		}

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
						if (window.USISNotify) window.USISNotify.success("W-4 complete — review and sign.");
						return loadWizard().then(function () {
							var panel = document.getElementById("usis-w4-review-panel");
							if (panel) panel.classList.remove("d-none");
							renderW4ReviewPanel();
						});
					})
					.catch(function () {});
			});
		}

		var openW4Sign = document.getElementById("usis-w4-open-sign-btn");
		if (openW4Sign) {
			openW4Sign.addEventListener("click", function () {
				clearW4SignCanvas();
				var u = (state.wizard && state.wizard.user) || {};
				var nm = [u.first_name, u.last_name].filter(Boolean).join(" ");
				var nameEl = document.getElementById("usis-w4-sign-fullname");
				if (nameEl && !nameEl.value) nameEl.value = nm;
				var el = document.getElementById("usis-w4-sign-modal");
				if (el && window.bootstrap && window.bootstrap.Modal) {
					window.bootstrap.Modal.getOrCreateInstance(el).show();
				}
			});
		}

		var w4SignSubmit = document.getElementById("usis-w4-sign-submit");
		if (w4SignSubmit) w4SignSubmit.addEventListener("click", submitW4Sign);

		var w4SignClear = document.getElementById("usis-w4-sign-clear");
		if (w4SignClear) w4SignClear.addEventListener("click", clearW4SignCanvas);

		var w4TypedIn = document.getElementById("usis-w4-sign-typed-input");
		var w4TypedPrev = document.getElementById("usis-w4-sign-typed-preview");
		if (w4TypedIn && w4TypedPrev) {
			w4TypedIn.addEventListener("input", function () {
				w4TypedPrev.textContent = w4TypedIn.value;
			});
		}

		initSignCanvas();
		initW4SignCanvas();
		checkSession();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
