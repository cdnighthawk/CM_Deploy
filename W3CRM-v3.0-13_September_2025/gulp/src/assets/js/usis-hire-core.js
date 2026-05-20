/**
 * Shared hire-wizard utilities for multi-page applicant flow (/apply/*).
 */
(function () {
	"use strict";

	var ENTRY_PATH = "apply/application.html";

	var STEPS = [
		{ id: "application", file: "application.html", label: "Application" },
		{ id: "union", file: "union.html", label: "Union docs" },
		{ id: "i9", file: "i9.html", label: "Form I-9" },
		{ id: "w4", file: "w4.html", label: "Form W-4" },
		{ id: "complete", file: "complete.html", label: "Done" },
	];

	var state = {
		wizard: null,
		authenticated: false,
		selfRegisterEnabled: true,
		section1: null,
		w4Data: null,
		signDrawing: false,
		w4SignDrawing: false,
		currentStep: null,
	};

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

	function rootRelativePath() {
		var p = (window.location.pathname || "").replace(/\\/g, "/");
		if (p.charAt(0) === "/") p = p.slice(1);
		return p;
	}

	function nextParamPath() {
		var p = rootRelativePath();
		return p || ENTRY_PATH;
	}

	function loginUrl() {
		return "../page-login.html?next=" + encodeURIComponent(nextParamPath());
	}

	function registerUrl() {
		return "../page-register.html?next=" + encodeURIComponent(nextParamPath());
	}

	function stepFromBody() {
		var b = document.body;
		if (b && b.getAttribute("data-usis-hire-step")) return b.getAttribute("data-usis-hire-step");
		var p = rootRelativePath().toLowerCase();
		var i;
		for (i = 0; i < STEPS.length; i++) {
			if (p.indexOf("apply/" + STEPS[i].file) !== -1) return STEPS[i].id;
		}
		return null;
	}

	function stepFile(stepId) {
		for (var i = 0; i < STEPS.length; i++) {
			if (STEPS[i].id === stepId) return STEPS[i].file;
		}
		return "application.html";
	}

	function taskMap(wizard) {
		var map = {};
		((wizard && wizard.tasks) || []).forEach(function (t) {
			map[t.key] = t;
		});
		return map;
	}

	function applicationComplete(wizard) {
		var t = taskMap(wizard).application;
		return !!(t && t.status === "complete");
	}

	function unionComplete(wizard) {
		var m = taskMap(wizard);
		return !!(m.union_card && m.union_card.status === "complete" && m.union_dispatch && m.union_dispatch.status === "complete");
	}

	function i9Complete(wizard) {
		var w = wizard || {};
		var st = w.steps || {};
		var i9 = w.i9 || {};
		return i9.status === "signed" || !!(st.i9 && st.i9.signed_at);
	}

	function w4Complete(wizard) {
		var w = wizard || {};
		var st = w.steps || {};
		var w4 = w.w4 || {};
		return w4.status === "signed" || !!(st.w4 && st.w4.signed_at);
	}

	function firstAllowedStepId(wizard) {
		if (!applicationComplete(wizard)) return "application";
		if (!unionComplete(wizard)) return "union";
		if (!i9Complete(wizard)) return "i9";
		if (!w4Complete(wizard)) return "w4";
		return "complete";
	}

	function canAccessStep(stepId, wizard) {
		if (!stepId || stepId === "application") return true;
		if (!applicationComplete(wizard)) return false;
		if (stepId === "union") return true;
		if (stepId === "i9") return true;
		if (stepId === "w4") return i9Complete(wizard);
		if (stepId === "complete") return w4Complete(wizard);
		return false;
	}

	function redirectToStep(stepId) {
		window.location.replace(stepFile(stepId));
	}

	function enforceStepAccess(stepId, wizard) {
		if (!stepId || stepId === "complete") return;
		if (canAccessStep(stepId, wizard)) return;
		redirectToStep(firstAllowedStepId(wizard));
	}

	function highlightStepNav(stepId) {
		document.querySelectorAll(".usis-apply-step").forEach(function (li) {
			var active = li.getAttribute("data-step") === stepId;
			li.classList.toggle("fw-semibold", active);
			li.classList.toggle("text-primary", active);
		});
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

	function wireApplyNav(opts) {
		opts = opts || {};
		var back = document.getElementById("usis-apply-back");
		var next = document.getElementById("usis-apply-next");
		var saveNext = document.getElementById("usis-apply-save-next");
		if (back && opts.backHref) back.setAttribute("href", opts.backHref);
		if (next) {
			if (opts.nextHref) {
				next.setAttribute("href", opts.nextHref);
				next.classList.remove("d-none");
			} else {
				next.classList.add("d-none");
			}
		}
		if (saveNext) {
			if (opts.onSaveNext) {
				saveNext.classList.remove("d-none");
				saveNext.onclick = opts.onSaveNext;
			} else {
				saveNext.classList.add("d-none");
			}
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
		renderProgress(w.progress);
		if (window.USISHireUnion && window.USISHireUnion.afterWizardLoad) window.USISHireUnion.afterWizardLoad(w);
		if (window.USISHireI9 && window.USISHireI9.afterWizardLoad) window.USISHireI9.afterWizardLoad(w);
		if (window.USISHireW4 && window.USISHireW4.afterWizardLoad) window.USISHireW4.afterWizardLoad(w);
	}

	function loadWizard() {
		return fetch(apiBase() + "/api/v1/hr/me/hire-wizard", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
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
				if (state.currentStep) enforceStepAccess(state.currentStep, w);
				return w;
			});
	}

	function checkSession() {
		state.currentStep = stepFromBody();
		if (state.currentStep) highlightStepNav(state.currentStep);
		var signIn = document.getElementById("usis-public-sign-in");
		if (signIn) signIn.setAttribute("href", loginUrl());
		return fetch(apiBase() + "/api/v1/auth/status", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				return r.json();
			})
			.then(function (body) {
				state.authenticated = !!(body && body.authenticated);
				state.selfRegisterEnabled = body && body.self_register_enabled !== false;
				if (!state.authenticated) {
					if (state.currentStep && state.currentStep !== "complete") {
						setAuthGate(true);
					}
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
		return fetch(apiBase() + "/api/v1/me", {
			method: "PATCH",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({
				first_name: (document.getElementById("usis-hire-fn") || {}).value,
				last_name: (document.getElementById("usis-hire-ln") || {}).value,
				phone: (document.getElementById("usis-hire-phone") || {}).value,
			}),
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
		return patchMe()
			.then(function () {
				return fetch(apiBase() + "/api/v1/hr/me/hire-application", {
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
			});
	}

	window.USISHireCore = {
		state: state,
		STEPS: STEPS,
		ENTRY_PATH: ENTRY_PATH,
		apiBase: apiBase,
		loginUrl: loginUrl,
		registerUrl: registerUrl,
		showErr: showErr,
		loadWizard: loadWizard,
		checkSession: checkSession,
		submitApplication: submitApplication,
		wireApplyNav: wireApplyNav,
		applicationComplete: applicationComplete,
		unionComplete: unionComplete,
		i9Complete: i9Complete,
		w4Complete: w4Complete,
		firstAllowedStepId: firstAllowedStepId,
		redirectToStep: redirectToStep,
		stepFromBody: stepFromBody,
	};
})();
