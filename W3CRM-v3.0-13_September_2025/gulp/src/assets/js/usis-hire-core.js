/**
 * Shared hire-wizard utilities for multi-page applicant flow (/apply/*).
 */
(function () {
	"use strict";

	var ENTRY_PATH = "apply/path.html";

	var UNION_STEPS = [
		{ id: "application", file: "application.html", label: "Application" },
		{ id: "i9", file: "i9.html", label: "Form I-9" },
		{ id: "w4", file: "w4.html", label: "Form W-4" },
		{ id: "union", file: "union.html", label: "Union docs", optional: true },
		{ id: "complete", file: "complete.html", label: "Done" },
	];

	var STANDARD_STEPS = [
		{ id: "application", file: "application.html", label: "Application" },
		{ id: "complete", file: "complete.html", label: "Submitted" },
		{ id: "offer", file: "offer.html", label: "Job offer" },
		{ id: "i9", file: "i9.html", label: "Form I-9" },
		{ id: "w4", file: "w4.html", label: "Form W-4" },
	];

	var STEPS = UNION_STEPS;

	var state = {
		wizard: null,
		authenticated: false,
		selfRegisterEnabled: true,
		section1: null,
		w4Data: null,
		signDrawing: false,
		w4SignDrawing: false,
		currentStep: null,
		applicationFormHydrated: false,
		applicationFormDirty: false,
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

	function hirePath(wizard) {
		return wizard && wizard.hire_path;
	}

	function isStandardPath(wizard) {
		return hirePath(wizard) === "standard";
	}

	function isUnionPath(wizard) {
		return hirePath(wizard) === "union_dispatch";
	}

	function stepsForWizard(wizard) {
		if (isStandardPath(wizard)) return STANDARD_STEPS;
		return UNION_STEPS;
	}

	function offerBlock(wizard) {
		return (wizard && wizard.offer) || {};
	}

	function offerAccepted(wizard) {
		return !!offerBlock(wizard).accepted_at;
	}

	function offerPending(wizard) {
		return wizardReview(wizard).hire_status === "offer_extended";
	}

	function offerAvailable(wizard) {
		return offerPending(wizard) || offerAccepted(wizard);
	}

	function standardOnboardingComplete(wizard) {
		return isStandardPath(wizard) && offerAccepted(wizard) && w4Complete(wizard);
	}

	function nextStepAfterApplication(wizard) {
		return isStandardPath(wizard) ? "complete" : "i9";
	}

	function stepFromBody() {
		var b = document.body;
		if (b && b.getAttribute("data-usis-hire-step")) return b.getAttribute("data-usis-hire-step");
		var p = rootRelativePath().toLowerCase();
		if (p.indexOf("apply/path.html") !== -1) return "path";
		if (p.indexOf("apply/offer.html") !== -1) return "offer";
		var steps = stepsForWizard(state.wizard);
		var i;
		for (i = 0; i < steps.length; i++) {
			if (p.indexOf("apply/" + steps[i].file) !== -1) return steps[i].id;
		}
		for (i = 0; i < UNION_STEPS.length; i++) {
			if (p.indexOf("apply/" + UNION_STEPS[i].file) !== -1) return UNION_STEPS[i].id;
		}
		return null;
	}

	function stepFile(stepId, wizard) {
		if (stepId === "path") return "path.html";
		var steps = stepsForWizard(wizard);
		for (var i = 0; i < steps.length; i++) {
			if (steps[i].id === stepId) return steps[i].file;
		}
		for (i = 0; i < UNION_STEPS.length; i++) {
			if (UNION_STEPS[i].id === stepId) return UNION_STEPS[i].file;
		}
		return "application.html";
	}

	/** Step links must include ``apply/`` — pages use ``<base href="../">`` for shared assets. */
	function applyStepHref(stepIdOrFile, wizard) {
		var file = stepIdOrFile;
		if (!file || file.indexOf(".html") === -1) file = stepFile(stepIdOrFile, wizard || state.wizard);
		return "apply/" + file;
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
		if (!wizard || wizard.path_selection_required) return "path";
		if (!applicationSaved(wizard)) return "application";
		if (isStandardPath(wizard)) {
			if (!offerAccepted(wizard)) {
				if (offerPending(wizard)) return "offer";
				return "complete";
			}
			if (!i9Complete(wizard)) return "i9";
			if (!w4Complete(wizard)) return "w4";
			return "complete";
		}
		if (!i9Complete(wizard)) return "i9";
		if (!w4Complete(wizard)) return "w4";
		return "complete";
	}

	function canAccessStep(stepId, wizard) {
		if (!stepId || stepId === "path") return true;
		if (!wizard || wizard.path_selection_required) return stepId === "path";
		if (stepId === "application") return true;
		if (!applicationSaved(wizard)) return false;
		if (isStandardPath(wizard)) {
			if (stepId === "complete") return true;
			if (stepId === "offer") return offerAvailable(wizard);
			if (stepId === "i9" || stepId === "w4") return offerAccepted(wizard) && (stepId === "i9" || i9Complete(wizard));
			if (stepId === "union") return false;
			return false;
		}
		if (stepId === "i9") return true;
		if (stepId === "w4") return i9Complete(wizard);
		if (stepId === "union") return w4Complete(wizard);
		if (stepId === "complete") return w4Complete(wizard);
		if (stepId === "offer") return false;
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
		return applyStepHref(firstAllowedStepId(wizard));
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
			if (review.hire_status === "offer_extended") {
				return "Your application is with HR. Watch your email for a job offer link, or open the Job offer step when it appears.";
			}
			return "This application is no longer open for editing.";
		}
		if (wizard && wizard.path_selection_required && stepId !== "path") {
			return "Answer the onboarding question before continuing.";
		}
		if (stepId === "i9" && !applicationSaved(wizard)) {
			return "Complete step 1 first — save your employment application before starting Form I-9.";
		}
		if (isStandardPath(wizard) && (stepId === "i9" || stepId === "w4") && !offerAccepted(wizard)) {
			return "Accept your job offer before completing Form I-9 and W-4.";
		}
		if (stepId === "offer" && !offerAvailable(wizard)) {
			return "HR has not sent a job offer yet. You will receive email when an offer is ready.";
		}
		if (stepId === "w4" && !i9Complete(wizard)) {
			return "Sign Form I-9 (step 2) before starting Form W-4.";
		}
		if (stepId === "union" && !w4Complete(wizard)) {
			return "Sign Form W-4 (step 3) before uploading union documents.";
		}
		if (stepId === "complete" && isUnionPath(wizard) && !w4Complete(wizard)) {
			return "Sign Form W-4 (step 3) before finishing your application.";
		}
		return null;
	}

	function prereqLinkForStep(stepId) {
		if (!state.wizard || state.wizard.path_selection_required) return applyStepHref("path");
		if (!applicationSaved(state.wizard)) return applyStepHref("application");
		if (stepId === "offer") return applyStepHref("complete");
		if (stepId === "i9" && isStandardPath(state.wizard) && !offerAccepted(state.wizard)) {
			return offerAvailable(state.wizard) ? applyStepHref("offer") : applyStepHref("complete");
		}
		if (stepId === "i9") return applyStepHref("application");
		if (stepId === "w4") return applyStepHref("i9");
		if (stepId === "union" || stepId === "complete") return applyStepHref("w4");
		return applyStepHref("application");
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
			link.indexOf("application.html") !== -1
				? "Go to employment application"
				: link.indexOf("i9.html") !== -1
					? "Go to Form I-9"
					: link.indexOf("w4.html") !== -1
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

	function updateStepNavVisibility(wizard) {
		var nav = document.querySelector(".usis-apply-steps");
		if (nav) {
			nav.classList.toggle("d-none", state.currentStep === "path");
		}
		document.querySelectorAll(".usis-apply-step").forEach(function (li) {
			var stepId = li.getAttribute("data-step");
			if (!stepId) return;
			if (stepId === "offer") {
				li.classList.toggle("d-none", !isStandardPath(wizard));
			}
			if (stepId === "union") {
				li.classList.toggle("d-none", isStandardPath(wizard));
			}
		});
	}

	function updateStepNavLocks(wizard) {
		STEPS = stepsForWizard(wizard);
		updateStepNavVisibility(wizard);
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

	function applyStepPath(stepId) {
		var href = applyStepHref(stepId);
		var current = rootRelativePath().toLowerCase();
		var target = href.toLowerCase();
		return current === target || current.endsWith("/" + target) ? null : href;
	}

	function redirectToStep(stepId, reasonMsg) {
		var href = applyStepPath(stepId);
		if (!href) return;
		if (reasonMsg) setRedirectMessage(reasonMsg);
		window.location.replace(href);
	}

	function enforceStepAccess(stepId, wizard) {
		if (stepId === "path") return;
		if (wizard && wizard.path_selection_required && stepId !== "path") {
			redirectToStep("path", "Answer the onboarding question before continuing.");
			return;
		}
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

	function fieldValue(id) {
		var el = document.getElementById(id);
		return el ? String(el.value || "").trim() : "";
	}

	function radioValue(name) {
		var el = document.querySelector('input[name="' + name + '"]:checked');
		return el ? String(el.value || "").trim() : "";
	}

	function checkboxChecked(id) {
		var el = document.getElementById(id);
		return !!(el && el.checked);
	}

	function howHeardValue() {
		var sel = fieldValue("usis-hire-heard");
		if (sel === "Other") {
			return fieldValue("usis-hire-heard-other") || "Other";
		}
		return sel;
	}

	function normalizeSsnInput(raw) {
		var digits = String(raw || "").replace(/\D/g, "");
		if (digits.length !== 9) return String(raw || "").trim();
		return digits.slice(0, 3) + "-" + digits.slice(3, 5) + "-" + digits.slice(5, 9);
	}

	function validSsn(raw) {
		return /^\d{3}-?\d{2}-?\d{4}$/.test(String(raw || "").replace(/\s/g, ""));
	}

	function gatherApplicationPayload() {
		var payload = {
			position_applying_for: fieldValue("usis-hire-position"),
			preferred_start_date: fieldValue("usis-hire-start"),
			desired_compensation: fieldValue("usis-hire-compensation"),
			work_authorized_us: radioValue("usis-hire-work-auth"),
			requires_sponsorship: radioValue("usis-hire-sponsorship"),
			how_heard_about_position: howHeardValue(),
			middle_initial: fieldValue("usis-hire-mi"),
			date_of_birth: fieldValue("usis-hire-dob"),
			ssn: normalizeSsnInput(fieldValue("usis-hire-ssn")),
			citizenship_status: fieldValue("usis-hire-citizenship"),
			filing_status: fieldValue("usis-hire-filing-status"),
			dependents_amount: fieldValue("usis-hire-dependents"),
			other_income: fieldValue("usis-hire-other-income"),
			deductions: fieldValue("usis-hire-deductions"),
			address_line1: fieldValue("usis-hire-addr"),
			address_line2: fieldValue("usis-hire-addr2"),
			city: fieldValue("usis-hire-city"),
			state: fieldValue("usis-hire-state"),
			postal_code: fieldValue("usis-hire-zip"),
			country: fieldValue("usis-hire-country") || "United States",
			education_level: fieldValue("usis-hire-edu-level"),
			education_school: fieldValue("usis-hire-edu-school"),
			education_degree: fieldValue("usis-hire-edu-degree"),
			education_graduation_year: fieldValue("usis-hire-edu-year"),
			skills_experience: fieldValue("usis-hire-skills"),
			certifications_licenses: fieldValue("usis-hire-certs"),
			emergency_contact_name: fieldValue("usis-hire-ec-name"),
			emergency_contact_phone: fieldValue("usis-hire-ec-phone"),
			emergency_contact_relationship: fieldValue("usis-hire-ec-relationship"),
			drivers_license_number: fieldValue("usis-hire-dl-number"),
			drivers_license_state: fieldValue("usis-hire-dl-state"),
			felony_conviction: radioValue("usis-hire-felony"),
			felony_explanation: fieldValue("usis-hire-felony-explanation"),
			signature_certified: checkboxChecked("usis-hire-sig-certify"),
			signature_full_name: fieldValue("usis-hire-sig-name"),
			signature_date: fieldValue("usis-hire-sig-date"),
		};
		if (window.USISHireApplication && window.USISHireApplication.gatherEmploymentHistory) {
			payload.employment_history = window.USISHireApplication.gatherEmploymentHistory();
		} else {
			payload.employment_history = [];
		}
		return payload;
	}

	function validateApplicationForm() {
		var missing = [];
		function req(label, ok) {
			if (!ok) missing.push(label);
		}
		req("Legal first name", fieldValue("usis-hire-fn"));
		req("Legal last name", fieldValue("usis-hire-ln"));
		req("Phone", fieldValue("usis-hire-phone"));
		req("Position applying for", fieldValue("usis-hire-position"));
		req("Preferred start date", fieldValue("usis-hire-start"));
		req("Work authorization", radioValue("usis-hire-work-auth"));
		req("Sponsorship question", radioValue("usis-hire-sponsorship"));
		if (fieldValue("usis-hire-heard") === "Other") {
			req("How you heard about this position", fieldValue("usis-hire-heard-other"));
		} else {
			req("How you heard about this position", fieldValue("usis-hire-heard"));
		}
		req("Address line 1", fieldValue("usis-hire-addr"));
		req("City", fieldValue("usis-hire-city"));
		req("State / region", fieldValue("usis-hire-state"));
		req("Postal code", fieldValue("usis-hire-zip"));
		req("Country", fieldValue("usis-hire-country"));
		req("Education level", fieldValue("usis-hire-edu-level"));
		req("School / University", fieldValue("usis-hire-edu-school"));
		req("Degree / Certification", fieldValue("usis-hire-edu-degree"));
		req("Graduation year", fieldValue("usis-hire-edu-year"));
		req("Relevant skills / experience", fieldValue("usis-hire-skills"));
		req("Emergency contact name", fieldValue("usis-hire-ec-name"));
		req("Emergency contact phone", fieldValue("usis-hire-ec-phone"));
		req("Emergency contact relationship", fieldValue("usis-hire-ec-relationship"));
		req("Date of birth", fieldValue("usis-hire-dob"));
		if (!validSsn(fieldValue("usis-hire-ssn"))) missing.push("Social Security number (XXX-XX-XXXX)");
		req("Citizenship / immigration status", fieldValue("usis-hire-citizenship"));
		req("Filing status", fieldValue("usis-hire-filing-status"));
		req("Felony question", radioValue("usis-hire-felony"));
		if (radioValue("usis-hire-felony") === "yes") {
			req("Felony explanation", fieldValue("usis-hire-felony-explanation"));
		}
		req("Certification checkbox", checkboxChecked("usis-hire-sig-certify"));
		req("Signature full name", fieldValue("usis-hire-sig-name"));
		req("Signature date", fieldValue("usis-hire-sig-date"));

		var empResult = { ok: true };
		if (window.USISHireApplication && window.USISHireApplication.validateEmploymentHistory) {
			empResult = window.USISHireApplication.validateEmploymentHistory();
			if (!empResult.ok && empResult.message) missing.push(empResult.message);
		}

		if (missing.length) {
			return "Please complete all required fields: " + missing.join(", ") + ".";
		}
		return "";
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

	function renderCompletePageContent(w) {
		var heroStep = document.querySelector(".usis-public-hero .text-primary.text-uppercase");
		var heroTitle = document.querySelector(".usis-public-hero h1");
		var heroLead = document.querySelector(".usis-public-hero .text-muted");
		var bodyP = document.querySelector("#usis-hire-complete-body");
		if (!bodyP) return;

		if (isStandardPath(w) && !standardOnboardingComplete(w)) {
			if (heroStep) heroStep.textContent = "Application submitted";
			if (heroTitle) heroTitle.textContent = "Thank you";
			if (heroLead) heroLead.textContent = "HR will review your application and may send a job offer by email.";
			if (offerPending(w)) {
				bodyP.textContent =
					"Your employment application is on file. A job offer is ready — open the Job offer step above to review and accept it.";
			} else {
				bodyP.textContent =
					"Your employment application is on file. Our HR team will review it and email you if we extend an offer. After you accept, you will complete Form I-9 and W-4 in this portal.";
			}
			return;
		}

		if (heroStep) heroStep.textContent = isStandardPath(w) ? "Onboarding complete" : "Step 5 of 5";
		if (heroTitle) heroTitle.textContent = "Thank you";
		if (heroLead) {
			heroLead.textContent = isStandardPath(w)
				? "Your application, offer acceptance, and hiring documents are on file."
				: "Your employment application and hiring documents are on file.";
		}
		bodyP.textContent =
			"Our HR team will review your submission and follow up with next steps. You may sign out below or close this window.";
	}

	function renderCompleteReviewStatus(w) {
		renderCompletePageContent(w);
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

	function setRadioValue(name, value) {
		if (!value) return;
		var el = document.querySelector('input[name="' + name + '"][value="' + value + '"]');
		if (el) el.checked = true;
	}

	function markApplicationFormDirty() {
		if (state.currentStep === "application") state.applicationFormDirty = true;
	}

	function wireApplicationFormDirtyTracking() {
		var form = document.getElementById("usis-hire-application-form");
		if (!form || form.getAttribute("data-usis-dirty-wired") === "1") return;
		form.setAttribute("data-usis-dirty-wired", "1");
		form.addEventListener("input", markApplicationFormDirty);
		form.addEventListener("change", markApplicationFormDirty);
	}

	function applyWizardToForm(w, opts) {
		opts = opts || {};
		var onApplication = state.currentStep === "application";
		var skipFormFields =
			onApplication &&
			!opts.forceForm &&
			state.applicationFormHydrated &&
			state.applicationFormDirty;
		if (onApplication && !state.applicationFormHydrated) wireApplicationFormDirtyTracking();
		var u = w.user || {};
		if (!skipFormFields) {
			var fn = document.getElementById("usis-hire-fn");
			var ln = document.getElementById("usis-hire-ln");
			var ph = document.getElementById("usis-hire-phone");
			if (fn) fn.value = u.first_name || "";
			if (ln) ln.value = u.last_name || "";
			if (ph) ph.value = u.phone || "";
		}
		var app = w.application && w.application.payload;
		if (!skipFormFields && app && typeof app === "object") {
			function v(id, key) {
				var el = document.getElementById(id);
				if (el && app[key] != null) el.value = String(app[key]);
			}
			v("usis-hire-position", "position_applying_for");
			v("usis-hire-start", "preferred_start_date");
			v("usis-hire-compensation", "desired_compensation");
			v("usis-hire-mi", "middle_initial");
			v("usis-hire-dob", "date_of_birth");
			v("usis-hire-ssn", "ssn");
			v("usis-hire-citizenship", "citizenship_status");
			v("usis-hire-filing-status", "filing_status");
			v("usis-hire-dependents", "dependents_amount");
			v("usis-hire-other-income", "other_income");
			v("usis-hire-deductions", "deductions");
			v("usis-hire-addr", "address_line1");
			v("usis-hire-addr2", "address_line2");
			v("usis-hire-city", "city");
			v("usis-hire-state", "state");
			v("usis-hire-zip", "postal_code");
			v("usis-hire-country", "country");
			v("usis-hire-edu-level", "education_level");
			v("usis-hire-edu-school", "education_school");
			v("usis-hire-edu-degree", "education_degree");
			v("usis-hire-edu-year", "education_graduation_year");
			v("usis-hire-skills", "skills_experience");
			v("usis-hire-certs", "certifications_licenses");
			v("usis-hire-ec-name", "emergency_contact_name");
			v("usis-hire-ec-phone", "emergency_contact_phone");
			v("usis-hire-ec-relationship", "emergency_contact_relationship");
			v("usis-hire-dl-number", "drivers_license_number");
			v("usis-hire-dl-state", "drivers_license_state");
			v("usis-hire-felony-explanation", "felony_explanation");
			v("usis-hire-sig-name", "signature_full_name");
			v("usis-hire-sig-date", "signature_date");
			setRadioValue("usis-hire-work-auth", app.work_authorized_us);
			setRadioValue("usis-hire-sponsorship", app.requires_sponsorship);
			setRadioValue("usis-hire-felony", app.felony_conviction);
			var sigCert = document.getElementById("usis-hire-sig-certify");
			if (sigCert) sigCert.checked = !!app.signature_certified;
			var heard = String(app.how_heard_about_position || "");
			var heardSel = document.getElementById("usis-hire-heard");
			var heardOther = document.getElementById("usis-hire-heard-other");
			var heardWrap = document.getElementById("usis-hire-heard-other-wrap");
			if (heardSel && heard) {
				var options = ["Company website", "Indeed", "LinkedIn", "Employee referral", "Job fair"];
				if (options.indexOf(heard) >= 0) {
					heardSel.value = heard;
				} else {
					heardSel.value = "Other";
					if (heardOther) heardOther.value = heard;
					if (heardWrap) heardWrap.classList.remove("d-none");
				}
			}
			if (window.USISHireApplication && window.USISHireApplication.applyEmploymentHistory) {
				window.USISHireApplication.applyEmploymentHistory(app.employment_history || app.prior_employer_summary);
			}
			if (window.USISHireApplication && window.USISHireApplication.syncConditionalFields) {
				window.USISHireApplication.syncConditionalFields();
			}
		}
		if (onApplication && !skipFormFields) state.applicationFormHydrated = true;
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
		if (window.USISHireApplicationReview && window.USISHireApplicationReview.afterWizardLoad) {
			window.USISHireApplicationReview.afterWizardLoad(w);
		}
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
				STEPS = stepsForWizard(w);
				var disc = document.getElementById("usis-hire-disclaimer");
				if (disc) disc.textContent = w.disclaimer || "";
				applyWizardToForm(w);
				showErr("");
				if (w.path_selection_required && state.currentStep !== "path") {
					var pathHref = applyStepPath("path");
					if (pathHref) {
						window.location.replace(pathHref);
						return w;
					}
				}
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
		var validationMsg = validateApplicationForm();
		if (validationMsg) {
			showErr(validationMsg);
			if (window.USISNotify) window.USISNotify.error(validationMsg);
			return Promise.reject(new Error(validationMsg));
		}
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
				state.applicationFormDirty = false;
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
		UNION_STEPS: UNION_STEPS,
		STANDARD_STEPS: STANDARD_STEPS,
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
		hirePath: hirePath,
		isStandardPath: isStandardPath,
		isUnionPath: isUnionPath,
		stepsForWizard: stepsForWizard,
		offerAccepted: offerAccepted,
		offerPending: offerPending,
		offerAvailable: offerAvailable,
		nextStepAfterApplication: nextStepAfterApplication,
		standardOnboardingComplete: standardOnboardingComplete,
		firstAllowedStepId: firstAllowedStepId,
		canAccessStep: canAccessStep,
		redirectToStep: redirectToStep,
		stepFromBody: stepFromBody,
		stepFile: stepFile,
		applyStepHref: applyStepHref,
		resumeStepUrl: resumeStepUrl,
		renderStepPrereqBanner: renderStepPrereqBanner,
		updateStepNavLocks: updateStepNavLocks,
		stepPrereqMessage: stepPrereqMessage,
		wizardReview: wizardReview,
		isWizardLocked: isWizardLocked,
		renderCompleteReviewStatus: renderCompleteReviewStatus,
		renderCompletePageContent: renderCompletePageContent,
		validateApplicationForm: validateApplicationForm,
		gatherApplicationPayload: gatherApplicationPayload,
		normalizeSsnInput: normalizeSsnInput,
		validSsn: validSsn,
	};
})();
