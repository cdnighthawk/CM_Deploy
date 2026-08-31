/**
 * Procore-parity Create RFI page.
 *
 * - Project picker pre-selects ``?project_id=`` query param.
 * - Project detail prefills prefix, GC contractor, location/stage/sub-job,
 *   RFI manager, reference, and general information. Query params
 *   (subject, question, drawing/sheet, spec, cost code, impacts) win first.
 * - Lookups (Locations, Spec Sections, Cost Codes, Project Stages, Sub Jobs)
 *   load on project change.
 * - Users (Assignees / RFI Manager / Distribution / Received From) load once.
 * - Companies (Responsible Contractor) load once.
 * - "Create as Draft" + "Create as Open" footer buttons mirror Procore.
 * - "Draft with AI" modal calls /rfis/draft-assist.
 * - Attachments: files are uploaded after create via ``POST /rfis/<id>/attachments/upload``.
 */
(function () {
	"use strict";

	var U = window.USIS_RFI;

	var state = {
		projectId: null,
		projectItem: null,
		users: [],
		companies: [],
		lookups: {},
		customFieldDefs: [],
		configurable: [],
		assignees: [],
		distribution: [],
		queuedFiles: [],
	};

	function $(id) { return document.getElementById(id); }

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	function fillSelect(sel, items, options) {
		options = options || {};
		if (!sel) return;
		var current = sel.value;
		sel.innerHTML = "";
		if (options.allowEmpty !== false) {
			var blank = document.createElement("option");
			blank.value = "";
			blank.textContent = t(options.emptyLabel || "—");
			if (options.emptyLabel) blank.setAttribute("data-i18n", options.emptyLabel);
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

	function currentLeadHint() {
		return U.queryParam("lead_id") || U.queryParam("leadId");
	}

	function ensureLeadWorkspace(leadId) {
		if (!leadId) return Promise.resolve(null);
		return U.fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(leadId) + "/ensure-project", {
			method: "POST",
			body: {},
		}).then(function (data) {
			var next = (data && data.item) || {};
			return (data && data.project_id) || next.project_id || next.drawing_project_id || null;
		}).catch(function () {
			return null;
		});
	}

	function currentProjectHint() {
		var fromQuery = U.queryParam("project_id") || U.queryParam("projectId");
		if (fromQuery) return fromQuery;
		if (window.USISProjectContext && typeof window.USISProjectContext.getProjectId === "function") {
			var fromCtx = window.USISProjectContext.getProjectId();
			if (fromCtx) return fromCtx;
		}
		try {
			return window.sessionStorage.getItem("usis.activeProjectId") || null;
		} catch (e) {
			return null;
		}
	}

	function rememberProject(projectId) {
		if (!projectId) return;
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(projectId);
		}
	}

	function sameId(a, b) {
		return U.sameId ? U.sameId(a, b) : String(a || "").toLowerCase() === String(b || "").toLowerCase();
	}

	function dash(s) {
		if (s == null || String(s).trim() === "") return "—";
		return String(s).trim();
	}

	function formatProjectAddress(item) {
		if (!item) return "—";
		var street = [item.address_line1, item.address_line2].filter(Boolean).join(", ");
		var cityLine = [item.city, item.state, item.postal_code].filter(Boolean).join(" ");
		if (item.country && item.country !== "US") {
			cityLine = (cityLine ? cityLine + ", " : "") + item.country;
		}
		var parts = [street, cityLine].filter(Boolean);
		return parts.length ? parts.join(" · ") : "—";
	}

	function formatTypeStatus(item) {
		if (!item) return "—";
		var bits = [item.project_type, item.status].filter(function (x) {
			return x && String(x).trim();
		});
		return bits.length ? bits.join(" · ") : "—";
	}

	function setText(id, value) {
		var el = $(id);
		if (el) el.textContent = value;
	}

	function renderProjectCard(item) {
		var card = $("usis-rfi-project-card");
		if (!card) return;
		if (!item) {
			card.classList.add("d-none");
			return;
		}
		setText("usis-rfi-proj-number", dash(item.number));
		setText("usis-rfi-proj-name", dash(item.name));
		setText("usis-rfi-proj-type-status", formatTypeStatus(item));
		setText("usis-rfi-proj-address", formatProjectAddress(item));
		setText("usis-rfi-proj-owner", dash(item.owner_company_name));
		setText("usis-rfi-proj-gc", dash(item.gc_company_name));
		setText("usis-rfi-proj-architect", dash(item.architect_company_name));
		setText("usis-rfi-proj-contract", item.contract_value != null ? U.fmtMoney(item.contract_value) : "—");
		setText("usis-rfi-proj-start", item.start_date ? U.fmtDate(item.start_date) : "—");
		card.classList.remove("d-none");
	}

	function selectProjectOption(sel, projectId) {
		if (!sel || !projectId) return false;
		var matched = false;
		Array.prototype.forEach.call(sel.options, function (o) {
			if (sameId(o.value, projectId)) {
				sel.value = o.value;
				matched = true;
			}
		});
		return matched;
	}

	function ensureProjectOption(sel, item, projectId) {
		if (!sel) return;
		var id = (item && item.id) || projectId;
		if (!id) return;
		if (!selectProjectOption(sel, id)) {
			var opt = document.createElement("option");
			opt.value = id;
			opt.textContent = ((item && item.number) ? item.number + " · " : "") + ((item && item.name) || "Current project");
			sel.appendChild(opt);
			sel.value = id;
		}
	}

	function syncProjectQuery(projectId) {
		if (!projectId || !window.history || !window.history.replaceState) return;
		try {
			var u = new URL(window.location.href);
			if (sameId(u.searchParams.get("project_id"), projectId)) return;
			u.searchParams.set("project_id", projectId);
			window.history.replaceState({}, "", u.pathname + u.search + u.hash);
		} catch (e) {}
	}

	function currentActorUserId() {
		try {
			return window.localStorage.getItem("usisActorUserId") || null;
		} catch (e) {
			return null;
		}
	}

	function selectIfEmpty(sel, raw) {
		if (!sel || sel.value) return false;
		return selectByIdOrLabel(sel, raw);
	}

	function setInputIfEmpty(el, value) {
		if (!el || value == null) return false;
		var next = String(value).trim();
		if (!next || String(el.value || "").trim()) return false;
		el.value = next;
		return true;
	}

	function selectByIdOrLabel(sel, raw) {
		if (!sel || raw == null || String(raw).trim() === "") return false;
		var want = String(raw).trim();
		if (selectProjectOption(sel, want)) return true;
		var lower = want.toLowerCase();
		var matched = false;
		Array.prototype.forEach.call(sel.options, function (o) {
			if (matched || !o.value) return;
			var label = (o.textContent || "").trim().toLowerCase();
			if (
				label === lower ||
				label.indexOf(lower + " —") === 0 ||
				label.indexOf(lower + " ·") === 0 ||
				label.indexOf(lower + " -") === 0
			) {
				sel.value = o.value;
				matched = true;
			}
		});
		return matched;
	}

	function firstRealOptionValue(sel) {
		if (!sel) return "";
		var values = [];
		Array.prototype.forEach.call(sel.options, function (o) {
			if (o.value) values.push(o.value);
		});
		return values.length === 1 ? values[0] : "";
	}

	function firstQueryValue(names) {
		for (var i = 0; i < names.length; i++) {
			var v = U.queryParam(names[i]);
			if (v != null && String(v).trim() !== "") return String(v).trim();
		}
		return "";
	}

	function applyQueryPrefill() {
		setInputIfEmpty($("usis-rfi-subject"), firstQueryValue(["subject"]));
		setInputIfEmpty($("usis-rfi-question"), firstQueryValue(["question"]));
		setInputIfEmpty(
			$("usis-rfi-drawing-number"),
			firstQueryValue(["drawing_number", "drawing", "sheet", "sheet_number"])
		);
		setInputIfEmpty($("usis-rfi-reference"), firstQueryValue(["reference", "trade"]));
		setInputIfEmpty($("usis-rfi-general"), firstQueryValue(["general", "general_information"]));
		setInputIfEmpty($("usis-rfi-prefix"), firstQueryValue(["prefix"]));
		selectIfEmpty($("usis-rfi-spec"), firstQueryValue(["spec_section_id", "spec_section", "spec"]));
		selectIfEmpty($("usis-rfi-location"), firstQueryValue(["location_id", "location"]));
		selectIfEmpty($("usis-rfi-cost-code"), firstQueryValue(["cost_code_id", "cost_code"]));
		selectIfEmpty($("usis-rfi-stage"), firstQueryValue(["project_stage_id", "project_stage", "stage"]));
		selectIfEmpty($("usis-rfi-sub-job"), firstQueryValue(["sub_job_id", "sub_job"]));
		selectIfEmpty($("usis-rfi-manager"), firstQueryValue(["rfi_manager_user_id", "rfi_manager", "manager"]));
		selectIfEmpty(
			$("usis-rfi-received-from"),
			firstQueryValue(["received_from_user_id", "received_from"])
		);
		selectIfEmpty($("usis-rfi-responsible"), firstQueryValue(["responsible_contractor_company_id", "responsible"]));

		var costAmt = firstQueryValue(["cost_impact"]);
		var costChoice = $("usis-rfi-cost-choice");
		var costInput = $("usis-rfi-cost-amount");
		if (costAmt && costChoice && !costChoice.value) {
			if (/^(yes|yes_unknown|no|tbd|na)$/i.test(costAmt)) {
				costChoice.value = costAmt.toLowerCase();
			} else if (!isNaN(Number(costAmt))) {
				costChoice.value = "yes";
				setInputIfEmpty(costInput, costAmt);
			}
		}
		var schedDays = firstQueryValue(["schedule_impact_days"]);
		var schedChoice = $("usis-rfi-sched-choice");
		var schedInput = $("usis-rfi-sched-days");
		if (schedDays && schedChoice && !schedChoice.value) {
			if (/^(yes|yes_unknown|no|tbd|na)$/i.test(schedDays)) {
				schedChoice.value = schedDays.toLowerCase();
			} else if (!isNaN(Number(schedDays))) {
				schedChoice.value = "yes";
				setInputIfEmpty(schedInput, schedDays);
			}
		}
	}

	function prefillResponsibleContractor(item) {
		var sel = $("usis-rfi-responsible");
		if (!sel || !item || sel.value) return;
		var gcId = item.gc_company_id || "";
		if (gcId && selectProjectOption(sel, gcId)) return;
		var gcName = (item.gc_company_name || "").trim();
		if (gcName) selectByIdOrLabel(sel, gcName);
	}

	function prefillLookupIfSingleOrMatch(selId, matchValues) {
		var sel = $(selId);
		if (!sel || sel.value) return;
		var i;
		for (i = 0; i < (matchValues || []).length; i++) {
			if (selectIfEmpty(sel, matchValues[i])) return;
		}
		var only = firstRealOptionValue(sel);
		if (only) sel.value = only;
	}

	function applyStagePrefix(item) {
		var prefix = $("usis-rfi-prefix");
		if (!prefix || prefix.value.trim()) return;
		var stageId = $("usis-rfi-stage") && $("usis-rfi-stage").value;
		var rows = state.lookups.project_stages || [];
		var stage = rows.find(function (r) { return sameId(r.id, stageId); });
		if (stage && stage.prefix) {
			prefix.value = String(stage.prefix).trim();
			return;
		}
		if (item && item.number) prefix.value = String(item.number).trim();
	}

	function prefillManager() {
		var sel = $("usis-rfi-manager");
		if (!sel || sel.value) return;
		selectIfEmpty(sel, currentActorUserId());
	}

	function projectContextBlurb(item) {
		if (!item) return "";
		var head = [item.number, item.name].filter(Boolean).join(" — ");
		var addr = formatProjectAddress(item);
		var parties = [
			item.owner_company_name ? "Owner: " + item.owner_company_name : "",
			item.gc_company_name ? "GC: " + item.gc_company_name : "",
			item.architect_company_name ? "Architect: " + item.architect_company_name : "",
		].filter(Boolean).join("; ");
		return [head, addr !== "—" ? addr : "", parties].filter(Boolean).join(". ");
	}

	function prefillFromProject(item) {
		if (!item) return;
		prefillResponsibleContractor(item);
		prefillLookupIfSingleOrMatch("usis-rfi-location", [
			item.address_line1,
			item.city,
			[item.city, item.state].filter(Boolean).join(", "),
		]);
		prefillLookupIfSingleOrMatch("usis-rfi-stage", [item.status, item.project_type]);
		prefillLookupIfSingleOrMatch("usis-rfi-sub-job", []);
		applyStagePrefix(item);
		prefillManager();
		setInputIfEmpty($("usis-rfi-reference"), [item.number, item.name].filter(Boolean).join(" · "));
		setInputIfEmpty($("usis-rfi-general"), projectContextBlurb(item));
	}

	function applyProjectDerivedFields() {
		applyQueryPrefill();
		prefillFromProject(state.projectItem);
	}

	function applySelectedProject(projectId) {
		state.projectId = projectId || null;
		if (!state.projectId) {
			state.projectItem = null;
			renderProjectCard(null);
			return Promise.resolve();
		}
		rememberProject(state.projectId);
		syncProjectQuery(state.projectId);
		return U.loadProject(state.projectId).then(function (item) {
			ensureProjectOption($("usis-rfi-project"), item, state.projectId);
			if (item && item.id) state.projectId = item.id;
			state.projectItem = item || null;
			renderProjectCard(item);
			prefillFromProject(item);
		}).catch(function () {
			state.projectItem = null;
			renderProjectCard(null);
		});
	}

	function loadProjects() {
		var leadId = currentLeadHint();
		var hinted = Promise.resolve(currentProjectHint());
		if (!currentProjectHint() && leadId) {
			hinted = ensureLeadWorkspace(leadId);
		}
		return hinted.then(function (resolvedHint) {
		return U.loadProjects().then(function (rows) {
			var sel = $("usis-rfi-project");
			fillSelect(sel,
				rows.map(function (p) { return { id: p.id, label: (p.number ? p.number + " · " : "") + p.name }; }),
				{ emptyLabel: "Select project…" }
			);
			var hint = resolvedHint || currentProjectHint();
			if (!hint) {
				sel.value = "";
				state.projectId = null;
				return null;
			}
			if (selectProjectOption(sel, hint)) {
				state.projectId = sel.value;
				rememberProject(sel.value);
				return null;
			}
			state.projectId = hint;
			return U.loadProject(hint).then(function (item) {
				if (!item) {
					state.projectId = null;
					return null;
				}
				ensureProjectOption(sel, item, item.id);
				state.projectId = item.id;
				rememberProject(item.id);
				return item;
			}).catch(function () {
				state.projectId = null;
				return null;
			});
		});
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
			fillSelect($("usis-rfi-received-from"), asLabel, { emptyLabel: "Select a person" });
			fillSelect(
				$("usis-rfi-responsible"),
				state.companies.map(function (c) { return { id: c.id, label: c.name }; }),
				{ emptyLabel: "Select a vendor" }
			);
		});
	}

	function loadLookupsAndCustom() {
		if (!state.projectId) return Promise.resolve();
		var emptyByKind = {
			locations: "Select a Location",
			spec_sections: "Select a Specification",
			cost_codes: "Select a cost code",
			project_stages: "Select…",
			sub_jobs: "Select…",
		};
		var kinds = [
			["locations", "usis-rfi-location", "name"],
			["spec_sections", "usis-rfi-spec", "code"],
			["cost_codes", "usis-rfi-cost-code", "code"],
			["project_stages", "usis-rfi-stage", "name"],
			["sub_jobs", "usis-rfi-sub-job", "name"],
		];
		var tasks = kinds.map(function (k) {
			return U.loadLookup(state.projectId, k[0]).then(function (rows) {
				state.lookups[k[0]] = rows || [];
				var formatted = rows.map(function (r) {
					var label = r[k[2]] || r.code || r.name || "(no name)";
					if (k[0] === "spec_sections" && r.title) label = r.code + " — " + r.title;
					if (k[0] === "cost_codes" && r.description) label = r.code + " — " + r.description;
					return { id: r.id, label: label };
				});
				fillSelect($(k[1]), formatted, { emptyLabel: emptyByKind[k[0]] || "—" });
			}).catch(function () {
				state.lookups[k[0]] = [];
			});
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
				col.className = "usis-rfi-field";
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
				var wrap = el.closest(".usis-rfi-field") || el.closest(".col-md-6, .col-md-12");
				if (r.requirement === "hidden") {
					if (wrap) wrap.classList.add("d-none");
				} else if (r.requirement === "required") {
					var lbl = wrap && wrap.querySelector("label");
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
		if (!state.queuedFiles.length) return Promise.resolve();
		return Promise.all(state.queuedFiles.map(function (file) {
			return U.uploadRfiAttachment(rfiId, file);
		})).then(function () {
			state.queuedFiles = [];
		});
	}

	function submit(status) {
		U.flashError($("usis-rfi-error"), "");
		if (!state.projectId) { U.flashError($("usis-rfi-error"), t("Choose a project.")); return; }
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
			if (window.USISNotify && window.USISNotify.error) {
				window.USISNotify.error(err.message || String(err));
			}
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

	function addAssigneeFromPicker() {
		var picker = $("usis-rfi-assignee-picker");
		if (!picker) return;
		var uid = picker.value;
		if (!uid) return;
		if (state.assignees.some(function (a) { return a.user_id === uid; })) return;
		state.assignees.push({
			user_id: uid,
			is_required: $("usis-rfi-assignee-required") && $("usis-rfi-assignee-required").checked,
		});
		picker.value = "";
		renderAssigneeChips();
	}

	function addDistributionFromPicker() {
		var picker = $("usis-rfi-dist-picker");
		if (!picker) return;
		var uid = picker.value;
		if (!uid) return;
		if (state.distribution.some(function (d) { return d.user_id === uid; })) return;
		state.distribution.push({ user_id: uid });
		picker.value = "";
		renderDistributionChips();
	}

	function wireAssignees() {
		var btn = $("usis-rfi-assignee-add");
		var picker = $("usis-rfi-assignee-picker");
		if (btn) btn.addEventListener("click", addAssigneeFromPicker);
		if (picker) picker.addEventListener("change", addAssigneeFromPicker);
	}

	function wireDistribution() {
		var btn = $("usis-rfi-dist-add");
		var picker = $("usis-rfi-dist-picker");
		if (btn) btn.addEventListener("click", addDistributionFromPicker);
		if (picker) picker.addEventListener("change", addDistributionFromPicker);
	}

	function wireProjectChange() {
		var sel = $("usis-rfi-project");
		if (!sel) return;
		sel.addEventListener("change", function () {
			applySelectedProject(sel.value).then(function () {
				return loadLookupsAndCustom();
			}).then(function () {
				applyProjectDerivedFields();
				return applyConfigurableFields();
			});
		});
	}

	function queueFiles(files) {
		Array.from(files || []).forEach(function (f) {
			state.queuedFiles.push(f);
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
		list.innerHTML = state.queuedFiles.map(function (f, i) {
			return '<div class="d-flex align-items-center gap-2 small mb-1"><i class="fa fa-file"></i> ' +
				U.esc(f.name) + ' <a href="javascript:void(0);" class="text-danger" data-rm="' + i + '">remove</a></div>';
		}).join("");
		Array.prototype.forEach.call(list.querySelectorAll("[data-rm]"), function (a) {
			a.addEventListener("click", function () {
				state.queuedFiles.splice(parseInt(a.dataset.rm, 10), 1);
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
		applyQueryPrefill();
		loadProjects().then(function () {
			return Promise.all([loadUsersAndCompanies(), loadLookupsAndCustom()]);
		}).then(function () {
			return applySelectedProject(state.projectId);
		}).then(function () {
			applyProjectDerivedFields();
			return applyConfigurableFields();
		});

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
