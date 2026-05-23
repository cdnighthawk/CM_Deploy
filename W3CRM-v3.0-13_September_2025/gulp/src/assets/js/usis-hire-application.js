(function () {
	"use strict";

	var MAX_EMPLOYERS = 4;
	var MIN_ROWS = 2;
	var rowSeq = 0;

	function escAttr(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;");
	}

	function listRoot() {
		return document.getElementById("usis-hire-employment-list");
	}

	function rowCount() {
		var root = listRoot();
		return root ? root.querySelectorAll(".usis-hire-employment-row").length : 0;
	}

	function updateEmploymentControls() {
		var addBtn = document.getElementById("usis-hire-employment-add");
		var rows = listRoot();
		if (!addBtn || !rows) return;
		addBtn.disabled = rowCount() >= MAX_EMPLOYERS;
		rows.querySelectorAll(".usis-hire-employment-remove").forEach(function (btn) {
			btn.disabled = rowCount() <= 1;
		});
	}

	function wireEmploymentRow(rowEl) {
		if (!rowEl || rowEl.getAttribute("data-usis-employment-wired") === "1") return;
		rowEl.setAttribute("data-usis-employment-wired", "1");
		var present = rowEl.querySelector(".usis-hire-employment-present");
		var endInput = rowEl.querySelector(".usis-hire-employment-end");
		if (present && endInput) {
			function syncPresent() {
				if (present.checked) {
					endInput.value = "Present";
					endInput.readOnly = true;
					endInput.classList.add("bg-light");
				} else {
					if (endInput.value === "Present") endInput.value = "";
					endInput.readOnly = false;
					endInput.classList.remove("bg-light");
				}
			}
			present.addEventListener("change", syncPresent);
			endInput.addEventListener("input", function () {
				if (endInput.value && endInput.value.toLowerCase() !== "present") {
					present.checked = false;
					endInput.readOnly = false;
					endInput.classList.remove("bg-light");
				}
			});
			syncPresent();
		}
		var removeBtn = rowEl.querySelector(".usis-hire-employment-remove");
		if (removeBtn) {
			removeBtn.addEventListener("click", function () {
				if (rowCount() <= 1) return;
				rowEl.remove();
				updateEmploymentControls();
			});
		}
		updateEmploymentControls();
	}

	function employmentRowHtml(data, index) {
		data = data || {};
		rowSeq += 1;
		var id = "usis-hire-employment-" + rowSeq;
		var presentChecked = String(data.end_date || "").toLowerCase() === "present" ? " checked" : "";
		var endVal = escAttr(data.end_date || "");
		return (
			'<div class="usis-hire-employment-row" data-employment-index="' +
			index +
			'">' +
			'<div class="d-flex justify-content-between align-items-center mb-2">' +
			'<h3 class="h6 mb-0">Previous employer ' +
			(index + 1) +
			"</h3>" +
			'<button type="button" class="btn btn-link btn-sm text-danger p-0 usis-hire-employment-remove">Remove</button>' +
			"</div>" +
			'<div class="row g-3">' +
			'<div class="col-md-6">' +
			'<label class="form-label" for="' +
			id +
			'-company">Company name</label>' +
			'<input class="form-control usis-hire-employment-company" id="' +
			id +
			'-company" value="' +
			escAttr(data.company_name) +
			'">' +
			"</div>" +
			'<div class="col-md-6">' +
			'<label class="form-label" for="' +
			id +
			'-title">Job title / Position</label>' +
			'<input class="form-control usis-hire-employment-title" id="' +
			id +
			'-title" value="' +
			escAttr(data.job_title) +
			'">' +
			"</div>" +
			'<div class="col-md-4">' +
			'<label class="form-label" for="' +
			id +
			'-start">Start date</label>' +
			'<input class="form-control usis-hire-employment-start" id="' +
			id +
			'-start" placeholder="mm/dd/yyyy" value="' +
			escAttr(data.start_date) +
			'">' +
			"</div>" +
			'<div class="col-md-4">' +
			'<label class="form-label" for="' +
			id +
			'-end">End date</label>' +
			'<input class="form-control usis-hire-employment-end" id="' +
			id +
			'-end" placeholder="mm/dd/yyyy" value="' +
			endVal +
			'">' +
			"</div>" +
			'<div class="col-md-4 d-flex align-items-end">' +
			'<div class="form-check mb-2">' +
			'<input class="form-check-input usis-hire-employment-present" type="checkbox" id="' +
			id +
			'-present"' +
			presentChecked +
			">" +
			'<label class="form-check-label" for="' +
			id +
			'-present">Currently employed here</label>' +
			"</div>" +
			"</div>" +
			'<div class="col-md-8">' +
			'<label class="form-label" for="' +
			id +
			'-reason">Reason for leaving</label>' +
			'<input class="form-control usis-hire-employment-reason" id="' +
			id +
			'-reason" placeholder="Optional" value="' +
			escAttr(data.reason_for_leaving) +
			'">' +
			"</div>" +
			'<div class="col-md-4">' +
			'<fieldset><legend class="form-label mb-2">May we contact this employer?</legend>' +
			'<div class="d-flex flex-wrap gap-3">' +
			'<div class="form-check">' +
			'<input class="form-check-input usis-hire-employment-contact" type="radio" name="' +
			id +
			'-contact" value="yes"' +
			(data.may_contact === "yes" ? " checked" : "") +
			">" +
			'<label class="form-check-label">Yes</label>' +
			"</div>" +
			'<div class="form-check">' +
			'<input class="form-check-input usis-hire-employment-contact" type="radio" name="' +
			id +
			'-contact" value="no"' +
			(data.may_contact === "no" ? " checked" : "") +
			">" +
			'<label class="form-check-label">No</label>' +
			"</div>" +
			"</div></fieldset>" +
			"</div>" +
			"</div></div>"
		);
	}

	function addEmploymentRow(data) {
		var root = listRoot();
		if (!root || rowCount() >= MAX_EMPLOYERS) return;
		var index = rowCount();
		root.insertAdjacentHTML("beforeend", employmentRowHtml(data, index));
		var row = root.lastElementChild;
		wireEmploymentRow(row);
		updateEmploymentControls();
	}

	function ensureEmploymentRows(count) {
		var root = listRoot();
		if (!root) return;
		count = Math.max(MIN_ROWS, count || MIN_ROWS);
		while (rowCount() < count) addEmploymentRow({});
		updateEmploymentControls();
	}

	function gatherEmploymentHistory() {
		var root = listRoot();
		if (!root) return [];
		var out = [];
		root.querySelectorAll(".usis-hire-employment-row").forEach(function (row) {
			function val(sel) {
				var el = row.querySelector(sel);
				return el ? String(el.value || "").trim() : "";
			}
			function contactVal() {
				var el = row.querySelector('.usis-hire-employment-contact:checked');
				return el ? String(el.value || "").trim() : "";
			}
			var present = row.querySelector(".usis-hire-employment-present");
			var endDate = val(".usis-hire-employment-end");
			if (present && present.checked) endDate = "Present";
			var entry = {
				company_name: val(".usis-hire-employment-company"),
				job_title: val(".usis-hire-employment-title"),
				start_date: val(".usis-hire-employment-start"),
				end_date: endDate,
				reason_for_leaving: val(".usis-hire-employment-reason"),
				may_contact: contactVal(),
			};
			if (entry.company_name || entry.job_title || entry.start_date || entry.end_date) {
				out.push(entry);
			}
		});
		return out.slice(0, MAX_EMPLOYERS);
	}

	function employmentRowComplete(row) {
		function val(sel) {
			var el = row.querySelector(sel);
			return el ? String(el.value || "").trim() : "";
		}
		function contactVal() {
			return row.querySelector('.usis-hire-employment-contact:checked');
		}
		var present = row.querySelector(".usis-hire-employment-present");
		var endOk = (present && present.checked) || val(".usis-hire-employment-end");
		return val(".usis-hire-employment-company") && val(".usis-hire-employment-title") && val(".usis-hire-employment-start") && endOk && contactVal();
	}

	function validateEmploymentHistory() {
		var root = listRoot();
		if (!root) return { ok: true };
		var complete = 0;
		root.querySelectorAll(".usis-hire-employment-row").forEach(function (row) {
			if (employmentRowComplete(row)) complete += 1;
		});
		if (complete >= 1) return { ok: true };
		return {
			ok: false,
			message: "Employment history (company, title, dates, and contact permission)",
		};
	}

	function applyEmploymentHistory(raw) {
		var root = listRoot();
		if (!root) return;
		root.innerHTML = "";
		rowSeq = 0;
		var rows = [];
		if (Array.isArray(raw)) {
			rows = raw;
		}
		if (!rows.length) rows = [{}, {}];
		rows.slice(0, MAX_EMPLOYERS).forEach(function (row, idx) {
			addEmploymentRow(row);
		});
		while (rowCount() < MIN_ROWS) addEmploymentRow({});
		updateEmploymentControls();
	}

	function syncConditionalFields() {
		var heard = document.getElementById("usis-hire-heard");
		var heardWrap = document.getElementById("usis-hire-heard-other-wrap");
		if (heard && heardWrap) {
			heardWrap.classList.toggle("d-none", heard.value !== "Other");
		}
		var felonyYes = document.getElementById("usis-hire-felony-yes");
		var felonyWrap = document.getElementById("usis-hire-felony-explanation-wrap");
		if (felonyWrap) {
			felonyWrap.classList.toggle("d-none", !(felonyYes && felonyYes.checked));
		}
	}

	function setDefaultSignatureDate() {
		var el = document.getElementById("usis-hire-sig-date");
		if (el && !el.value) {
			var d = new Date();
			el.value =
				d.getFullYear() +
				"-" +
				String(d.getMonth() + 1).padStart(2, "0") +
				"-" +
				String(d.getDate()).padStart(2, "0");
		}
	}

	function wireConditionalFields() {
		var heard = document.getElementById("usis-hire-heard");
		if (heard) heard.addEventListener("change", syncConditionalFields);
		document.querySelectorAll('input[name="usis-hire-felony"]').forEach(function (el) {
			el.addEventListener("change", syncConditionalFields);
		});
		syncConditionalFields();
	}

	function initEmploymentHistory() {
		var addBtn = document.getElementById("usis-hire-employment-add");
		if (addBtn) {
			addBtn.addEventListener("click", function () {
				addEmploymentRow({});
			});
		}
		if (rowCount() === 0) ensureEmploymentRows(MIN_ROWS);
	}

	function init() {
		initEmploymentHistory();
		wireConditionalFields();
		setDefaultSignatureDate();
		var country = document.getElementById("usis-hire-country");
		if (country && !country.value) country.value = "United States";

		var core = window.USISHireCore;
		if (!core) return;
		var saveBtn = document.getElementById("usis-hire-submit-app");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				core.submitApplication().catch(function (e) {
					var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : e.message || String(e);
					core.showErr(msg);
					if (window.USISNotify) window.USISNotify.error(msg);
				});
			});
		}
		core.checkSession().then(function (w) {
			if (w && core.applicationSaved(w)) {
				var ok = document.getElementById("usis-hire-app-saved-ok");
				if (ok) ok.classList.remove("d-none");
			}
			var nextStep = w ? core.nextStepAfterApplication(w) : "i9";
			var savedMsg = document.getElementById("usis-hire-app-saved-ok");
			if (savedMsg && w && core.isStandardPath(w)) {
				savedMsg.textContent =
					"Application saved — HR will review your submission. Watch your email for a job offer, or return here to check status.";
			}
			core.wireApplyNav({
				backHref: "../apply.html",
				onSaveNext: function () {
					core
						.submitApplication()
						.then(function (nw) {
							window.location.href = core.resolveApplyStepUrl(
								nw ? core.nextStepAfterApplication(nw) : nextStep,
								nw
							);
						})
						.catch(function (e) {
							var msg = core.friendlyFetchError ? core.friendlyFetchError(e) : e.message || String(e);
							core.showErr(msg);
							if (window.USISNotify) window.USISNotify.error(msg);
						});
				},
				nextHref: w && core.applicationSaved(w) ? core.applyStepHref(nextStep) : null,
			});
		});
	}

	window.USISHireApplication = {
		gatherEmploymentHistory: gatherEmploymentHistory,
		validateEmploymentHistory: validateEmploymentHistory,
		applyEmploymentHistory: applyEmploymentHistory,
		syncConditionalFields: syncConditionalFields,
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
