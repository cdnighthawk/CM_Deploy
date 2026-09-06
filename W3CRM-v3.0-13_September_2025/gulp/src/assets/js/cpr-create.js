/**
 * Change Proposal Request create / detail.
 * Query: project_id (required). id = existing CPR (GET + PATCH). Else POST.
 */
(function () {
	"use strict";

	var ORIGINS = [
		{ value: "tm_ticket", label: "T&M ticket" },
		{ value: "rfi", label: "RFI" },
		{ value: "field_condition", label: "Field condition" },
		{ value: "gc_request", label: "GC request" },
		{ value: "other", label: "Other" },
	];

	var STATUSES = [
		{ value: "draft", label: "Draft" },
		{ value: "submitted", label: "Submitted" },
		{ value: "under_review", label: "Under review" },
		{ value: "accepted", label: "Accepted" },
		{ value: "rejected", label: "Rejected" },
		{ value: "converted", label: "Converted" },
		{ value: "void", label: "Void" },
	];

	var CONVERTIBLE = { accepted: true, under_review: true };

	var state = {
		projectId: "",
		cprId: "",
		lines: null,
		busy: false,
		item: null,
	};

	function $(id) {
		return document.getElementById(id);
	}

	function queryParam(name) {
		try {
			return new URLSearchParams(window.location.search).get(name) || "";
		} catch (e) {
			return "";
		}
	}

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(
			function (res) {
				return res.text().then(function (t) {
					if (!res.ok) {
						var err = new Error(res.status + " " + (t || res.statusText));
						err.status = res.status;
						err.body = t;
						throw err;
					}
					return t ? JSON.parse(t) : null;
				});
			}
		);
	}

	function currentProjectId() {
		var fromQuery = (queryParam("project_id") || queryParam("projectId") || "").trim();
		if (fromQuery) return fromQuery;
		if (window.USISProjectContext && typeof window.USISProjectContext.getProjectId === "function") {
			var fromCtx = window.USISProjectContext.getProjectId();
			if (fromCtx) return String(fromCtx).trim();
		}
		try {
			return (window.sessionStorage.getItem("usis.activeProjectId") || "").trim();
		} catch (e) {
			return "";
		}
	}

	function rememberProject(projectId) {
		if (!projectId) return;
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(projectId);
		}
	}

	function contractHref(pid) {
		var id = pid || state.projectId;
		if (!id) return "construction/project-detail.html?tab=contract";
		return "construction/project-detail.html?id=" + encodeURIComponent(id) + "&tab=contract";
	}

	function pidPath(suffix) {
		return "/api/v1/projects/" + encodeURIComponent(state.projectId) + suffix;
	}

	function setErr(msg) {
		var el = $("usis-cpr-error");
		if (!el) return;
		if (msg) {
			el.textContent = String(msg);
			el.classList.remove("d-none");
			try {
				el.scrollIntoView({ behavior: "smooth", block: "center" });
			} catch (e) {}
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function errMessage(err) {
		if (!err) return "Request failed.";
		var body = err.body;
		if (typeof body === "string") {
			try {
				body = JSON.parse(body);
			} catch (e) {}
		}
		if (body && typeof body === "object") {
			return body.error || body.message || err.message || "Request failed.";
		}
		if (typeof body === "string" && body.trim()) return body.trim();
		return err.message || "Request failed.";
	}

	function todayIso() {
		var d = new Date();
		return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
	}

	function dateInputValue(raw) {
		if (!raw) return "";
		return String(raw).slice(0, 10);
	}

	function fillStaticSelects() {
		var origin = $("usis-cpr-origin");
		if (origin && !origin.options.length) {
			ORIGINS.forEach(function (o) {
				var opt = document.createElement("option");
				opt.value = o.value;
				opt.textContent = o.label;
				origin.appendChild(opt);
			});
			origin.value = "other";
		}
		var status = $("usis-cpr-status");
		if (status && !status.options.length) {
			STATUSES.forEach(function (o) {
				var opt = document.createElement("option");
				opt.value = o.value;
				opt.textContent = o.label;
				status.appendChild(opt);
			});
			status.value = "draft";
		}
	}

	function setTitle(isDetail, number, subject) {
		var createLabel = "New Change Proposal Request";
		var detailLabel = number ? "CPR " + number : subject ? subject : "Change Proposal Request";
		var label = isDetail ? detailLabel : createLabel;
		var titleEl = $("usis-cpr-page-title");
		if (titleEl) titleEl.textContent = label;
		var crumb = $("usis-cpr-crumb-title");
		if (crumb) crumb.textContent = label;
		var crumbActive = document.querySelector(".page-title .breadcrumb-item.active span");
		if (crumbActive) crumbActive.textContent = label;
		var h1Crumb = document.querySelector(".page-title .breadcrumb li h1");
		if (h1Crumb) h1Crumb.textContent = label;
		if (document.title) document.title = label + " · USIS";
	}

	function syncConvertButton(item) {
		var wrap = $("usis-cpr-convert-wrap");
		var btn = $("usis-cpr-convert");
		var note = $("usis-cpr-prime-co-note");
		var isDetail = !!(state.cprId || (item && item.id));
		if (wrap) wrap.classList.toggle("d-none", !isDetail);
		var status = item && item.status ? String(item.status) : ($("usis-cpr-status") && $("usis-cpr-status").value) || "";
		var canConvert = isDetail && !!CONVERTIBLE[status];
		if (btn) {
			btn.disabled = !canConvert;
			btn.setAttribute(
				"title",
				canConvert
					? "Create a Prime CO from this CPR. Contract value does not change."
					: "Enabled when status is Accepted or Under review."
			);
		}
		if (note) {
			if (item && item.prime_co_number) {
				note.textContent = "Prime CO " + item.prime_co_number + " is linked. Convert does not move contract value.";
				note.classList.remove("d-none");
			} else {
				note.textContent = "";
				note.classList.add("d-none");
			}
		}
	}

	function ensureCompanyOption(sel, companyId, name) {
		if (!sel || !companyId) return;
		var found = false;
		Array.prototype.forEach.call(sel.options, function (o) {
			if (o.value === companyId) found = true;
		});
		if (!found) {
			var opt = document.createElement("option");
			opt.value = companyId;
			opt.textContent = name || "Selected company";
			sel.appendChild(opt);
		}
		sel.value = companyId;
	}

	function loadCompanies(selectedId, selectedName) {
		var sel = $("usis-cpr-company");
		if (!sel || !state.projectId) return Promise.resolve();
		return fetchJson(pidPath("/directory/companies?all=1"))
			.then(function (data) {
				var items = (data && data.items) || [];
				var seen = {};
				sel.innerHTML = "";
				var blank = document.createElement("option");
				blank.value = "";
				blank.textContent = "—";
				sel.appendChild(blank);
				items.forEach(function (it) {
					var cid = it.company_id || it.id;
					if (!cid || seen[cid]) return;
					seen[cid] = true;
					var opt = document.createElement("option");
					opt.value = cid;
					opt.textContent = it.name || cid;
					sel.appendChild(opt);
				});
				if (selectedId) ensureCompanyOption(sel, selectedId, selectedName);
			})
			.catch(function (err) {
				setErr(errMessage(err) || "Could not load project directory.");
			});
	}

	function bindLines() {
		if (!window.USISDocumentLines || typeof window.USISDocumentLines.bind !== "function") {
			setErr("Line grid failed to load.");
			return;
		}
		state.lines = window.USISDocumentLines.bind({
			tbody: "usis-doc-lines",
			addBtn: "usis-doc-line-add",
			totalEl: "usis-doc-total",
			minRows: 1,
		});
		state.lines.load([]);
	}

	function collectPayload() {
		var subject = (($("usis-cpr-subject") && $("usis-cpr-subject").value) || "").trim();
		var origin = (($("usis-cpr-origin") && $("usis-cpr-origin").value) || "").trim();
		var status = (($("usis-cpr-status") && $("usis-cpr-status").value) || "").trim();
		var items = state.lines ? state.lines.collect() : [];
		if (!subject) return { error: "Subject is required." };
		if (!origin) return { error: "Origin is required." };
		if (!status) return { error: "Status is required." };
		if (!items.length) return { error: "Add at least one line with a description." };
		var body = {
			subject: subject,
			origin: origin,
			status: status,
			notes: (($("usis-cpr-notes") && $("usis-cpr-notes").value) || "").trim(),
			needed_by_date: (($("usis-cpr-needed-by") && $("usis-cpr-needed-by").value) || "").trim() || null,
			impacted_company_id: (($("usis-cpr-company") && $("usis-cpr-company").value) || "").trim() || null,
			items: items.map(function (row) {
				return {
					description: row.description,
					quantity: row.quantity,
					unit: row.unit,
					unit_price: row.unit_price,
					sort_order: row.sort_order,
				};
			}),
		};
		var statusDate = (($("usis-cpr-status-date") && $("usis-cpr-status-date").value) || "").trim();
		if (statusDate) body.status_date = statusDate;
		return { body: body };
	}

	function applyItem(item) {
		if (!item) return;
		state.item = item;
		state.cprId = item.id || state.cprId;
		if (item.project_id && !state.projectId) state.projectId = item.project_id;
		var subject = $("usis-cpr-subject");
		if (subject) subject.value = item.subject || item.title || "";
		var origin = $("usis-cpr-origin");
		if (origin) origin.value = item.origin || "other";
		var status = $("usis-cpr-status");
		if (status) status.value = item.status || "draft";
		var statusDate = $("usis-cpr-status-date");
		if (statusDate) statusDate.value = dateInputValue(item.status_date);
		var needed = $("usis-cpr-needed-by");
		if (needed) needed.value = dateInputValue(item.needed_by_date || item.response_due_date);
		var notes = $("usis-cpr-notes");
		if (notes) notes.value = item.notes || "";
		var number = $("usis-cpr-number");
		if (number) number.value = item.number || "";
		var company = $("usis-cpr-company");
		if (company && item.impacted_company_id) {
			ensureCompanyOption(company, item.impacted_company_id, item.impacted_company_name);
		}
		if (state.lines) state.lines.load(item.items && item.items.length ? item.items : [{}]);
		setTitle(true, item.number, item.subject || item.title);
		syncConvertButton(item);
	}

	function setBusy(on) {
		state.busy = !!on;
		["usis-cpr-save", "usis-cpr-save-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.disabled = !!on;
		});
		if (!on) syncConvertButton(state.item);
		else {
			var convert = $("usis-cpr-convert");
			if (convert) convert.disabled = true;
		}
	}

	function save() {
		if (state.busy) return;
		setErr("");
		if (!state.projectId) {
			setErr("Missing project_id. Open this page from Contract admin.");
			return;
		}
		var packed = collectPayload();
		if (packed.error) {
			setErr(packed.error);
			return;
		}
		var isPatch = !!state.cprId;
		var path = isPatch ? pidPath("/cprs/" + encodeURIComponent(state.cprId)) : pidPath("/cprs");
		setBusy(true);
		fetchJson(path, { method: isPatch ? "PATCH" : "POST", body: packed.body })
			.then(function () {
				window.location.href = contractHref(state.projectId);
			})
			.catch(function (err) {
				setBusy(false);
				setErr(errMessage(err));
			});
	}

	function convertToPrimeCo() {
		if (state.busy) return;
		setErr("");
		if (!state.projectId || !state.cprId) {
			setErr("Save this CPR before converting.");
			return;
		}
		var status = (state.item && state.item.status) || ($("usis-cpr-status") && $("usis-cpr-status").value) || "";
		if (!CONVERTIBLE[status]) {
			setErr("Convert is available when status is Accepted or Under review.");
			return;
		}
		setBusy(true);
		fetchJson(pidPath("/cprs/" + encodeURIComponent(state.cprId) + "/convert-to-prime-co"), { method: "POST", body: {} })
			.then(function (data) {
				var co = data && (data.item || data.change_order || data.prime_co);
				var newId = co && co.id;
				if (!newId) {
					setBusy(false);
					setErr("Convert did not return a Prime CO id.");
					return;
				}
				window.location.href =
					"construction/prime-co-create.html?project_id=" +
					encodeURIComponent(state.projectId) +
					"&id=" +
					encodeURIComponent(newId);
			})
			.catch(function (err) {
				setBusy(false);
				setErr(errMessage(err));
			});
	}

	function wire() {
		var form = $("usis-cpr-form");
		if (form) {
			form.addEventListener("submit", function (e) {
				e.preventDefault();
				save();
			});
		}
		["usis-cpr-save", "usis-cpr-save-footer"].forEach(function (id) {
			var btn = $(id);
			if (btn) btn.addEventListener("click", save);
		});
		var convert = $("usis-cpr-convert");
		if (convert) convert.addEventListener("click", convertToPrimeCo);
		var status = $("usis-cpr-status");
		if (status) {
			status.addEventListener("change", function () {
				var dateEl = $("usis-cpr-status-date");
				if (dateEl && !dateEl.value) dateEl.value = todayIso();
				syncConvertButton(
					Object.assign({}, state.item || {}, {
						status: status.value,
						prime_co_number: state.item && state.item.prime_co_number,
					})
				);
			});
		}
		[ $("usis-cpr-cancel"), $("usis-cpr-cancel-footer") ].forEach(function (el) {
			if (!el) return;
			el.setAttribute("href", contractHref(state.projectId));
		});
	}

	function boot() {
		state.projectId = currentProjectId();
		state.cprId = (queryParam("id") || queryParam("cpr_id") || "").trim();
		rememberProject(state.projectId);
		fillStaticSelects();
		bindLines();
		wire();
		setTitle(!!state.cprId, "", "");
		syncConvertButton(null);

		if (!state.projectId) {
			setErr("Missing project_id. Open this page from a project Contract tab.");
			return;
		}

		var companies = loadCompanies();
		if (state.cprId) {
			companies
				.then(function () {
					return fetchJson(pidPath("/cprs/" + encodeURIComponent(state.cprId)));
				})
				.then(function (data) {
					applyItem((data && data.item) || data);
				})
				.catch(function (err) {
					setErr(errMessage(err) || "Could not load this CPR.");
				});
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
})();
