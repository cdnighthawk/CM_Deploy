/**
 * Procore-parity Create RFI page.
 *
 * - Project picker pre-selects ``?project_id=`` query param.
 * - Lookups (Locations, Spec Sections, Cost Codes, Project Stages, Sub Jobs)
 *   load on project change.
 * - Users (Assignees / RFI Manager / Distribution / Received From) load once.
 * - Companies (Responsible Contractor) load once.
 * - "Create as Draft" + "Create as Open" footer buttons mirror Procore.
 * - "Draft with AI" modal calls /rfis/draft-assist.
 * - Attachments are queued in-page; after successful create the page posts
 *   them via /rfis/<id>/attachments.
 */
(function () {
	"use strict";

	var U = window.USIS_RFI;

	var state = {
		projectId: null,
		users: [],
		companies: [],
		customFieldDefs: [],
		configurable: [],
		assignees: [],
		distribution: [],
		queuedAttachments: [],
	};

	function $(id) { return document.getElementById(id); }

	function fillSelect(sel, items, options) {
		options = options || {};
		if (!sel) return;
		var current = sel.value;
		sel.innerHTML = "";
		if (options.allowEmpty !== false) {
			var blank = document.createElement("option");
			blank.value = "";
			blank.textContent = options.emptyLabel || "—";
			sel.appendChild(blank);
		}
		items.forEach(function (it) {
			var opt = document.createElement("option");
			opt.value = it.id;
			opt.textContent = it.label;
			sel.appendChild(opt);
		});
		if (current) sel.value = current;
	}

	function loadProjects() {
		return U.loadProjects().then(function (rows) {
			var sel = $("usis-rfi-project");
			fillSelect(sel,
				rows.map(function (p) { return { id: p.id, label: (p.number ? p.number + " · " : "") + p.name }; }),
				{ emptyLabel: "Select project…" }
			);
			var hint = U.queryParam("project_id");
			if (hint && Array.prototype.some.call(sel.options, function (o) { return o.value === hint; })) {
				sel.value = hint;
				state.projectId = hint;
			} else if (sel.options.length > 1) {
				sel.selectedIndex = 1;
				state.projectId = sel.value;
			}
		});
	}

	function loadUsersAndCompanies() {
		return Promise.all([U.loadUsers(""), U.loadCompanies("")]).then(function (results) {
			state.users = results[0] || [];
			state.companies = results[1] || [];
			var asLabel = state.users.map(function (u) { return { id: u.id, label: u.name + " · " + (u.email || "") }; });
			fillSelect($("usis-rfi-manager"), asLabel, { emptyLabel: "Select manager…" });
			fillSelect($("usis-rfi-assignee-picker"), asLabel, { emptyLabel: "Select user…" });
			fillSelect($("usis-rfi-dist-picker"), asLabel, { emptyLabel: "Select user…" });
			fillSelect($("usis-rfi-received-from"), asLabel, { emptyLabel: "—" });
			fillSelect(
				$("usis-rfi-responsible"),
				state.companies.map(function (c) { return { id: c.id, label: c.name }; }),
				{ emptyLabel: "—" }
			);
		});
	}

	function loadLookupsAndCustom() {
		if (!state.projectId) return Promise.resolve();
		var kinds = [
			["locations", "usis-rfi-location", "name"],
			["spec_sections", "usis-rfi-spec", "code"],
			["cost_codes", "usis-rfi-cost-code", "code"],
			["project_stages", "usis-rfi-stage", "name"],
			["sub_jobs", "usis-rfi-sub-job", "name"],
		];
		var tasks = kinds.map(function (k) {
			return U.loadLookup(state.projectId, k[0]).then(function (rows) {
				var formatted = rows.map(function (r) {
					var label = r[k[2]] || r.code || r.name || "(no name)";
					if (k[0] === "spec_sections" && r.title) label = r.code + " — " + r.title;
					if (k[0] === "cost_codes" && r.description) label = r.code + " — " + r.description;
					return { id: r.id, label: label };
				});
				fillSelect($(k[1]), formatted);
			}).catch(function () {});
		});
		tasks.push(loadCustomFields());
		return Promise.all(tasks);
	}

	function loadCustomFields() {
		return U.loadCustomFieldDefs().then(function (rows) {
			state.customFieldDefs = rows;
			var wrap = $("usis-rfi-custom-fields");
			if (!wrap) return;
			wrap.innerHTML = "";
			rows.forEach(function (f) {
				var col = document.createElement("div");
				col.className = "col-md-6";
				var id = "usis-rfi-cf-" + U.escAttr(f.key);
				var label = '<label class="form-label" for="' + id + '">' + U.esc(f.label) + "</label>";
				var input = "";
				if (f.field_type === "number") {
					input = '<input type="number" class="form-control form-control-sm" id="' + id + '" data-cf-id="' + U.escAttr(f.id) + '" data-cf-type="number">';
				} else if (f.field_type === "date") {
					input = '<input type="date" class="form-control form-control-sm" id="' + id + '" data-cf-id="' + U.escAttr(f.id) + '" data-cf-type="date">';
				} else if (f.field_type === "checkbox") {
					input = '<div class="form-check"><input class="form-check-input" type="checkbox" id="' + id + '" data-cf-id="' + U.escAttr(f.id) + '" data-cf-type="bool"></div>';
				} else {
					input = '<input type="text" class="form-control form-control-sm" id="' + id + '" data-cf-id="' + U.escAttr(f.id) + '" data-cf-type="text">';
				}
				col.innerHTML = label + input;
				wrap.appendChild(col);
			});
		}).catch(function () {});
	}

	function applyConfigurableFields() {
		if (!state.projectId) return Promise.resolve();
		return U.loadConfigurableFields(state.projectId).then(function (rows) {
			state.configurable = rows;
			rows.forEach(function (r) {
				var sel = "[data-field-key='" + r.field_key + "']";
				var el = document.querySelector(sel);
				if (!el) return;
				if (r.requirement === "hidden") {
					el.closest(".col-md-6, .col-md-12") && el.closest(".col-md-6, .col-md-12").classList.add("d-none");
				} else if (r.requirement === "required") {
					var lbl = el.closest(".col-md-6, .col-md-12").querySelector("label");
					if (lbl && !/\*/.test(lbl.innerText)) {
						lbl.innerHTML += '<span class="req">*</span>';
					}
				}
			});
		}).catch(function () {});
	}

	function renderAssigneeChips() {
		var wrap = $("usis-rfi-assignees-chips");
		if (!wrap) return;
		wrap.innerHTML = state.assignees.map(function (a) {
			var u = state.users.find(function (x) { return x.id === a.user_id; });
			var label = u ? (u.name || u.email) : a.user_id;
			return '<span class="usis-chip" data-uid="' + U.escAttr(a.user_id) + '">' +
				U.esc(label) + (a.is_required ? " <small>(required)</small>" : "") +
				' <span class="x" title="Remove">&times;</span></span>';
		}).join("");
		Array.prototype.forEach.call(wrap.querySelectorAll(".usis-chip .x"), function (x) {
			x.addEventListener("click", function () {
				var uid = x.parentElement.dataset.uid;
				state.assignees = state.assignees.filter(function (a) { return a.user_id !== uid; });
				renderAssigneeChips();
			});
		});
	}

	function renderDistributionChips() {
		var wrap = $("usis-rfi-dist-chips");
		if (!wrap) return;
		wrap.innerHTML = state.distribution.map(function (d) {
			var u = state.users.find(function (x) { return x.id === d.user_id; });
			var label = u ? (u.name || u.email) : d.user_id;
			return '<span class="usis-chip" data-uid="' + U.escAttr(d.user_id) + '">' +
				U.esc(label) + ' <span class="x" title="Remove">&times;</span></span>';
		}).join("");
		Array.prototype.forEach.call(wrap.querySelectorAll(".usis-chip .x"), function (x) {
			x.addEventListener("click", function () {
				var uid = x.parentElement.dataset.uid;
				state.distribution = state.distribution.filter(function (d) { return d.user_id !== uid; });
				renderDistributionChips();
			});
		});
	}

	function readCustomFields() {
		var out = [];
		Array.prototype.forEach.call(document.querySelectorAll("[data-cf-id]"), function (el) {
			var defId = el.dataset.cfId;
			var type = el.dataset.cfType;
			var v = type === "bool" ? el.checked : el.value;
			if (v === "" || v == null) return;
			if (type === "number") out.push({ field_def_id: defId, value_number: parseFloat(v) });
			else if (type === "date") out.push({ field_def_id: defId, value_date: v });
			else if (type === "bool") out.push({ field_def_id: defId, value_bool: v });
			else out.push({ field_def_id: defId, value_text: v });
		});
		return out;
	}

	function readPayload() {
		var p = {
			subject: $("usis-rfi-subject").value.trim(),
			number: $("usis-rfi-number").value || null,
			prefix: $("usis-rfi-prefix").value || null,
			rfi_manager_user_id: $("usis-rfi-manager").value || null,
			due_at: $("usis-rfi-due").value || null,
			received_from_user_id: $("usis-rfi-received-from").value || null,
			responsible_contractor_company_id: $("usis-rfi-responsible").value || null,
			drawing_number_text: $("usis-rfi-drawing-number").value || null,
			location_id: $("usis-rfi-location").value || null,
			spec_section_id: $("usis-rfi-spec").value || null,
			cost_code_id: $("usis-rfi-cost-code").value || null,
			project_stage_id: $("usis-rfi-stage").value || null,
			sub_job_id: $("usis-rfi-sub-job").value || null,
			cost_impact_choice: $("usis-rfi-cost-choice").value || null,
			cost_impact: $("usis-rfi-cost-amount").value || null,
			schedule_impact_choice: $("usis-rfi-sched-choice").value || null,
			schedule_impact_days: $("usis-rfi-sched-days").value || null,
			is_private: $("usis-rfi-private").value === "true",
			reference_text: $("usis-rfi-reference").value || null,
			general_information: $("usis-rfi-general").value || null,
			question: $("usis-rfi-question").value || null,
			assignees: state.assignees,
			distribution: state.distribution,
		};
		return p;
	}

	function postCustomFields(rfiId, fields) {
		if (!fields || !fields.length) return Promise.resolve();
		var path = "/api/v1/rfis/" + encodeURIComponent(rfiId) + "/custom-fields";
		return Promise.all(fields.map(function (f) {
			return U.fetchJson(path, { method: "POST", body: f }).catch(function () {});
		}));
	}

	function postAttachments(rfiId) {
		if (!state.queuedAttachments.length) return Promise.resolve();
		var path = "/api/v1/rfis/" + encodeURIComponent(rfiId) + "/attachments";
		return Promise.all(state.queuedAttachments.map(function (a) {
			return U.fetchJson(path, { method: "POST", body: a }).catch(function () {});
		}));
	}

	function submit(status) {
		U.flashError($("usis-rfi-error"), "");
		if (!state.projectId) { U.flashError($("usis-rfi-error"), "Choose a project."); return; }
		var payload = readPayload();
		payload.status = status;
		var customFields = readCustomFields();

		U.createRfi(state.projectId, payload).then(function (data) {
			var item = data.item || {};
			return postCustomFields(item.id, customFields).then(function () {
				return postAttachments(item.id);
			}).then(function () {
				window.location.href = "construction/rfi-detail.html?id=" + encodeURIComponent(item.id);
			});
		}).catch(function (err) {
			U.flashError($("usis-rfi-error"), err.message || String(err));
		});
	}

	function wireSubmit() {
		var draft = $("usis-rfi-btn-draft");
		var open = $("usis-rfi-btn-open");
		var send = $("usis-rfi-btn-send-review");
		if (draft) draft.addEventListener("click", function () { submit("draft"); });
		if (open) open.addEventListener("click", function () { submit("open"); });
		if (send) send.addEventListener("click", function () { submit("draft"); });
	}

	function wireAssignees() {
		var btn = $("usis-rfi-assignee-add");
		if (!btn) return;
		btn.addEventListener("click", function () {
			var uid = $("usis-rfi-assignee-picker").value;
			if (!uid) return;
			if (state.assignees.some(function (a) { return a.user_id === uid; })) return;
			state.assignees.push({
				user_id: uid,
				is_required: $("usis-rfi-assignee-required").checked,
			});
			renderAssigneeChips();
		});
	}

	function wireDistribution() {
		var btn = $("usis-rfi-dist-add");
		if (!btn) return;
		btn.addEventListener("click", function () {
			var uid = $("usis-rfi-dist-picker").value;
			if (!uid) return;
			if (state.distribution.some(function (d) { return d.user_id === uid; })) return;
			state.distribution.push({ user_id: uid });
			renderDistributionChips();
		});
	}

	function wireProjectChange() {
		var sel = $("usis-rfi-project");
		if (!sel) return;
		sel.addEventListener("change", function () {
			state.projectId = sel.value;
			loadLookupsAndCustom().then(applyConfigurableFields);
		});
	}

	function queueFiles(files) {
		Array.from(files || []).forEach(function (f) {
			// We don't have an upload endpoint yet (binary upload + storage is
			// out of scope for this phase). Stash a placeholder URL so the
			// user sees the file in the list; the create flow will POST the
			// metadata via /rfis/<id>/attachments after the RFI is saved.
			state.queuedAttachments.push({
				file_url: "pending-upload://" + f.name,
				title: f.name,
				filename: f.name,
				mime_type: f.type || null,
				file_size_bytes: f.size,
			});
		});
		renderQueuedAttachments();
	}

	function wireAttachments() {
		var input = $("usis-rfi-attach-file");
		var list = $("usis-rfi-attach-list");
		var drop = $("usis-rfi-attach-drop");
		if (!input || !list) return;
		input.addEventListener("change", function () { queueFiles(input.files); input.value = ""; });
		if (!drop) return;
		drop.addEventListener("click", function () { input.click(); });
		drop.addEventListener("keydown", function (e) {
			if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
		});
		["dragenter", "dragover"].forEach(function (evt) {
			drop.addEventListener(evt, function (e) {
				e.preventDefault();
				e.stopPropagation();
				drop.classList.add("is-drag");
			});
		});
		["dragleave", "drop"].forEach(function (evt) {
			drop.addEventListener(evt, function (e) {
				e.preventDefault();
				e.stopPropagation();
				drop.classList.remove("is-drag");
			});
		});
		drop.addEventListener("drop", function (e) {
			var files = (e.dataTransfer && e.dataTransfer.files) || [];
			if (files.length) queueFiles(files);
		});
	}

	function renderQueuedAttachments() {
		var list = $("usis-rfi-attach-list");
		if (!list) return;
		list.innerHTML = state.queuedAttachments.map(function (a, i) {
			return '<div class="d-flex align-items-center gap-2 small mb-1"><i class="fa fa-file"></i> ' +
				U.esc(a.title) + ' <a href="javascript:void(0);" class="text-danger" data-rm="' + i + '">remove</a></div>';
		}).join("");
		Array.prototype.forEach.call(list.querySelectorAll("[data-rm]"), function (a) {
			a.addEventListener("click", function () {
				state.queuedAttachments.splice(parseInt(a.dataset.rm, 10), 1);
				renderQueuedAttachments();
			});
		});
	}

	function wireAiDraft() {
		var btn = $("usis-rfi-ai-draft");
		var modal = $("usis-rfi-ai-modal");
		var go = $("usis-rfi-ai-go");
		if (btn && modal && window.bootstrap) {
			btn.addEventListener("click", function () { bootstrap.Modal.getOrCreateInstance(modal).show(); });
		}
		if (go) go.addEventListener("click", function () {
			var txt = $("usis-rfi-ai-input").value.trim();
			if (!txt) return;
			U.fetchJson("/api/v1/rfis/draft-assist", {
				method: "POST",
				body: { text: txt, project_id: state.projectId || null },
			}).then(function (data) {
				var item = data.item || {};
				if (item.subject) $("usis-rfi-subject").value = item.subject;
				if (item.question) $("usis-rfi-question").value = item.question;
				if (item.cost_impact_choice) $("usis-rfi-cost-choice").value = item.cost_impact_choice;
				if (item.schedule_impact_choice) $("usis-rfi-sched-choice").value = item.schedule_impact_choice;
				if (modal && window.bootstrap) bootstrap.Modal.getInstance(modal).hide();
			}).catch(function (err) { alert(err.message || String(err)); });
		});
	}

	function autoFillRespFromUser() {
		var rec = $("usis-rfi-received-from");
		if (!rec) return;
		rec.addEventListener("change", function () {
			// Procore behavior: prefill Responsible Contractor from Received From's company.
			// We don't have a user→company mapping yet — leave manual.
		});
	}

	function init() {
		loadProjects().then(function () {
			return Promise.all([loadUsersAndCompanies(), loadLookupsAndCustom()]);
		}).then(applyConfigurableFields);

		wireProjectChange();
		wireAssignees();
		wireDistribution();
		wireSubmit();
		wireAttachments();
		wireAiDraft();
		autoFillRespFromUser();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
