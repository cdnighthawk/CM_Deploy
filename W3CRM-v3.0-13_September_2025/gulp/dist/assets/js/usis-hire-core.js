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
		if (!applicationSaved(wizard)) return "application";
		if (!unionComplete(wizard)) return "union";
		if (!i9Complete(wizard)) return "i9";
		if (!w4Complete(wizard)) return "w4";
		return "complete";
	}

	function canAccessStep(stepId, wizard) {
		if (!stepId || stepId === "application") return true;
		if (!applicationSaved(wizard)) return false;
		if (stepId === "union") return true;
		if (stepId === "i9") return true;
		if (stepId === "w4") return i9Complete(wizard);
		if (stepId === "complete") return w4Complete(wizard);
		return false;
	}

	var REDIRECT_MSG_KEY = "usis_hire_redirect_msg";

	function applicationSaved(wizard) {
		var w = wizard || {};
		var st = w.steps || {};
		if (st.application && st.application.completed) return true;
		if (w.application && w.application.submitted_at) return true;
		return applicationComplete(wizard);
	}

	function resumeStepUrl(wizard) {
		var stepId = firstAllowedStepId(wizard);
		return "apply/" + stepFile(stepId);
	}

	function stepPrereqMessage(stepId, wizard) {
		if (isWizardLocked(wizard)) {
			var review = wizardReview(wizard);
			if (review.hire_status === "rejected") {
				return (
					"Your application is closed and cannot be edited." +
					(review.review_notes ? " " + review.review_notes : "")
				);
			}
			if (review.hire_status === "hired") {
				return "You have been hired. HR will follow up with onboarding next steps.";
			}
			return "This application is no longer open for editing.";
		}
		if (stepId === "i9" && !applicationSaved(wizard)) {
			return "Complete step 1 first — save your employment application before starting Form I-9.";
		}
		if (stepId === "w4" && !i9Complete(wizard)) {
			return "Sign Form I-9 (step 3) before starting Form W-4.";
		}
		if (stepId === "complete" && !w4Complete(wizard)) {
			return "Sign Form W-4 (step 4) before finishing your application.";
		}
		return null;
	}

	function prereqLinkForStep(stepId) {
		if (stepId === "i9" || stepId === "union" || stepId === "w4") {
			if (!applicationSaved(state.wizard)) return "application.html";
		}
		if (stepId === "w4") return "i9.html";
		if (stepId === "complete") return "w4.html";
		return "application.html";
	}

	function renderStepPrereqBanner(wizard, stepId, bannerId) {
		var el = document.getElementById(bannerId || "usis-hire-step-prereq");
		if (!el) return;
		var msg = stepPrereqMessage(stepId, wizard);
		if (!msg) {
			el.classList.add("d-none");
			el.innerHTML = "";
			return;
		}
		var link = prereqLinkForStep(stepId);
		var linkLabel =
			link === "application.html"
				? "Go to employment application"
				: link === "i9.html"
					? "Go to Form I-9"
					: link === "w4.html"
						? "Go to Form W-4"
						: "Go to previous step";
		el.className = isWizardLocked(wizard) ? "alert alert-warning py-2 small mb-3" : "alert alert-info py-2 small mb-3";
		el.innerHTML =
			msg +
			(isWizardLocked(wizard)
				? ""
				: ' <a href="' + link + '" class="alert-link fw-semibold">' + linkLabel + "</a>.");
		el.classList.remove("d-none");
	}

	function setRedirectMessage(msg) {
		try {
			if (msg) sessionStorage.setItem(REDIRECT_MSG_KEY, msg);
		} catch (e) {}
	}

	function showRedirectMessage() {
		var el = document.getElementById("usis-hire-redirect-info");
		if (!el) return;
		var msg = null;
		try {
			msg = sessionStorage.getItem(REDIRECT_MSG_KEY);
			if (msg) sessionStorage.removeItem(REDIRECT_MSG_KEY);
		} catch (e) {}
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function updateStepNavLocks(wizard) {
		document.querySelectorAll(".usis-apply-step").forEach(function (li) {
			var stepId = li.getAttribute("data-step");
			if (!stepId) return;
			var allowed = canAccessStep(stepId, wizard);
			li.classList.toggle("usis-apply-step-locked", !allowed);
			var a = li.querySelector("a");
			if (a) {
				a.setAttribute("aria-disabled", allowed ? "false" : "true");
				if (!allowed) {
					a.setAttribute("tabindex", "-1");
				} else {
					a.removeAttribute("tabindex");
				}
			}
		});
	}

	function wireStepNavLocks() {
		document.querySelectorAll(".usis-apply-step a").forEach(function (a) {
			if (a.getAttribute("data-usis-nav-wired") === "1") return;
			a.setAttribute("data-usis-nav-wired", "1");
			a.addEventListener("click", function (ev) {
				var li = a.closest(".usis-apply-step");
				if (!li) return;
				var stepId = li.getAttribute("data-step");
				if (!stepId || canAccessStep(stepId, state.wizard)) return;
				ev.preventDefault();
				var msg = stepPrereqMessage(stepId, state.wizard);
				if (msg) showErr(msg);
				if (window.USISNotify && msg) window.USISNotify.warning(msg);
			});
		});
	}

	function redirectToStep(stepId, reasonMsg) {
		if (reasonMsg) setRedirectMessage(reasonMsg);
		window.location.replace(stepFile(stepId));
	}

	function enforceStepAccess(stepId, wizard) {
		if (!stepId || stepId === "complete") return;
		if (canAccessStep(stepId, wizard)) return;
		var msg = stepPrereqMessage(stepId, wizard) || "Complete the previous steps before continuing.";
		redirectToStep(firstAllowedStepId(wizard), msg);
	}

	function highlightStepNav(stepId) {
		document.querySelectorAll(".usis-apply-step").forEach(function (li) {
			var active = li.getAttribute("data-step") === stepId;
			li.classList.toggle("fw-semibold", active);
			li.classList.toggle("text-primary", active);
			li.classList.toggle("usis-apply-step-active", active);
		});
		if (state.wizard) updateStepNavLocks(state.wizard);
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

	function friendlyFetchError(err) {
		var msg = (err && err.message) || String(err || "");
		if (/NetworkError|Failed to fetch|Load failed|Network request failed/i.test(msg)) {
			return "Could not reach the server. Check your connection and refresh the page.";
		}
		return msg;
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

	function wizardReview(w) {
		return (w && w.review) || {};
	}

	function isWizardLocked(w) {
		var review = wizardReview(w);
		return !!review.wizard_locked;
	}

	function renderReviewBanner(w) {
		var banner = document.getElementById("usis-hire-review-banner");
		if (!banner) return;
		var review = wizardReview(w);
		var status = review.hire_status;
		if (status === "rejected") {
			banner.className = "alert alert-warning mb-3";
			banner.textContent =
				"Your application was not approved." +
				(review.review_notes ? " " + review.review_notes : "") +
				" You can sign out below; this account is read-only.";
			banner.classList.remove("d-none");
			return;
		}
		if (status === "hired") {
			banner.className = "alert alert-success mb-3";
			banner.textContent = "Congratulations — you have been hired. HR will follow up with onboarding next steps.";
			banner.classList.remove("d-none");
			return;
		}
		banner.classList.add("d-none");
	}

	function renderCompleteReviewStatus(w) {
		renderReviewBanner(w);
		var card = document.querySelector(".card .card-body");
		if (!card) return;
		var review = wizardReview(w);
		if (review.hire_status === "rejected") {
			card.querySelectorAll("a.btn-outline-secondary").forEach(function (a) {
				a.classList.add("d-none");
			});
		}
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
		renderReviewBanner(w);
		updateStepNavLocks(w);
		if (state.currentStep) renderStepPrereqBanner(w, state.currentStep);
		if (isWizardLocked(w)) {
			document.querySelectorAll("button[type='submit'], .usis-hire-save, #usis-apply-save-next").forEach(function (el) {
				el.disabled = true;
				el.classList.add("disabled");
			});
		}
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
		wireStepNavLocks();
		showRedirectMessage();
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
				if (e && e.message === "unauthorized") {
					setAuthGate(true);
					return;
				}
				showErr(friendlyFetchError(e));
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
				return loadWizard().then(function (w) {
					var ok = document.getElementById("usis-hire-app-saved-ok");
					if (ok) ok.classList.remove("d-none");
					if (w) updateStepNavLocks(w);
					return w;
				});
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
		friendlyFetchError: friendlyFetchError,
		loadWizard: loadWizard,
		checkSession: checkSession,
		submitApplication: submitApplication,
		wireApplyNav: wireApplyNav,
		applicationComplete: applicationComplete,
		applicationSaved: applicationSaved,
		unionComplete: unionComplete,
		i9Complete: i9Complete,
		w4Complete: w4Complete,
		firstAllowedStepId: firstAllowedStepId,
		canAccessStep: canAccessStep,
		redirectToStep: redirectToStep,
		stepFromBody: stepFromBody,
		stepFile: stepFile,
		resumeStepUrl: resumeStepUrl,
		renderStepPrereqBanner: renderStepPrereqBanner,
		updateStepNavLocks: updateStepNavLocks,
		stepPrereqMessage: stepPrereqMessage,
		wizardReview: wizardReview,
		isWizardLocked: isWizardLocked,
		renderCompleteReviewStatus: renderCompleteReviewStatus,
	};
})();
