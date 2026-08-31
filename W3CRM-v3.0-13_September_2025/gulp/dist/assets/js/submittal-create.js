/**
 * Create Submittal page — Procore-like section layout, USIS styling.
 *
 * Project is taken from ``?project_id=`` (or the active project context).
 * Attachments are uploaded after create via
 * ``POST /projects/<id>/submittals/<id>/attachments/upload``.
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		users: [],
		companies: [],
		specs: [],
		drawings: [],
		scheduleItems: [],
		distribution: [],
		linkedDrawings: [],
		queuedFiles: [],
		lineItems: [],
		workflow: [{ user_id: "", role: "Approver", due_date: "" }],
	};

	function $(id) {
		return document.getElementById(id);
	}

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(
			function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.statusText || String(res.status));
					return j;
				});
			}
		);
	}

	function apiBase() {
		if (window.USIS_API && typeof window.USIS_API.apiBase === "function") return window.USIS_API.apiBase();
		return "";
	}

	function actorHeaders() {
		if (window.USIS_API && typeof window.USIS_API.actorHeaders === "function") return window.USIS_API.actorHeaders();
		return {};
	}

	function queryParam(name) {
		return new URLSearchParams(window.location.search).get(name);
	}

	function currentProjectHint() {
		var fromQuery = queryParam("project_id") || queryParam("projectId") || queryParam("id");
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

	function flashError(msg) {
		var el = $("usis-sub-error");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.classList.remove("d-none");
		el.textContent = String(msg);
		try {
			window.scrollTo({ top: 0, behavior: "smooth" });
		} catch (e) {}
	}

	function isoFromDateInput(el) {
		if (!el || !el.value) return null;
		var v = String(el.value).trim();
		if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
		return v + "T00:00:00+00:00";
	}

	function dateValue(el) {
		return el && el.value ? String(el.value).trim() : "";
	}

	function addDays(isoDate, days) {
		if (!isoDate) return "";
		var d = new Date(isoDate + "T00:00:00");
		if (isNaN(d.getTime())) return "";
		d.setDate(d.getDate() + Number(days || 0));
		var m = String(d.getMonth() + 1).padStart(2, "0");
		var day = String(d.getDate()).padStart(2, "0");
		return d.getFullYear() + "-" + m + "-" + day;
	}

	function fmtDisplayDate(isoDate) {
		if (!isoDate) return "—";
		var p = String(isoDate).split("-");
		if (p.length !== 3) return isoDate;
		return p[1] + "/" + p[2] + "/" + p[0];
	}

	function fillSelect(sel, items, options) {
		options = options || {};
		if (!sel) return;
		var current = sel.value;
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = t(options.emptyLabel || "—");
		sel.appendChild(blank);
		(items || []).forEach(function (it) {
			var opt = document.createElement("option");
			opt.value = it.id;
			opt.textContent = it.label;
			sel.appendChild(opt);
		});
		if (current) sel.value = current;
	}

	function userLabel(u) {
		if (!u) return "";
		return u.name || u.email || u.id;
	}

	function drawingId(d) {
		return d.series_id || d.id || (d.current_revision && d.current_revision.id) || "";
	}

	function drawingLabel(d) {
		var num = d.sheet_number || d.number || "";
		var title = d.sheet_title || d.title || "";
		return (num ? num + " — " : "") + (title || drawingId(d));
	}

	function specLineId(line) {
		return line && line.spec_section_id != null ? String(line.spec_section_id) : "";
	}

	function renderLineItems() {
		var tb = $("usis-sub-c-lines-tbody");
		if (!tb) return;
		tb.innerHTML = "";
		if (!state.lineItems.length) {
			tb.innerHTML = '<tr><td colspan="5" class="text-muted small">No line items — check spec sections above.</td></tr>';
			return;
		}
		state.lineItems.forEach(function (line, idx) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				'<td class="small">' +
				esc(line.spec_section_code || "—") +
				'</td><td class="small">' +
				esc(line.description || "—") +
				'</td><td><input type="text" class="form-control form-control-sm usis-sub-line-mfr" data-idx="' +
				idx +
				'" maxlength="200" value="' +
				esc(line.manufacturer || "") +
				'"></td><td><input type="text" class="form-control form-control-sm usis-sub-line-model" data-idx="' +
				idx +
				'" maxlength="200" value="' +
				esc(line.model || "") +
				'"></td><td class="text-end"><button type="button" class="btn btn-link btn-sm p-0 text-danger usis-sub-line-rm" data-idx="' +
				idx +
				'">Remove</button></td>';
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-sub-line-mfr").forEach(function (inp) {
			inp.addEventListener("input", function () {
				var i = parseInt(inp.getAttribute("data-idx"), 10);
				if (!isNaN(i) && state.lineItems[i]) state.lineItems[i].manufacturer = inp.value.trim() || null;
			});
		});
		tb.querySelectorAll(".usis-sub-line-model").forEach(function (inp) {
			inp.addEventListener("input", function () {
				var i = parseInt(inp.getAttribute("data-idx"), 10);
				if (!isNaN(i) && state.lineItems[i]) state.lineItems[i].model = inp.value.trim() || null;
			});
		});
		tb.querySelectorAll(".usis-sub-line-rm").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var i = parseInt(btn.getAttribute("data-idx"), 10);
				if (isNaN(i)) return;
				var removed = state.lineItems.splice(i, 1)[0];
				var box = document.querySelector('#usis-sub-c-spec-list input[data-spec-id="' + specLineId(removed) + '"]');
				if (box) box.checked = false;
				renderLineItems();
			});
		});
	}

	function setSpecChecked(spec, checked) {
		var id = spec && spec.id != null ? String(spec.id) : "";
		var idx = state.lineItems.findIndex(function (line) {
			return specLineId(line) === id;
		});
		if (checked && idx < 0) {
			state.lineItems.push({
				spec_section_id: spec.id,
				spec_section_code: spec.code,
				description: spec.title,
				manufacturer: null,
				model: null,
				save_to_catalog: true,
			});
			var titleEl = $("usis-sub-c-title");
			if (titleEl && !titleEl.value.trim()) titleEl.value = spec.title || spec.code || "";
			var specEl = $("usis-sub-c-spec");
			if (specEl && !specEl.value) specEl.value = spec.id;
		} else if (!checked && idx >= 0) {
			state.lineItems.splice(idx, 1);
		}
		renderLineItems();
	}

	function renderSpecPicker() {
		var list = $("usis-sub-c-spec-list");
		var empty = $("usis-sub-c-spec-empty");
		var qEl = $("usis-sub-c-spec-q");
		if (!list) return;
		var q = qEl && qEl.value ? qEl.value.trim().toLowerCase() : "";
		var active = (state.specs || []).filter(function (s) {
			return s && s.is_active !== false;
		});
		var items = active.filter(function (s) {
			if (!q) return true;
			return ((s.code || "") + " " + (s.title || "")).toLowerCase().indexOf(q) !== -1;
		});
		if (empty) empty.classList.toggle("d-none", active.length > 0);
		list.innerHTML = "";
		if (!active.length) return;
		if (!items.length) {
			list.innerHTML = '<p class="text-muted small mb-0 py-1">No sections match that search.</p>';
			return;
		}
		items.forEach(function (spec) {
			var id = String(spec.id);
			var checked = state.lineItems.some(function (line) {
				return specLineId(line) === id;
			});
			var boxId = "usis-sub-c-spec-cb-" + id;
			var row = document.createElement("div");
			row.className = "form-check d-flex align-items-start gap-2 py-1 mb-0";
			row.innerHTML =
				'<input class="form-check-input mt-1" type="checkbox" id="' +
				esc(boxId) +
				'" data-spec-id="' +
				esc(id) +
				'"' +
				(checked ? " checked" : "") +
				'><label class="form-check-label small" for="' +
				esc(boxId) +
				'">' +
				esc(spec.code || "—") +
				(spec.title ? " — " + esc(spec.title) : "") +
				"</label>";
			row.querySelector("input").addEventListener("change", function (e) {
				setSpecChecked(spec, e.target.checked);
			});
			list.appendChild(row);
		});
	}

	function renderChips(wrapId, items, onRemove) {
		var wrap = $(wrapId);
		if (!wrap) return;
		wrap.innerHTML = items
			.map(function (it, i) {
				return (
					'<span class="usis-chip">' +
					esc(it.label) +
					' <span class="x" data-idx="' +
					i +
					'" title="Remove">&times;</span></span>'
				);
			})
			.join("");
		Array.prototype.forEach.call(wrap.querySelectorAll(".x"), function (x) {
			x.addEventListener("click", function () {
				onRemove(parseInt(x.getAttribute("data-idx"), 10));
			});
		});
	}

	function renderDistribution() {
		renderChips("usis-sub-c-dist-chips", state.distribution, function (i) {
			if (!isNaN(i)) state.distribution.splice(i, 1);
			renderDistribution();
		});
	}

	function renderLinkedDrawings() {
		renderChips("usis-sub-c-drawing-chips", state.linkedDrawings, function (i) {
			if (!isNaN(i)) state.linkedDrawings.splice(i, 1);
			renderLinkedDrawings();
		});
	}

	function renderQueuedAttachments() {
		var list = $("usis-sub-c-attach-list");
		if (!list) return;
		list.innerHTML = state.queuedFiles
			.map(function (f, i) {
				return (
					'<div class="d-flex align-items-center gap-2 small mb-1"><i class="fa fa-file"></i> ' +
					esc(f.name) +
					' <a href="javascript:void(0);" class="text-danger" data-rm="' +
					i +
					'">remove</a></div>'
				);
			})
			.join("");
		Array.prototype.forEach.call(list.querySelectorAll("[data-rm]"), function (a) {
			a.addEventListener("click", function () {
				state.queuedFiles.splice(parseInt(a.dataset.rm, 10), 1);
				renderQueuedAttachments();
			});
		});
	}

	function queueFiles(files) {
		Array.from(files || []).forEach(function (f) {
			state.queuedFiles.push(f);
		});
		renderQueuedAttachments();
	}

	function renderWorkflow() {
		var tb = $("usis-sub-c-wf-tbody");
		if (!tb) return;
		tb.innerHTML = "";
		var userOpts = '<option value="">Select a Person</option>';
		state.users.forEach(function (u) {
			userOpts += '<option value="' + esc(u.id) + '">' + esc(userLabel(u)) + "</option>";
		});
		var roles = ["Submitter", "Reviewer", "Approver", "CC"];
		state.workflow.forEach(function (step, idx) {
			var tr = document.createElement("tr");
			var roleOpts = roles
				.map(function (r) {
					return '<option value="' + r + '"' + (step.role === r ? " selected" : "") + ">" + r + "</option>";
				})
				.join("");
			tr.innerHTML =
				'<td class="usis-sub-grip" title="Reorder"><i class="fa fa-grip-vertical"></i></td>' +
				"<td>" +
				(idx + 1) +
				"</td>" +
				'<td><select class="form-select form-select-sm usis-sub-wf-user" data-idx="' +
				idx +
				'">' +
				userOpts +
				"</select></td>" +
				'<td><select class="form-select form-select-sm usis-sub-wf-role" data-idx="' +
				idx +
				'">' +
				roleOpts +
				"</select></td>" +
				'<td><input type="date" class="form-control form-control-sm usis-sub-wf-due" data-idx="' +
				idx +
				'" value="' +
				esc(step.due_date || "") +
				'"></td>' +
				'<td><button type="button" class="btn btn-link btn-sm text-danger p-0 usis-sub-wf-rm" data-idx="' +
				idx +
				'">&times;</button></td>';
			tb.appendChild(tr);
			var userSel = tr.querySelector(".usis-sub-wf-user");
			if (userSel && step.user_id) userSel.value = step.user_id;
		});
		tb.querySelectorAll(".usis-sub-wf-user").forEach(function (sel) {
			sel.addEventListener("change", function () {
				var i = parseInt(sel.getAttribute("data-idx"), 10);
				if (!isNaN(i) && state.workflow[i]) {
					state.workflow[i].user_id = sel.value;
					syncBallInCourtFromWorkflow();
				}
			});
		});
		tb.querySelectorAll(".usis-sub-wf-role").forEach(function (sel) {
			sel.addEventListener("change", function () {
				var i = parseInt(sel.getAttribute("data-idx"), 10);
				if (!isNaN(i) && state.workflow[i]) state.workflow[i].role = sel.value;
			});
		});
		tb.querySelectorAll(".usis-sub-wf-due").forEach(function (inp) {
			inp.addEventListener("change", function () {
				var i = parseInt(inp.getAttribute("data-idx"), 10);
				if (!isNaN(i) && state.workflow[i]) state.workflow[i].due_date = inp.value;
			});
		});
		tb.querySelectorAll(".usis-sub-wf-rm").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var i = parseInt(btn.getAttribute("data-idx"), 10);
				if (isNaN(i) || state.workflow.length < 2) return;
				state.workflow.splice(i, 1);
				renderWorkflow();
			});
		});
	}

	function syncBallInCourtFromWorkflow() {
		var bic = $("usis-sub-c-bic");
		if (!bic || bic.value) return;
		var first = state.workflow.find(function (s) {
			return s.user_id;
		});
		if (first) bic.value = first.user_id;
	}

	function updatePlannedDates() {
		var due = dateValue($("usis-sub-c-due"));
		var design = parseInt(($("usis-sub-c-design-days") || {}).value, 10);
		var internal = parseInt(($("usis-sub-c-internal-days") || {}).value, 10);
		if (isNaN(design)) design = 0;
		if (isNaN(internal)) internal = 0;
		var plannedReturn = due;
		var plannedInternal = due ? addDays(due, -design) : "";
		var plannedSubmit = plannedInternal ? addDays(plannedInternal, -internal) : "";
		var r = $("usis-sub-c-planned-return");
		var i = $("usis-sub-c-planned-internal");
		var s = $("usis-sub-c-planned-submit");
		if (r) r.textContent = fmtDisplayDate(plannedReturn);
		if (i) i.textContent = fmtDisplayDate(plannedInternal);
		if (s) s.textContent = fmtDisplayDate(plannedSubmit);
		return plannedSubmit;
	}

	function toggleMaterialFields() {
		var on = $("usis-sub-c-material") && $("usis-sub-c-material").checked;
		var wrap = $("usis-sub-material-fields");
		if (wrap) wrap.classList.toggle("d-none", !on);
	}

	function selectedSpecCode() {
		var sel = $("usis-sub-c-spec");
		if (!sel || !sel.value) return null;
		var spec = state.specs.find(function (s) {
			return String(s.id) === sel.value;
		});
		return spec ? spec.code || spec.title : sel.options[sel.selectedIndex].text;
	}

	function selectedLabel(sel) {
		if (!sel || !sel.value) return null;
		var opt = sel.options[sel.selectedIndex];
		return opt ? opt.textContent : null;
	}

	function readPayload(status) {
		var plannedSubmit = updatePlannedDates();
		var contractorSel = $("usis-sub-c-contractor");
		var receivedSel = $("usis-sub-c-receivedfrom");
		var bicSel = $("usis-sub-c-bic");
		var locSel = $("usis-sub-c-location");
		var lines = state.lineItems.slice();
		if ($("usis-sub-c-material") && $("usis-sub-c-material").checked) {
			var mfr = ($("usis-sub-c-mfr") || {}).value;
			if (mfr && mfr.trim()) {
				if (lines.length) {
					if (!lines[0].manufacturer) lines[0].manufacturer = mfr.trim();
				} else {
					lines.push({
						description: ($("usis-sub-c-title") || {}).value || "Material",
						manufacturer: mfr.trim(),
						model: null,
					});
				}
			}
		}
		return {
			title: (($("usis-sub-c-title") || {}).value || "").trim(),
			spec_section: selectedSpecCode(),
			submittal_type: ($("usis-sub-c-type") || {}).value || null,
			status: status || "draft",
			revision: (($("usis-sub-c-rev") || {}).value || "").trim() || null,
			responsible_contractor: selectedLabel(contractorSel),
			received_from: selectedLabel(receivedSel),
			ball_in_court: selectedLabel(bicSel),
			due_at: isoFromDateInput($("usis-sub-c-due")),
			submit_by_at: plannedSubmit ? plannedSubmit + "T00:00:00+00:00" : null,
			released_at: isoFromDateInput($("usis-sub-c-release")),
			needed_by_date: dateValue($("usis-sub-c-needed")) || null,
			notes: (($("usis-sub-c-notes") || {}).value || "").trim() || null,
			response: (($("usis-sub-c-comments") || {}).value || "").trim() || null,
			linked_drawing_ids: state.linkedDrawings.map(function (d) {
				return d.id;
			}),
			line_items: lines,
			approvers: {
				version: 1,
				steps: state.workflow.map(function (step, idx) {
					var u = state.users.find(function (x) {
						return x.id === step.user_id;
					});
					return {
						step: idx + 1,
						user_id: step.user_id || null,
						name: u ? userLabel(u) : null,
						role: step.role || "Approver",
						due_date: step.due_date || null,
					};
				}),
				distribution: state.distribution.map(function (d) {
					return { user_id: d.id, name: d.label };
				}),
				location_id: locSel && locSel.value ? locSel.value : null,
				location_label: selectedLabel(locSel),
				is_private: !!( $("usis-sub-c-private") && $("usis-sub-c-private").checked ),
				material_tracking: !!( $("usis-sub-c-material") && $("usis-sub-c-material").checked ),
				supply_chain_risk: ($("usis-sub-c-risk") || {}).value || null,
				manufacturer: (($("usis-sub-c-mfr") || {}).value || "").trim() || null,
				manufacturer_location: (($("usis-sub-c-mfr-loc") || {}).value || "").trim() || null,
				schedule_item_id: ($("usis-sub-c-task") || {}).value || null,
				design_review_days: parseInt(($("usis-sub-c-design-days") || {}).value, 10) || 0,
				internal_review_days: parseInt(($("usis-sub-c-internal-days") || {}).value, 10) || 0,
				confirmed_delivery_date: dateValue($("usis-sub-c-confirmed")) || null,
				actual_delivery_date: dateValue($("usis-sub-c-actual")) || null,
			},
		};
	}

	function uploadAttachments(projectId, submittalId) {
		if (!state.queuedFiles.length) return Promise.resolve();
		var url =
			apiBase() +
			"/api/v1/projects/" +
			encodeURIComponent(projectId) +
			"/submittals/" +
			encodeURIComponent(submittalId) +
			"/attachments/upload";
		return Promise.all(
			state.queuedFiles.map(function (file) {
				var fd = new FormData();
				fd.append("file", file, file.name || "attachment");
				return fetch(url, {
					method: "POST",
					credentials: "include",
					headers: actorHeaders(),
					body: fd,
				}).then(function (res) {
					if (!res.ok) {
						return res.text().then(function (txt) {
							var msg = txt;
							try {
								var j = JSON.parse(txt);
								msg = j.error || j.message || txt;
							} catch (e) {}
							throw new Error(msg || res.statusText);
						});
					}
					return res.json();
				});
			})
		).then(function () {
			state.queuedFiles = [];
		});
	}

	function submit(status) {
		flashError("");
		if (!state.projectId) {
			flashError(t("Choose a project."));
			return;
		}
		var payload = readPayload(status);
		if (!payload.title) {
			flashError("Title is required.");
			return;
		}
		var draftBtn = $("usis-sub-btn-draft");
		var createBtn = $("usis-sub-btn-create");
		if (draftBtn) draftBtn.disabled = true;
		if (createBtn) createBtn.disabled = true;
		fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/submittals", {
			method: "POST",
			body: payload,
		})
			.then(function (data) {
				var item = data.item || {};
				return uploadAttachments(state.projectId, item.id).then(function () {
					return item;
				});
			})
			.then(function (item) {
				window.location.href =
					"construction/submittal-detail.html?id=" +
					encodeURIComponent(state.projectId) +
					"&submittal=" +
					encodeURIComponent(item.id);
			})
			.catch(function (err) {
				flashError(err.message || String(err));
				if (draftBtn) draftBtn.disabled = false;
				if (createBtn) createBtn.disabled = false;
			});
	}

	function loadLookups(projectId) {
		var pid = encodeURIComponent(projectId);
		return Promise.all([
			fetchJson("/api/v1/rfi-users").then(function (d) {
				state.users = d.items || [];
			}),
			fetchJson("/api/v1/rfi-companies").then(function (d) {
				state.companies = d.items || [];
			}),
			fetchJson("/api/v1/projects/" + pid + "/rfi-lookups/spec_sections").then(function (d) {
				state.specs = d.items || [];
			}),
			fetchJson("/api/v1/projects/" + pid + "/rfi-lookups/locations").then(function (d) {
				return d.items || [];
			}),
			fetchJson("/api/v1/projects/" + pid + "/drawings?limit=2000&offset=0").then(function (d) {
				state.drawings = d.items || [];
			}).catch(function () {
				state.drawings = [];
			}),
			fetchJson("/api/v1/projects/" + pid + "/schedule-items").then(function (d) {
				state.scheduleItems = d.items || [];
			}).catch(function () {
				state.scheduleItems = [];
			}),
			fetchJson("/api/v1/projects/" + pid + "/submittals").then(function (d) {
				var nums = (d.items || []).map(function (it) {
					return Number(it.number) || 0;
				});
				var next = (nums.length ? Math.max.apply(null, nums) : 0) + 1;
				var numEl = $("usis-sub-c-number");
				if (numEl) numEl.value = String(next);
			}).catch(function () {}),
		]).then(function (results) {
			var locations = results[3] || [];
			fillSelect(
				$("usis-sub-c-spec"),
				state.specs.map(function (s) {
					return { id: s.id, label: (s.code ? s.code + " — " : "") + (s.title || "") };
				})
			);
			fillSelect(
				$("usis-sub-c-contractor"),
				state.companies.map(function (c) {
					return { id: c.id, label: c.name };
				})
			);
			var people = state.users.map(function (u) {
				return { id: u.id, label: userLabel(u) + (u.email && u.name ? " · " + u.email : "") };
			});
			fillSelect($("usis-sub-c-receivedfrom"), people);
			fillSelect($("usis-sub-c-bic"), people);
			fillSelect($("usis-sub-c-dist-picker"), people, { emptyLabel: "Select…" });
			fillSelect(
				$("usis-sub-c-location"),
				locations.map(function (l) {
					return { id: l.id, label: l.name || l.label || l.code || l.id };
				})
			);
			fillSelect(
				$("usis-sub-c-drawing-picker"),
				state.drawings.map(function (d) {
					return { id: drawingId(d), label: drawingLabel(d) };
				}),
				{ emptyLabel: "Select…" }
			);
			fillSelect(
				$("usis-sub-c-task"),
				state.scheduleItems.map(function (it) {
					return { id: it.id, label: it.title || it.id };
				}),
				{ emptyLabel: "Select" }
			);
			renderSpecPicker();
			renderWorkflow();
		});
	}

	function wire() {
		var draft = $("usis-sub-btn-draft");
		var create = $("usis-sub-btn-create");
		if (draft) draft.addEventListener("click", function () { submit("draft"); });
		if (create) create.addEventListener("click", function () { submit("submitted"); });

		var specQ = $("usis-sub-c-spec-q");
		if (specQ) specQ.addEventListener("input", renderSpecPicker);

		var specSel = $("usis-sub-c-spec");
		if (specSel) {
			specSel.addEventListener("change", function () {
				if (!specSel.value) return;
				var spec = state.specs.find(function (s) {
					return String(s.id) === specSel.value;
				});
				if (spec) setSpecChecked(spec, true);
				var box = document.querySelector('#usis-sub-c-spec-list input[data-spec-id="' + specSel.value + '"]');
				if (box) box.checked = true;
			});
		}

		var dist = $("usis-sub-c-dist-picker");
		if (dist) {
			dist.addEventListener("change", function () {
				if (!dist.value) return;
				if (state.distribution.some(function (d) { return d.id === dist.value; })) {
					dist.value = "";
					return;
				}
				state.distribution.push({ id: dist.value, label: selectedLabel(dist) });
				dist.value = "";
				renderDistribution();
			});
		}

		var draw = $("usis-sub-c-drawing-picker");
		if (draw) {
			draw.addEventListener("change", function () {
				if (!draw.value) return;
				if (state.linkedDrawings.some(function (d) { return d.id === draw.value; })) {
					draw.value = "";
					return;
				}
				state.linkedDrawings.push({ id: draw.value, label: selectedLabel(draw) });
				draw.value = "";
				renderLinkedDrawings();
			});
		}

		var mat = $("usis-sub-c-material");
		if (mat) mat.addEventListener("change", toggleMaterialFields);
		toggleMaterialFields();

		["usis-sub-c-due", "usis-sub-c-design-days", "usis-sub-c-internal-days"].forEach(function (id) {
			var el = $(id);
			if (el) el.addEventListener("input", updatePlannedDates);
			if (el) el.addEventListener("change", updatePlannedDates);
		});
		updatePlannedDates();

		var addStep = $("usis-sub-c-wf-add");
		if (addStep) {
			addStep.addEventListener("click", function () {
				state.workflow.push({ user_id: "", role: "Approver", due_date: "" });
				renderWorkflow();
			});
		}

		var input = $("usis-sub-c-attach-file");
		var drop = $("usis-sub-attach-drop");
		var btn = $("usis-sub-attach-btn");
		if (input) input.addEventListener("change", function () { queueFiles(input.files); input.value = ""; });
		function openFile() {
			if (input) input.click();
		}
		if (btn) btn.addEventListener("click", function (e) { e.stopPropagation(); openFile(); });
		if (drop) {
			drop.addEventListener("click", openFile);
			drop.addEventListener("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					openFile();
				}
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

		var cancel = $("usis-sub-cancel");
		if (cancel && state.projectId) {
			cancel.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(state.projectId));
		}
	}

	function init() {
		var pid = currentProjectHint();
		if (!pid) {
			flashError(t("Choose a project."));
			wire();
			return;
		}
		state.projectId = pid;
		rememberProject(pid);
		wire();
		renderLineItems();
		loadLookups(pid).catch(function (err) {
			flashError(err.message || String(err));
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
