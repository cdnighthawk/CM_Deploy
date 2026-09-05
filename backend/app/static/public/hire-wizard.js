(function () {
	"use strict";

	var token = document.body.getAttribute("data-hire-token") || "";
	var root = document.getElementById("hire-root");
	var state = { data: null, step: 1, busy: false, error: "" };

	function api(path, opts) {
		return fetch("/api/public/hire/" + encodeURIComponent(token) + path, Object.assign({
			credentials: "same-origin",
			headers: { "Content-Type": "application/json", Accept: "application/json" }
		}, opts || {})).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || "Request failed");
				return j;
			});
		});
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function val(sel) {
		var el = root.querySelector(sel);
		return el ? el.value : "";
	}

	function checked(sel) {
		var el = root.querySelector(sel);
		return !!(el && el.checked);
	}

	function stepsBar(n) {
		var html = '<div class="steps">';
		for (var i = 1; i <= 8; i++) html += '<span class="' + (i <= n ? "on" : "") + '"></span>';
		return html + "</div>";
	}

	function field(name, label, value, type, extra) {
		type = type || "text";
		extra = extra || "";
		return '<div class="mb-2"><label class="form-label">' + esc(label) + '</label>' +
			'<input class="form-control" name="' + name + '" type="' + type + '" value="' + esc(value || "") + '" ' + extra + '></div>';
	}

	function select(name, label, value, options) {
		var opts = options.map(function (o) {
			var v = typeof o === "string" ? o : o.v;
			var t = typeof o === "string" ? o : o.t;
			return '<option value="' + esc(v) + '"' + (String(value) === String(v) ? " selected" : "") + ">" + esc(t) + "</option>";
		}).join("");
		return '<div class="mb-2"><label class="form-label">' + esc(label) + '</label><select class="form-select" name="' + name + '">' + opts + "</select></div>";
	}

	function nav(prev, nextLabel) {
		return '<div class="d-flex gap-2 mt-3">' +
			(prev ? '<button type="button" class="btn btn-outline-primary flex-fill" data-act="prev">Back</button>' : "") +
			'<button type="button" class="btn btn-primary flex-fill" data-act="next">' + esc(nextLabel || "Save & continue") + "</button></div>";
	}

	function person() {
		return (state.data && state.data.person) || {};
	}

	function renderWelcome() {
		var d = state.data || {};
		return stepsBar(1) +
			"<h1>Welcome</h1>" +
			'<p class="muted">You are joining <strong>' + esc(d.company_name) + "</strong> as <strong>" + esc(d.job_title) + "</strong>. Start date: " + esc(d.start_of_work_date) + ".</p>" +
			"<p>You will enter your information once. We fill Form W-4, Form I-9 Section 1, California DE-4, direct deposit, and California new-hire notices. You review the PDFs and sign.</p>" +
			'<p class="muted">Bring original I-9 identity and work-authorization documents on day 1. Do not upload List A/B/C here.</p>' +
			'<p class="muted">Official instructions: <a href="https://www.irs.gov/forms-pubs/about-form-w-4" target="_blank" rel="noopener">IRS W-4</a> · <a href="https://www.uscis.gov/i-9" target="_blank" rel="noopener">USCIS I-9</a> · <a href="https://edd.ca.gov/en/payroll_taxes/de_4/" target="_blank" rel="noopener">EDD DE-4</a></p>' +
			(d.send_back_note ? '<p class="err">HR note: ' + esc(d.send_back_note) + "</p>" : "") +
			nav(false, "Start");
	}

	function renderYou() {
		var p = person();
		return stepsBar(2) + "<h2>You</h2>" +
			'<p class="muted">Legal name as printed on your Social Security card.</p>' +
			field("legal_first", "Legal first name", p.legal_first, "text", "required") +
			field("legal_middle", "Middle", p.legal_middle) +
			field("legal_last", "Legal last name", p.legal_last, "text", "required") +
			field("legal_suffix", "Suffix", p.legal_suffix) +
			field("preferred_name", "Preferred / badge name", p.preferred_name) +
			field("dob", "Date of birth", p.dob, "date", "required") +
			field("ssn", "Social Security number", p.ssn, "text", 'inputmode="numeric" required') +
			field("email", "Personal email", p.email, "email", "required") +
			field("mobile", "Mobile", p.mobile, "tel") +
			field("address1", "Street", p.address1) +
			field("city", "City", p.city) +
			field("state", "State", p.state || "CA") +
			field("zip", "ZIP", p.zip) +
			field("county", "County (optional)", p.county) +
			'<div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="mailing_same" id="mailsame"' + (p.mailing_same_as_residential !== false ? " checked" : "") + '><label class="form-check-label" for="mailsame">Mailing address is the same as residential</label></div>' +
			'<div id="mailing-fields"' + (p.mailing_same_as_residential !== false ? ' class="d-none"' : "") + ">" +
			field("mailing_address1", "Mailing street", p.mailing_address1) +
			field("mailing_city", "Mailing city", p.mailing_city) +
			field("mailing_state", "Mailing state", p.mailing_state || "CA") +
			field("mailing_zip", "Mailing ZIP", p.mailing_zip) +
			"</div>" +
			(state.data.drives_for_work ? field("dl_number", "Driver's license number", p.dl_number) + field("dl_state", "DL state", p.dl_state || "CA") : "") +
			field("last_company", "Last company (optional)", p.last_company) +
			field("referred_by", "Referred by (optional)", p.referred_by) +
			nav(true);
	}

	function renderElig() {
		var i9 = (state.data && state.data.i9) || {};
		return stepsBar(3) + "<h2>Work eligibility (I-9 Section 1)</h2>" +
			'<p class="muted">Pick the status that matches Form I-9. Bring original documents on day 1 — <a href="https://www.uscis.gov/i-9-central/form-i-9-acceptable-documents" target="_blank" rel="noopener">Lists of Acceptable Documents</a>.</p>' +
			select("attestation", "I attest that I am a:", i9.attestation, [
				{ v: "", t: "Select…" },
				{ v: "us_citizen", t: "Citizen of the United States" },
				{ v: "noncitizen_national", t: "Noncitizen national of the United States" },
				{ v: "lawful_permanent_resident", t: "Lawful permanent resident" },
				{ v: "alien_authorized_to_work", t: "An alien authorized to work" }
			]) +
			field("uscis_a_number", "USCIS / A-number (if required)", i9.uscis_a_number) +
			field("i94_number", "Form I-94 number (if required)", i9.i94_number) +
			field("foreign_passport_number", "Foreign passport number (if required)", i9.foreign_passport_number) +
			field("work_until", "Authorized to work until", i9.work_until, "date") +
			nav(true);
	}

	function renderW4() {
		var w = (state.data && state.data.w4) || {};
		var wording = (state.data && state.data.w4_step_wording) || {};
		var exempt = !!w.exempt;
		return stepsBar(4) + "<h2>Federal tax (Form W-4 2026)</h2>" +
			'<p class="muted">' + esc(wording.step1c || "Complete Steps 1(c) through 4(c) using the official IRS wording. Preview updates when you save.") + "</p>" +
			select("filing_status", "Step 1(c) Filing status", w.filing_status, [
				{ v: "", t: "Select…" },
				{ v: "single_or_mfs", t: "Single or Married filing separately" },
				{ v: "mfj", t: "Married filing jointly" },
				{ v: "hoh", t: "Head of household" }
			]) +
			'<div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="exempt" id="w4ex"' + (exempt ? " checked" : "") + '><label class="form-check-label" for="w4ex">Exempt from withholding (2026 certification)</label></div>' +
			'<p class="muted">' + esc((state.data && state.data.w4_exempt_text) || "") + "</p>" +
			'<div id="w4-steps"' + (exempt ? ' class="d-none"' : "") + ">" +
			'<p class="muted">' + esc(wording.step2 || "") + "</p>" +
			'<div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="step2" id="w4s2"' + (w.step2 ? " checked" : "") + '><label class="form-check-label" for="w4s2">Step 2 — Multiple jobs or spouse works</label></div>' +
			'<p class="muted">' + esc(wording.step3 || "") + "</p>" +
			field("step3", "Step 3 — Claim dependents and other credits ($)", w.step3, "number") +
			'<p class="muted">' + esc(wording.step4a || "") + "</p>" +
			field("step4a", "Step 4(a) Other income ($)", w.step4a || w.other_income, "number") +
			'<p class="muted">' + esc(wording.step4b || "") + "</p>" +
			field("step4b", "Step 4(b) Deductions ($)", w.step4b || w.deductions, "number") +
			'<p class="muted">' + esc(wording.step4c || "") + "</p>" +
			field("step4c", "Step 4(c) Extra withholding per pay period ($)", w.step4c || w.extra_withholding, "number") +
			'<p class="muted">' + esc(wording.step5 || "") + "</p>" +
			"</div>" +
			'<p class="muted mt-2">Live preview</p><iframe class="preview-frame" title="W-4 preview" src="/api/public/hire/' + encodeURIComponent(token) + '/preview/w4"></iframe>' +
			nav(true);
	}

	function renderDe4() {
		var d = (state.data && state.data.de4) || {};
		return stepsBar(5) + "<h2>California tax (Form DE-4)</h2>" +
			'<p class="muted">California withholding is separate from your W-4. Do not copy federal elections here.</p>' +
			select("filing_status", "Filing status", d.filing_status, [
				{ v: "", t: "Select…" },
				{ v: "single", t: "Single or Married (with two or more incomes)" },
				{ v: "married", t: "Married (one income)" },
				{ v: "hoh", t: "Head of household" }
			]) +
			field("regular_allowances", "Regular withholding allowances", d.regular_allowances, "number") +
			field("additional_allowances", "Additional allowances", d.additional_allowances, "number") +
			field("extra_withholding", "Extra CA withholding per pay period ($)", d.extra_withholding, "number") +
			'<div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="exempt" id="de4ex"' + (d.exempt ? " checked" : "") + '><label class="form-check-label" for="de4ex">I claim exemption from California PIT withholding</label></div>' +
			'<iframe class="preview-frame" title="DE-4 preview" src="/api/public/hire/' + encodeURIComponent(token) + '/preview/de4"></iframe>' +
			nav(true);
	}

	function renderPay() {
		var d = (state.data && state.data.direct_deposit) || {};
		return stepsBar(6) + "<h2>Pay deposit</h2>" +
			'<div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="pay_by_check" id="pbc"' + (d.pay_by_check ? " checked" : "") + '><label class="form-check-label" for="pbc">Pay me by check instead</label></div>' +
			'<div id="bank-fields">' +
			field("bank_name", "Bank name", d.bank_name) +
			field("routing", "Routing number (9 digits)", d.routing, "text", 'inputmode="numeric"') +
			field("account", "Account number", d.account, "text", 'inputmode="numeric"') +
			select("account_type", "Account type", d.account_type, [
				{ v: "checking", t: "Checking" },
				{ v: "savings", t: "Savings" }
			]) +
			field("account_holder_name", "Account holder name", d.account_holder_name || person().legal_first) +
			'<label class="form-label">Voided check (optional)</label>' +
			'<input class="form-control mb-2" type="file" name="voided_check" accept="image/*,.pdf">' +
			(d.has_voided_check ? '<p class="muted">A voided check is already on file.</p>' : '<p class="muted">Upload a photo or PDF of a voided check, or give one to HR on day 1.</p>') +
			"</div>" +
			nav(true);
	}

	function renderEmerg() {
		var cs = (state.data && state.data.emergency_contacts) || [{}, {}];
		while (cs.length < 2) cs.push({});
		var acks = (state.data && state.data.notice_acks) || {};
		var cat = (state.data && state.data.notice_catalog) || [];
		var html = stepsBar(7) + "<h2>Emergency contacts &amp; California notices</h2>";
		cs.slice(0, 2).forEach(function (c, i) {
			html += "<h2>Contact " + (i + 1) + "</h2>" +
				field("ec" + i + "_name", "Name", c.name) +
				field("ec" + i + "_relation", "Relation", c.relation) +
				field("ec" + i + "_phone", "Phone", c.phone, "tel");
		});
		html += "<h2>Notices</h2><p class=\"muted\">Open each official pamphlet, then check that you received it.</p>";
		cat.forEach(function (n) {
			html += '<div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="n-' + n.key + '" ' + (acks[n.key] ? "checked" : "") + '>' +
				'<label class="form-check-label" for="n-' + n.key + '">' + esc(n.title) +
				' — <a href="/api/public/hire/' + encodeURIComponent(token) + "/preview/" + encodeURIComponent(n.key) + '" target="_blank">view PDF</a></label></div>';
		});
		return html + nav(true);
	}

	function renderSign() {
		var cert = (state.data && state.data.cert_text) || {};
		var keys = [
			["w4", "Form W-4", cert.w4],
			["i9", "Form I-9 Section 1", cert.i9],
			["de4", "Form DE-4", cert.de4],
			["dd_auth", "Direct deposit", cert.dd_auth],
			["notices", "California notices", cert.notices]
		];
		var html = stepsBar(8) + "<h2>Review &amp; sign</h2><p class=\"muted\">Open each PDF. Check every certification, type your legal name, and sign.</p>";
		["w4", "i9", "de4", "dd_auth", "notices"].forEach(function (k) {
			html += '<p class="mb-1"><a class="btn btn-outline-primary btn-sm w-100" href="/api/public/hire/' + encodeURIComponent(token) + "/preview/" + k + '" target="_blank">Review ' + k.toUpperCase() + "</a></p>";
		});
		keys.forEach(function (row) {
			html += '<div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="c-' + row[0] + '"><label class="form-check-label" for="c-' + row[0] + '"><strong>' + esc(row[1]) + "</strong> — " + esc(row[2] || "") + "</label></div>";
		});
		html += '<p class="muted">Under penalty of perjury, the certifications you checked are true.</p>';
		html += field("typed_legal_name", "Type your legal name", person().legal_first ? (person().legal_first + " " + (person().legal_last || "")).trim() : "");
		html += '<label class="form-label">Draw signature</label><canvas id="sig-pad"></canvas>' +
			'<button type="button" class="btn btn-sm btn-outline-secondary mt-1" data-act="clear-sig">Clear</button>' +
			nav(true, "Sign packet");
		return html;
	}

	function renderSigned() {
		return "<h1>Submitted</h1><p>Your packet is on file. Download your signed forms. HR will complete I-9 Section 2 when they examine original documents on or before day 1.</p>" +
			'<a class="btn btn-primary w-100" href="/api/public/hire/' + encodeURIComponent(token) + '/packet">Download signed packet</a>';
	}

	function collect(step) {
		if (step === 2) {
			return {
				legal_first: val('[name="legal_first"]'),
				legal_middle: val('[name="legal_middle"]'),
				legal_last: val('[name="legal_last"]'),
				legal_suffix: val('[name="legal_suffix"]'),
				preferred_name: val('[name="preferred_name"]'),
				dob: val('[name="dob"]'),
				ssn: val('[name="ssn"]'),
				email: val('[name="email"]'),
				mobile: val('[name="mobile"]'),
				address1: val('[name="address1"]'),
				city: val('[name="city"]'),
				state: val('[name="state"]'),
				zip: val('[name="zip"]'),
				county: val('[name="county"]'),
				mailing_same_as_residential: checked("#mailsame"),
				mailing_address1: val('[name="mailing_address1"]'),
				mailing_city: val('[name="mailing_city"]'),
				mailing_state: val('[name="mailing_state"]'),
				mailing_zip: val('[name="mailing_zip"]'),
				dl_number: val('[name="dl_number"]'),
				dl_state: val('[name="dl_state"]'),
				last_company: val('[name="last_company"]'),
				referred_by: val('[name="referred_by"]')
			};
		}
		if (step === 3) {
			return {
				attestation: val('[name="attestation"]'),
				uscis_a_number: val('[name="uscis_a_number"]'),
				i94_number: val('[name="i94_number"]'),
				foreign_passport_number: val('[name="foreign_passport_number"]'),
				work_until: val('[name="work_until"]')
			};
		}
		if (step === 4) {
			return {
				filing_status: val('[name="filing_status"]'),
				exempt: checked("#w4ex"),
				step2: checked("#w4s2"),
				step3: val('[name="step3"]'),
				step4a: val('[name="step4a"]'),
				step4b: val('[name="step4b"]'),
				step4c: val('[name="step4c"]')
			};
		}
		if (step === 5) {
			return {
				filing_status: val('[name="filing_status"]'),
				regular_allowances: val('[name="regular_allowances"]'),
				additional_allowances: val('[name="additional_allowances"]'),
				extra_withholding: val('[name="extra_withholding"]'),
				exempt: checked("#de4ex")
			};
		}
		if (step === 6) {
			return {
				pay_by_check: checked("#pbc"),
				bank_name: val('[name="bank_name"]'),
				routing: val('[name="routing"]'),
				account: val('[name="account"]'),
				account_type: val('[name="account_type"]'),
				account_holder_name: val('[name="account_holder_name"]')
			};
		}
		if (step === 7) {
			var acks = {};
			((state.data && state.data.notice_catalog) || []).forEach(function (n) {
				var el = root.querySelector("#n-" + n.key);
				acks[n.key] = !!(el && el.checked);
			});
			return {
				emergency_contacts: [
					{ name: val('[name="ec0_name"]'), relation: val('[name="ec0_relation"]'), phone: val('[name="ec0_phone"]') },
					{ name: val('[name="ec1_name"]'), relation: val('[name="ec1_relation"]'), phone: val('[name="ec1_phone"]') }
				],
				notice_acks: acks
			};
		}
		return {};
	}

	function render() {
		if (!root) return;
		if (!state.data) {
			root.innerHTML = "Loading…";
			return;
		}
		if (state.data.status === "closed") {
			root.innerHTML = "<h1>Packet closed</h1><p class=\"muted\">" + esc(state.data.message || "Contact HR.") + "</p>";
			return;
		}
		if (state.data.readonly || state.data.status === "signed") {
			root.innerHTML = renderSigned();
			return;
		}
		var html = "";
		if (state.step === 1) html = renderWelcome();
		else if (state.step === 2) html = renderYou();
		else if (state.step === 3) html = renderElig();
		else if (state.step === 4) html = renderW4();
		else if (state.step === 5) html = renderDe4();
		else if (state.step === 6) html = renderPay();
		else if (state.step === 7) html = renderEmerg();
		else html = renderSign();
		if (state.error) html = '<p class="err">' + esc(state.error) + "</p>" + html;
		root.innerHTML = html;
		bind();
	}

	function bindSig() {
		var c = document.getElementById("sig-pad");
		if (!c) return;
		var ctx = c.getContext("2d");
		c.width = c.offsetWidth * 2;
		c.height = 280;
		ctx.scale(2, 2);
		ctx.strokeStyle = "#1B242C";
		ctx.lineWidth = 2;
		var drawing = false;
		function pos(e) {
			var r = c.getBoundingClientRect();
			var t = e.touches ? e.touches[0] : e;
			return { x: t.clientX - r.left, y: t.clientY - r.top };
		}
		c.addEventListener("pointerdown", function (e) { drawing = true; var p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); });
		c.addEventListener("pointermove", function (e) { if (!drawing) return; var p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); });
		c.addEventListener("pointerup", function () { drawing = false; });
		c._toData = function () { return c.toDataURL("image/png"); };
		c._clear = function () { ctx.clearRect(0, 0, c.width, c.height); };
	}

	function bind() {
		root.querySelectorAll("[data-act]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var act = btn.getAttribute("data-act");
				if (act === "clear-sig") {
					var c = document.getElementById("sig-pad");
					if (c && c._clear) c._clear();
					return;
				}
				if (act === "prev") {
					state.step = Math.max(1, state.step - 1);
					state.error = "";
					render();
					return;
				}
				if (act === "next") goNext();
			});
		});
		var ex = document.getElementById("w4ex");
		if (ex) {
			ex.addEventListener("change", function () {
				var box = document.getElementById("w4-steps");
				if (box) box.classList.toggle("d-none", ex.checked);
			});
		}
		var mail = document.getElementById("mailsame");
		if (mail) {
			mail.addEventListener("change", function () {
				var box = document.getElementById("mailing-fields");
				if (box) box.classList.toggle("d-none", mail.checked);
			});
		}
		bindSig();
	}

	function uploadVoidedCheck() {
		var input = root.querySelector('[name="voided_check"]');
		if (!input || !input.files || !input.files[0]) return Promise.resolve();
		var fd = new FormData();
		fd.append("file", input.files[0]);
		return fetch("/api/public/hire/" + encodeURIComponent(token) + "/voided-check", {
			method: "POST",
			credentials: "same-origin",
			body: fd
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || "Upload failed");
				return j;
			});
		});
	}

	function goNext() {
		if (state.busy) return;
		if (state.step === 8) {
			var certs = {};
			["w4", "i9", "de4", "dd_auth", "notices"].forEach(function (k) {
				var el = document.getElementById("c-" + k);
				certs[k] = !!(el && el.checked);
			});
			var c = document.getElementById("sig-pad");
			state.busy = true;
			api("/sign", {
				method: "POST",
				body: JSON.stringify({
					certifications: certs,
					typed_legal_name: val('[name="typed_legal_name"]'),
					signature_png: c && c._toData ? c._toData() : ""
				})
			}).then(function (j) {
				state.data = j;
				state.busy = false;
				render();
			}).catch(function (e) {
				state.busy = false;
				state.error = e.message;
				render();
			});
			return;
		}
		var payload = collect(state.step);
		var body = { step: state.step };
		if (state.step === 2) body.person = payload;
		else if (state.step === 3) body.i9 = payload;
		else if (state.step === 4) body.w4 = payload;
		else if (state.step === 5) body.de4 = payload;
		else if (state.step === 6) body.direct_deposit = payload;
		else Object.assign(body, payload);
		state.busy = true;
		api("", { method: "PATCH", body: JSON.stringify(body) }).then(function (j) {
			state.data = j;
			return state.step === 6 ? uploadVoidedCheck() : Promise.resolve();
		}).then(function () {
			state.step = Math.min(8, state.step + 1);
			state.busy = false;
			state.error = "";
			render();
		}).catch(function (e) {
			state.busy = false;
			state.error = e.message;
			render();
		});
	}

	api("").then(function (j) {
		state.data = j;
		state.step = Math.min(8, Math.max(1, parseInt(j.wizard_step, 10) || 1));
		render();
	}).catch(function (e) {
		root.innerHTML = "<p class=\"err\">" + esc(e.message) + "</p>";
	});
})();
