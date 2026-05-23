(function (global) {
	"use strict";

	var CITIZENSHIP_LABELS = {
		citizen: "U.S. Citizen",
		noncitizen_national: "Noncitizen national of the United States",
		lawful_permanent_resident: "Lawful permanent resident",
		alien_authorized: "Alien authorized to work",
	};

	var FILING_LABELS = {
		single: "Single or Married filing separately",
		married_joint: "Married filing jointly",
		head_of_household: "Head of household",
	};

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function summaryPairs(payload, user) {
		payload = payload || {};
		user = user || {};
		return [
			["Name", [user.first_name, payload.middle_initial, user.last_name].filter(Boolean).join(" ")],
			["Email", user.email],
			["Phone", user.phone || payload.phone],
			["Position", payload.position_applying_for],
			["Preferred start", payload.preferred_start_date],
			["Address", payload.address_line1],
			["Address line 2", payload.address_line2],
			["City / State / ZIP", [payload.city, payload.state, payload.postal_code].filter(Boolean).join(", ")],
			["Date of birth", payload.date_of_birth],
			["SSN", payload.ssn ? "•••-••-" + String(payload.ssn).slice(-4) : ""],
			["Citizenship status", CITIZENSHIP_LABELS[payload.citizenship_status] || payload.citizenship_status],
			["Filing status", FILING_LABELS[payload.filing_status] || payload.filing_status],
			["Dependents amount", payload.dependents_amount],
			["Other income", payload.other_income],
			["Deductions", payload.deductions],
			["Emergency contact", payload.emergency_contact_name],
			["Emergency phone", payload.emergency_contact_phone],
		];
	}

	function renderSummary(container, payload, user) {
		if (!container) return;
		container.innerHTML = summaryPairs(payload, user)
			.map(function (pair) {
				return (
					'<dt class="col-sm-4 text-muted">' +
					esc(pair[0]) +
					'</dt><dd class="col-sm-8 mb-2">' +
					esc(pair[1] || "—") +
					"</dd>"
				);
			})
			.join("");
	}

	global.USISHireFormMappings = {
		CITIZENSHIP_LABELS: CITIZENSHIP_LABELS,
		FILING_LABELS: FILING_LABELS,
		renderSummary: renderSummary,
	};
})(window);
