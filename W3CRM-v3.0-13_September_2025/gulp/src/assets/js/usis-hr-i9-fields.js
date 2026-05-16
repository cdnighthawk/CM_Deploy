/**
 * I-9 Section 1 field catalog, prefill merge, client validation, and form render/collect.
 */
(function (global) {
	"use strict";

	var CITIZENSHIP = [
		{ value: "citizen", label: "A citizen of the United States" },
		{ value: "noncitizen_national", label: "A noncitizen national of the United States" },
		{ value: "lawful_permanent_resident", label: "A lawful permanent resident" },
		{ value: "alien_authorized", label: "An alien authorized to work" },
	];

	/** USCIS Form I-9 acceptable documents (List A / B / C). */
	var LIST_A_DOCUMENTS = [
		{ value: "us_passport", label: "U.S. Passport" },
		{ value: "us_passport_card", label: "U.S. Passport Card" },
		{
			value: "permanent_resident_card",
			label: "Permanent Resident Card or Alien Registration Receipt Card (Form I-551)",
		},
		{
			value: "foreign_passport_i551",
			label: "Foreign passport with temporary I-551 stamp or MRIV notation",
		},
		{ value: "ead_i766", label: "Employment Authorization Document (Form I-766)" },
		{
			value: "foreign_passport_i94",
			label: "Foreign passport with Form I-94 or I-94A and work endorsement",
		},
		{
			value: "fsm_rmi_passport_i94",
			label:
				"Passport from FSM or RMI with Form I-94 or I-94A (Compact of Free Association)",
		},
		{
			value: "list_a_receipt",
			label: "Receipt for replacement of a lost, stolen, or damaged List A document",
		},
		{
			value: "i94_i551_stamp",
			label: "Form I-94 issued to lawful permanent resident with I-551 stamp and photograph",
		},
		{ value: "i94_refugee", label: 'Form I-94 with "RE" notation or refugee stamp' },
	];

	var LIST_B_DOCUMENTS = [
		{
			value: "drivers_license_state",
			label: "Driver's license or ID card issued by a U.S. state or outlying possession",
		},
		{
			value: "govt_id_card",
			label: "ID card issued by federal, state, or local government agency",
		},
		{ value: "school_id", label: "School ID card with a photograph" },
		{ value: "voters_registration", label: "Voter's registration card" },
		{ value: "military_card", label: "U.S. Military card or draft record" },
		{ value: "military_dependent_id", label: "Military dependent's ID card" },
		{ value: "coast_guard_merchant_mariner", label: "U.S. Coast Guard Merchant Mariner Card" },
		{ value: "native_american_tribal", label: "Native American tribal document" },
		{
			value: "canadian_drivers_license",
			label: "Driver's license issued by a Canadian government authority",
		},
		{ value: "school_record_under18", label: "School record or report card (under age 18)" },
		{
			value: "clinic_record_under18",
			label: "Clinic, doctor, or hospital record (under age 18)",
		},
		{
			value: "daycare_record_under18",
			label: "Day-care or nursery school record (under age 18)",
		},
		{
			value: "list_b_receipt",
			label: "Receipt for replacement of a lost, stolen, or damaged List B document",
		},
	];

	var LIST_C_DOCUMENTS = [
		{ value: "ss_card", label: "U.S. Social Security Card (unrestricted)" },
		{
			value: "birth_cert_report_dos",
			label: "Certification of report of birth (Forms DS-1350, FS-545, FS-240)",
		},
		{
			value: "birth_certificate",
			label: "Original or certified copy of U.S. birth certificate with official seal",
		},
		{ value: "native_american_tribal_c", label: "Native American tribal document" },
		{ value: "form_i197", label: "U.S. Citizen ID Card (Form I-197)" },
		{
			value: "form_i179",
			label: "Identification Card for Use of Resident Citizen in the United States (Form I-179)",
		},
		{
			value: "dhs_employment_auth",
			label: "Employment authorization document issued by the Department of Homeland Security",
		},
		{
			value: "list_c_receipt",
			label: "Receipt for replacement of a lost, stolen, or damaged List C document",
		},
	];

	var DOC_CATALOG = {
		list_a: LIST_A_DOCUMENTS,
		list_b: LIST_B_DOCUMENTS,
		list_c: LIST_C_DOCUMENTS,
	};

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function emptyDoc() {
		return { document_type: "", title: "", issuing_authority: "", number: "", expiration: "" };
	}

	function catalogFor(prefix) {
		return DOC_CATALOG[prefix] || [];
	}

	function labelForType(catalog, documentType) {
		if (!documentType) return "";
		for (var i = 0; i < catalog.length; i++) {
			if (catalog[i].value === documentType) return catalog[i].label;
		}
		return "";
	}

	function resolveDocumentType(doc, catalog) {
		if (!doc || typeof doc !== "object") return "";
		var dt = String(doc.document_type || "").trim();
		if (dt && catalog.some(function (c) { return c.value === dt; })) return dt;
		var t = String(doc.title || "").trim().toLowerCase();
		if (!t) return "";
		var j;
		for (j = 0; j < catalog.length; j++) {
			if (catalog[j].label.toLowerCase() === t || catalog[j].value === dt) return catalog[j].value;
		}
		if (t.indexOf("passport card") >= 0) return "us_passport_card";
		if (t.indexOf("passport") >= 0 && t.indexOf("foreign") < 0) return "us_passport";
		if (t.indexOf("i-551") >= 0 || t.indexOf("green card") >= 0 || t.indexOf("permanent resident") >= 0) {
			return "permanent_resident_card";
		}
		if (t.indexOf("i-766") >= 0 || t.indexOf("employment authorization") >= 0) return "ead_i766";
		if (t.indexOf("social security") >= 0) return "ss_card";
		if (t.indexOf("driver") >= 0 && t.indexOf("canad") >= 0) return "canadian_drivers_license";
		if (t.indexOf("driver") >= 0) return "drivers_license_state";
		return "__legacy__";
	}

	function normalizeDocBlock(block, catalog) {
		if (!block || typeof block !== "object") return block;
		var dt = String(block.document_type || "").trim();
		if (!dt) dt = resolveDocumentType(block, catalog);
		if (dt) block.document_type = dt;
		if (dt && dt !== "__legacy__") {
			var lbl = labelForType(catalog, dt);
			if (lbl) block.title = lbl;
		}
		return block;
	}

	function normalizeSection1Docs(data) {
		if (!data || typeof data !== "object") return data;
		["list_a", "list_b", "list_c"].forEach(function (prefix) {
			if (data[prefix] && typeof data[prefix] === "object") {
				normalizeDocBlock(data[prefix], catalogFor(prefix));
			}
		});
		return data;
	}

	function emptySection1() {
		return {
			last_name: "",
			first_name: "",
			middle_initial: "",
			other_last_names: "",
			address: "",
			apt: "",
			city: "",
			state: "",
			zip: "",
			date_of_birth: "",
			ssn: "",
			email: "",
			telephone: "",
			citizenship_status: "",
			document_choice: "",
			uscis_a_number: "",
			admission_i94: "",
			foreign_passport: "",
			work_authorization_expiration: "",
			list_a: emptyDoc(),
			list_b: emptyDoc(),
			list_c: emptyDoc(),
		};
	}

	function mergePrefill(prefill, draft) {
		var base = emptySection1();
		var p = prefill && typeof prefill === "object" ? prefill : {};
		var d = draft && typeof draft === "object" ? draft : {};
		Object.keys(base).forEach(function (k) {
			if (k === "list_a" || k === "list_b" || k === "list_c") {
				base[k] = Object.assign(emptyDoc(), p[k] || {}, d[k] || {});
				if (d[k] && typeof d[k] === "object") Object.assign(base[k], d[k]);
			} else if (d[k] != null && String(d[k]).trim() !== "") {
				base[k] = d[k];
			} else if (p[k] != null && String(p[k]).trim() !== "") {
				base[k] = p[k];
			}
		});
		normalizeSection1Docs(base);
		return base;
	}

	function validate(data) {
		var errors = [];
		function req(key, label) {
			if (!String(data[key] || "").trim()) errors.push(label + " is required");
		}
		req("last_name", "Last name");
		req("first_name", "First name");
		req("address", "Street address");
		req("city", "City");
		req("state", "State");
		req("zip", "ZIP code");
		req("date_of_birth", "Date of birth");
		req("ssn", "Social Security number");
		if (data.ssn && !/^\d{3}-?\d{2}-?\d{4}$/.test(String(data.ssn).replace(/\s/g, ""))) {
			errors.push("Social Security number format is invalid");
		}
		if (!data.citizenship_status) errors.push("Citizenship / immigration status is required");
		if (data.citizenship_status === "lawful_permanent_resident" && !String(data.uscis_a_number || "").trim()) {
			errors.push("USCIS A-Number is required");
		}
		if (data.citizenship_status === "alien_authorized") {
			if (!String(data.admission_i94 || "").trim() && !String(data.foreign_passport || "").trim()) {
				errors.push("I-94 number or foreign passport is required");
			}
			if (!String(data.work_authorization_expiration || "").trim()) {
				errors.push("Work authorization expiration is required");
			}
		}
		if (!data.document_choice) errors.push("Document choice (List A or List B + C) is required");
		function docReq(block, label, prefix) {
			if (!block || typeof block !== "object") {
				errors.push(label + ": invalid");
				return;
			}
			normalizeDocBlock(block, catalogFor(prefix));
			var dt = String(block.document_type || "").trim();
			if (!dt || dt === "__legacy__") {
				if (!String(block.title || "").trim()) errors.push(label + ": document type is required");
			}
			if (!String(block.issuing_authority || "").trim()) errors.push(label + ": issuing authority is required");
			if (!String(block.number || "").trim()) errors.push(label + ": document number is required");
		}
		if (data.document_choice === "list_a") docReq(data.list_a, "List A", "list_a");
		if (data.document_choice === "list_b_c") {
			docReq(data.list_b, "List B", "list_b");
			docReq(data.list_c, "List C", "list_c");
		}
		return { ok: errors.length === 0, errors: errors };
	}

	function inp(name, val, type, extraCls, ro) {
		type = type || "text";
		var cls = "form-control form-control-sm" + (extraCls || "") + (ro ? " bg-light" : "");
		return (
			'<input type="' +
			esc(type) +
			'" class="' +
			cls +
			'" data-i9-field="' +
			esc(name) +
			'" value="' +
			esc(val != null ? val : "") +
			'"' +
			(ro ? " readonly" : "") +
			">"
		);
	}

	function sel(name, val, options, locked, placeholder) {
		var cls = "form-select form-select-sm" + (locked ? " bg-light" : "");
		var html =
			'<select class="' +
			cls +
			'" data-i9-field="' +
			esc(name) +
			'"' +
			(locked ? " disabled" : "") +
			">";
		html +=
			'<option value="">' +
			esc(placeholder || "— Select document type —") +
			"</option>";
		(options || []).forEach(function (opt) {
			var selAttr = val === opt.value ? " selected" : "";
			html +=
				'<option value="' +
				esc(opt.value) +
				'"' +
				selAttr +
				">" +
				esc(opt.label) +
				"</option>";
		});
		html += "</select>";
		return html;
	}

	function docSelectOptions(catalog, doc) {
		var opts = catalog.slice();
		var resolved = resolveDocumentType(doc, catalog);
		if (resolved === "__legacy__" && String(doc.title || "").trim()) {
			opts.push({ value: "__legacy__", label: String(doc.title).trim() + " (previously saved)" });
		}
		return opts;
	}

	function fieldRow(label, controlHtml) {
		return (
			'<div class="row g-2 mb-2 align-items-center">' +
			'<div class="col-md-4"><label class="form-label small mb-0">' +
			esc(label) +
			"</label></div>" +
			'<div class="col-md-8">' +
			controlHtml +
			"</div></div>"
		);
	}

	function docBlock(prefix, doc, locked) {
		doc = doc || emptyDoc();
		var catalog = catalogFor(prefix);
		var docType = resolveDocumentType(doc, catalog);
		var labels = {
			list_a: "List A — Identity and employment authorization",
			list_b: "List B — Identity",
			list_c: "List C — Employment authorization",
		};
		var legacyNote =
			docType === "__legacy__"
				? '<p class="text-muted small mb-2">Your saved document description is shown below. Choose the matching USCIS document type if listed.</p>'
				: "";
		return (
			'<div class="usis-i9-doc-block border rounded p-2 mb-2">' +
			'<p class="small fw-semibold mb-2">' +
			esc(labels[prefix] || prefix) +
			"</p>" +
			legacyNote +
			fieldRow(
				"Document type",
				sel(prefix + ".document_type", docType, docSelectOptions(catalog, doc), locked)
			) +
			fieldRow("Issuing authority", inp(prefix + ".issuing_authority", doc.issuing_authority, "text", "", locked)) +
			fieldRow("Document number", inp(prefix + ".number", doc.number, "text", "", locked)) +
			fieldRow("Expiration (if any)", inp(prefix + ".expiration", doc.expiration, "text", "", locked)) +
			'<div class="usis-i9-doc-photos mt-3 pt-2 border-top" data-i9-doc-slot="' +
			esc(prefix) +
			'"></div>' +
			"</div>"
		);
	}

	function renderForm(root, data, opts) {
		if (!root) return;
		opts = opts || {};
		var locked = !!opts.locked;
		var prefillKeys = opts.prefillReadonly || [
			"last_name",
			"first_name",
			"address",
			"city",
			"state",
			"zip",
			"email",
			"telephone",
		];
		data = data || emptySection1();

		function roField(key, label, type) {
			var isRo =
				locked || (prefillKeys.indexOf(key) >= 0 && String(data[key] || "").trim() && !opts.reviewMode);
			return fieldRow(label, inp(key, data[key], type || "text", "", isRo));
		}

		var statusRadios = CITIZENSHIP.map(function (c) {
			var chk = data.citizenship_status === c.value ? " checked" : "";
			return (
				'<div class="form-check"><input class="form-check-input" type="radio" name="i9_citizenship" data-i9-field="citizenship_status" value="' +
				esc(c.value) +
				'"' +
				chk +
				(locked ? " disabled" : "") +
				'><label class="form-check-label small">' +
				esc(c.label) +
				"</label></div>"
			);
		}).join("");

		var docChoice =
			'<div class="form-check"><input class="form-check-input" type="radio" name="i9_doc_choice" data-i9-field="document_choice" value="list_a"' +
			(data.document_choice === "list_a" ? " checked" : "") +
			(locked ? " disabled" : "") +
			'><label class="form-check-label small">One List A document (establishes identity and employment authorization)</label></div>' +
			'<div class="form-check"><input class="form-check-input" type="radio" name="i9_doc_choice" data-i9-field="document_choice" value="list_b_c"' +
			(data.document_choice === "list_b_c" ? " checked" : "") +
			(locked ? " disabled" : "") +
			'><label class="form-check-label small">List B identity document + List C employment authorization document</label></div>';

		root.innerHTML =
			'<div class="usis-i9-form">' +
			'<p class="alert alert-info py-2 small mb-3">Digital I-9 Section 1 for USIS onboarding. Your employer must still retain a compliant Form I-9 per USCIS. SSN and ID numbers are encrypted at rest.</p>' +
			'<h6 class="fw-semibold">Section 1 — Employee information</h6>' +
			'<p class="text-muted small">From your application (edit only if incorrect)</p>' +
			roField("last_name", "Last name (family name)") +
			roField("first_name", "First name (given name)") +
			fieldRow("Middle initial", inp("middle_initial", data.middle_initial, "text", "", locked)) +
			fieldRow("Other last names used", inp("other_last_names", data.other_last_names, "text", "", locked)) +
			roField("address", "Address (street number and name)") +
			fieldRow("Apt / unit", inp("apt", data.apt, "text", "", locked)) +
			roField("city", "City or town") +
			roField("state", "State") +
			roField("zip", "ZIP code") +
			fieldRow("Date of birth", inp("date_of_birth", data.date_of_birth, "date", "", locked)) +
			fieldRow("U.S. Social Security number", inp("ssn", data.ssn, "password", "", locked)) +
			roField("email", "Email address") +
			roField("telephone", "Telephone number") +
			'<hr class="my-3"><h6 class="fw-semibold">Citizenship / immigration status</h6>' +
			statusRadios +
			'<div class="i9-conditional i9-lpn-extra mt-2" style="display:none">' +
			fieldRow("USCIS A-Number", inp("uscis_a_number", data.uscis_a_number, "text", "", locked)) +
			"</div>" +
			'<div class="i9-conditional i9-alien-extra mt-2" style="display:none">' +
			fieldRow("Form I-94 admission number", inp("admission_i94", data.admission_i94, "text", "", locked)) +
			fieldRow("Foreign passport number and country", inp("foreign_passport", data.foreign_passport, "text", "", locked)) +
			fieldRow("Work authorization expiration", inp("work_authorization_expiration", data.work_authorization_expiration, "date", "", locked)) +
			"</div>" +
			'<hr class="my-3"><h6 class="fw-semibold">Identity and employment authorization documents</h6>' +
			'<p class="text-muted small mb-2">Select the document(s) you will present for Section 2 verification, then enter issuing authority and document number.</p>' +
			docChoice +
			'<div class="i9-conditional i9-list-a mt-2" style="display:none">' +
			docBlock("list_a", data.list_a, locked) +
			"</div>" +
			'<div class="i9-conditional i9-list-bc mt-2" style="display:none">' +
			docBlock("list_b", data.list_b, locked) +
			docBlock("list_c", data.list_c, locked) +
			"</div></div>";

		wireConditionals(root);
	}

	function wireConditionals(root) {
		function refresh() {
			var data = collectFromForm(root);
			var st = data.citizenship_status;
			var dc = data.document_choice;
			var lpn = root.querySelector(".i9-lpn-extra");
			var alien = root.querySelector(".i9-alien-extra");
			var la = root.querySelector(".i9-list-a");
			var lbc = root.querySelector(".i9-list-bc");
			if (lpn) lpn.style.display = st === "lawful_permanent_resident" ? "" : "none";
			if (alien) alien.style.display = st === "alien_authorized" ? "" : "none";
			if (la) la.style.display = dc === "list_a" ? "" : "none";
			if (lbc) lbc.style.display = dc === "list_b_c" ? "" : "none";
		}
		root.querySelectorAll("[data-i9-field]").forEach(function (el) {
			el.addEventListener("change", refresh);
			el.addEventListener("input", refresh);
		});
		refresh();
	}

	function collectFromForm(root) {
		var out = emptySection1();
		if (!root) return out;
		root.querySelectorAll("[data-i9-field]").forEach(function (el) {
			var name = el.getAttribute("data-i9-field");
			if (!name) return;
			if (el.type === "radio" && !el.checked) return;
			var val = el.value;
			if (name.indexOf(".") >= 0) {
				var parts = name.split(".");
				if (!out[parts[0]]) out[parts[0]] = emptyDoc();
				out[parts[0]][parts[1]] = String(val).trim();
			} else {
				out[name] = String(val).trim();
			}
		});
		return normalizeSection1Docs(out);
	}

	global.USISHrI9 = {
		emptySection1: emptySection1,
		mergePrefill: mergePrefill,
		validate: validate,
		renderForm: renderForm,
		collectFromForm: collectFromForm,
		wireConditionals: wireConditionals,
	};
})(typeof window !== "undefined" ? window : this);
