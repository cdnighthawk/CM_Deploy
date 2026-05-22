/**
 * Form W-4 field catalog, prefill merge, client validation, and form render/collect.
 */
(function (global) {
	"use strict";

	var FILING_STATUS = [
		{ value: "single", label: "Single or Married filing separately" },
		{ value: "married_joint", label: "Married filing jointly or Qualifying surviving spouse" },
		{ value: "head_of_household", label: "Head of household" },
	];

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function emptyW4() {
		return {
			first_name: "",
			middle_initial: "",
			last_name: "",
			address: "",
			city: "",
			state: "",
			zip: "",
			ssn: "",
			filing_status: "",
			multiple_jobs: false,
			higher_withholding: false,
			dependents_amount: "",
			other_income: "",
			deductions: "",
			extra_withholding: "",
			exempt_claim: false,
		};
	}

	function mergePrefill(prefill, draft) {
		var base = emptyW4();
		var p = prefill && typeof prefill === "object" ? prefill : {};
		var d = draft && typeof draft === "object" ? draft : {};
		Object.keys(base).forEach(function (k) {
			if (typeof base[k] === "boolean") {
				base[k] = d[k] != null ? !!d[k] : !!p[k];
			} else if (d[k] != null && String(d[k]).trim() !== "") {
				base[k] = d[k];
			} else if (p[k] != null && String(p[k]).trim() !== "") {
				base[k] = p[k];
			}
		});
		return base;
	}

	function validate(data) {
		var errors = [];
		var warnings = [];
		function req(key, label) {
			if (!String(data[key] || "").trim()) errors.push(label + " is required");
		}
		req("first_name", "First name");
		req("last_name", "Last name");
		req("address", "Address");
		req("city", "City");
		req("state", "State");
		req("zip", "ZIP code");
		req("ssn", "Social Security number");
		if (data.ssn && !/^\d{3}-?\d{2}-?\d{4}$/.test(String(data.ssn).replace(/\s/g, ""))) {
			errors.push("Social Security number format is invalid");
		}
		if (!data.filing_status) errors.push("Filing status is required");
		if (data.exempt_claim) {
			warnings.push(
				"You claim exemption from withholding. You must meet IRS conditions and submit a new W-4 each year by February 15."
			);
		}
		return { ok: errors.length === 0, errors: errors, warnings: warnings };
	}

	function inp(name, val, type, ro) {
		type = type || "text";
		var cls = "form-control form-control-sm" + (ro ? " bg-light" : "");
		return (
			'<input type="' +
			esc(type) +
			'" class="' +
			cls +
			'" data-w4-field="' +
			esc(name) +
			'" value="' +
			esc(val != null ? val : "") +
			'"' +
			(ro ? " readonly" : "") +
			">"
		);
	}

	function fieldRow(label, controlHtml) {
		return (
			'<div class="row g-2 mb-2 align-items-center"><div class="col-md-4"><label class="form-label small mb-0">' +
			esc(label) +
			'</label></div><div class="col-md-8">' +
			controlHtml +
			"</div></div>"
		);
	}

	function renderForm(root, data, opts) {
		if (!root) return;
		opts = opts || {};
		var locked = !!opts.locked;
		data = data || emptyW4();

		var statusRadios = FILING_STATUS.map(function (c) {
			var chk = data.filing_status === c.value ? " checked" : "";
			return (
				'<div class="form-check"><input class="form-check-input" type="radio" name="w4_filing" data-w4-field="filing_status" value="' +
						esc(c.value) +
						'"' +
						chk +
						(locked ? " disabled" : "") +
						'><label class="form-check-label small">' +
						esc(c.label) +
						"</label></div>"
			);
		}).join("");

		root.innerHTML =
			'<div class="usis-w4-form">' +
			'<p class="alert alert-info py-2 small mb-3">Digital Form W-4 for USIS onboarding. Your employer retains the official IRS W-4 for payroll. SSN is encrypted at rest.</p>' +
			'<h6 class="fw-semibold">Employee information</h6>' +
			fieldRow("First name", inp("first_name", data.first_name, "text", locked)) +
			fieldRow("Middle initial", inp("middle_initial", data.middle_initial, "text", locked)) +
			fieldRow("Last name", inp("last_name", data.last_name, "text", locked)) +
			fieldRow("Address", inp("address", data.address, "text", locked)) +
			fieldRow("City", inp("city", data.city, "text", locked)) +
			fieldRow("State", inp("state", data.state, "text", locked)) +
			fieldRow("ZIP code", inp("zip", data.zip, "text", locked)) +
			fieldRow("Social Security number", inp("ssn", data.ssn, "password", locked)) +
			'<hr class="my-3"><h6 class="fw-semibold">Step 1(c) — Filing status</h6>' +
			statusRadios +
			'<hr class="my-3"><h6 class="fw-semibold">Step 2 — Multiple jobs</h6>' +
			'<div class="form-check"><input class="form-check-input" type="checkbox" data-w4-field="multiple_jobs"' +
			(data.multiple_jobs ? " checked" : "") +
			(locked ? " disabled" : "") +
			'><label class="form-check-label small">Two jobs total, or second job wages $10,500 or less</label></div>' +
			'<div class="form-check mt-1"><input class="form-check-input" type="checkbox" data-w4-field="higher_withholding"' +
			(data.higher_withholding ? " checked" : "") +
			(locked ? " disabled" : "") +
			'><label class="form-check-label small">Married filing jointly, only one spouse works — higher withholding</label></div>' +
			'<hr class="my-3"><h6 class="fw-semibold">Steps 3–4 — Amounts (optional)</h6>' +
			fieldRow("Step 3 — Dependents amount ($)", inp("dependents_amount", data.dependents_amount, "text", locked)) +
			fieldRow("Step 4(a) — Other income ($)", inp("other_income", data.other_income, "text", locked)) +
			fieldRow("Step 4(b) — Deductions ($)", inp("deductions", data.deductions, "text", locked)) +
			fieldRow(
				"Step 4(c) — Extra withholding per pay period ($)",
				inp("extra_withholding", data.extra_withholding, "text", locked)
			) +
			'<hr class="my-3"><h6 class="fw-semibold">Exemption</h6>' +
			'<div class="form-check"><input class="form-check-input" type="checkbox" data-w4-field="exempt_claim"' +
			(data.exempt_claim ? " checked" : "") +
			(locked ? " disabled" : "") +
			'><label class="form-check-label small">I claim exemption from withholding (must meet IRS conditions)</label></div>' +
			'<div id="usis-w4-exempt-warn" class="alert alert-warning py-2 small mt-2 d-none" role="status"></div>' +
			'<hr class="my-3"><h6 class="fw-semibold">Supporting document (optional)</h6>' +
			'<p class="text-muted small">Photo of a signed paper W-4 or backup copy, if you have one.</p>' +
			'<div class="usis-w4-doc-photos border rounded p-2" data-w4-doc-slot="supporting"></div>' +
			"</div>";

		wireExemptWarn(root);
	}

	function wireExemptWarn(root) {
		var warn = root.querySelector("#usis-w4-exempt-warn");
		if (!warn) return;
		function refresh() {
			var d = collectFromForm(root);
			var v = validate(d);
			if (d.exempt_claim && v.warnings.length) {
				warn.textContent = v.warnings.join(" ");
				warn.classList.remove("d-none");
			} else {
				warn.classList.add("d-none");
			}
		}
		root.querySelectorAll("[data-w4-field]").forEach(function (el) {
			el.addEventListener("change", refresh);
			el.addEventListener("input", refresh);
		});
		refresh();
	}

	function collectFromForm(root) {
		var out = emptyW4();
		if (!root) return out;
		root.querySelectorAll("[data-w4-field]").forEach(function (el) {
			var name = el.getAttribute("data-w4-field");
			if (!name) return;
			if (el.type === "radio" && !el.checked) return;
			if (el.type === "checkbox") {
				out[name] = el.checked;
				return;
			}
			out[name] = String(el.value).trim();
		});
		return out;
	}

	function fmtSsn(val) {
		var digits = String(val || "").replace(/\D/g, "");
		if (digits.length === 9) {
			return digits.slice(0, 3) + "-" + digits.slice(3, 5) + "-" + digits.slice(5);
		}
		return String(val || "").trim() || "—";
	}

	function fmtMoney(val) {
		var s = String(val || "").trim();
		if (!s) return "0";
		return s;
	}

	function filingLabel(value) {
		for (var i = 0; i < FILING_STATUS.length; i++) {
			if (FILING_STATUS[i].value === value) return FILING_STATUS[i].label;
		}
		return value || "—";
	}

	function filledField(label, value, wide) {
		return (
			'<div class="usis-official-field' +
			(wide ? " usis-official-field-wide" : "") +
			'"><div class="usis-official-label">' +
			esc(label) +
			'</div><div class="usis-official-value">' +
			esc(value || "—") +
			"</div></div>"
		);
	}

	function filledCheck(checked, label) {
		return (
			'<div class="usis-official-check">' +
			'<span class="usis-official-checkbox' +
			(checked ? " is-checked" : "") +
			'" aria-hidden="true"></span>' +
			'<span class="usis-official-check-label">' +
			esc(label) +
			"</span></div>"
		);
	}

	function renderFilledReview(root, data, opts) {
		if (!root) return;
		opts = opts || {};
		data = data || emptyW4();
		var statusChecks = FILING_STATUS.map(function (c) {
			return filledCheck(data.filing_status === c.value, c.label);
		}).join("");
		var signatureBlock = opts.signature_png
			? '<div class="usis-official-signature"><div class="usis-official-label">Employee signature</div><img src="' +
				esc(opts.signature_png) +
				'" alt="Employee signature" class="usis-official-signature-img"><div class="usis-official-value mt-2">Date signed: ' +
				esc(opts.signed_at || "—") +
				"</div></div>"
			: '<div class="usis-official-signature usis-official-signature-pending"><div class="usis-official-label">Employee signature</div><div class="usis-official-value">Pending — sign after review</div></div>';

		root.innerHTML =
			'<div class="usis-official-form usis-w4-filled-review">' +
			'<div class="usis-official-header">' +
			'<div class="usis-official-agency">Department of the Treasury · Internal Revenue Service</div>' +
			'<div class="usis-official-title">Employee&apos;s Withholding Certificate</div>' +
			'<div class="usis-official-form-id">Form W-4 · OMB No. 1545-0074</div>' +
			"</div>" +
			'<div class="usis-official-section">' +
			'<div class="usis-official-section-title">Step 1: Enter Personal Information</div>' +
			'<div class="usis-official-row">' +
			filledField("First name and middle initial", [data.first_name, data.middle_initial].filter(Boolean).join(" ")) +
			filledField("Last name", data.last_name) +
			"</div>" +
			'<div class="usis-official-row">' +
			filledField("Address", data.address, true) +
			"</div>" +
			'<div class="usis-official-row">' +
			filledField("City or town", data.city) +
			filledField("State", data.state) +
			filledField("ZIP code", data.zip) +
			"</div>" +
			'<div class="usis-official-row">' +
			filledField("Social security number", fmtSsn(data.ssn), true) +
			"</div>" +
			'<div class="usis-official-subsection">' +
			'<div class="usis-official-label mb-2">Step 1(c): Filing status (check one)</div>' +
			statusChecks +
			"</div>" +
			"</div>" +
			'<div class="usis-official-section">' +
			'<div class="usis-official-section-title">Step 2: Multiple Jobs or Spouse Works</div>' +
			filledCheck(!!data.multiple_jobs, "Two jobs total, or second job wages $10,500 or less") +
			filledCheck(!!data.higher_withholding, "Married filing jointly, only one spouse works — higher withholding") +
			"</div>" +
			'<div class="usis-official-section">' +
			'<div class="usis-official-section-title">Step 3: Claim Dependents and Other Credits</div>' +
			'<div class="usis-official-row">' +
			filledField("Dependents amount ($)", fmtMoney(data.dependents_amount), true) +
			"</div>" +
			"</div>" +
			'<div class="usis-official-section">' +
			'<div class="usis-official-section-title">Step 4 (optional): Other Adjustments</div>' +
			'<div class="usis-official-row">' +
			filledField("4(a) Other income (not from jobs) ($)", fmtMoney(data.other_income)) +
			filledField("4(b) Deductions ($)", fmtMoney(data.deductions)) +
			"</div>" +
			'<div class="usis-official-row">' +
			filledField("4(c) Extra withholding per pay period ($)", fmtMoney(data.extra_withholding), true) +
			"</div>" +
			"</div>" +
			'<div class="usis-official-section">' +
			'<div class="usis-official-section-title">Exemption from withholding</div>' +
			filledCheck(!!data.exempt_claim, "I claim exemption from withholding for 2026 (must meet IRS conditions)") +
			"</div>" +
			signatureBlock +
			'<div class="usis-official-section">' +
			'<div class="usis-official-section-title">Supporting document (optional)</div>' +
			'<p class="usis-official-instructions mb-2">Photo of a signed paper W-4 or backup copy, if provided.</p>' +
			'<div class="usis-w4-doc-photos border rounded p-2" data-w4-doc-slot="supporting"></div>' +
			"</div>" +
			'<p class="usis-official-note">This is a filled preview of your Form W-4 based on your questionnaire answers. Your employer retains the official IRS W-4 for payroll records.</p>' +
			"</div>";
	}

	global.USISHrW4 = {
		emptyW4: emptyW4,
		mergePrefill: mergePrefill,
		validate: validate,
		renderForm: renderForm,
		renderFilledReview: renderFilledReview,
		collectFromForm: collectFromForm,
	};
})(typeof window !== "undefined" ? window : this);
