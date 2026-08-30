/**
 * Estimate detail — Takeoff tab: Tabulator grid for estimate-scoped takeoff lines
 * (GET/POST /api/v1/estimates/<id>/takeoff-lines, PATCH/DELETE /api/v1/takeoff-lines/<line_id>).
 * Requires URL ?id=<estimate UUID>. Uses parent lead + project_id from usis-lead-estimate-loaded for viewer links.
 */
(function () {
	"use strict";

	var takeoffTable = null;
	var mountedEstimateKey = null;
	var activeProjectId = null;
	var parentLeadKey = null;
	var takeoffAf = null;
	var lastTakeoffRows = [];

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var port = String(loc.port || "");
		if (["3000", "3001", "3002", "3003", "5173", "8080"].indexOf(port) >= 0) return "";
		var host = loc.hostname || "";
		if ((host === "localhost" || host === "127.0.0.1") && port && port !== "5000") {
			return (loc.protocol + "//" + host + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	function leadKeyFromUrl() {
		return new URLSearchParams(window.location.search).get("id");
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function notifyErr(msg) {
		if (window.USISNotify) window.USISNotify.error(String(msg));
		else alert(String(msg));
	}

	function valuesEqual(a, b) {
		if (a === b) return true;
		if (a != null && b != null && typeof a === "object" && typeof b === "object") {
			try {
				return JSON.stringify(a) === JSON.stringify(b);
			} catch (e) {
				return false;
			}
		}
		return false;
	}

	function buildColumns(projectId) {
		return [
			{ title: "Sort", field: "sort_order", width: 72, editor: "number", hozAlign: "right", headerSort: true },
			{ title: "Section", field: "section", width: 110, editor: "input" },
			{ title: "Description", field: "description", minWidth: 140, widthGrow: 2, editor: "input" },
			{
				title: "Qty",
				field: "quantity",
				width: 90,
				hozAlign: "right",
				editor: "number",
				editorParams: { step: 0.0001, min: 0 },
			},
			{ title: "Unit", field: "unit", width: 72, editor: "input" },
			{
				title: "Unit cost",
				field: "unit_cost",
				width: 100,
				hozAlign: "right",
				editor: "number",
				editorParams: { step: 0.0001, min: 0 },
			},
			{
				title: "Ext.",
				field: "extended_total",
				width: 100,
				hozAlign: "right",
				editable: false,
				formatter: function (cell) {
					var v = cell.getValue();
					if (v == null || v === "") return "—";
					var n = Number(v);
					return isNaN(n) ? String(v) : n.toFixed(2);
				},
			},
			{
				title: "Type",
				field: "cost_type",
				width: 72,
				editor: "list",
				editorParams: { values: ["L", "M", "E", "S", "O"] },
			},
			{ title: "Cost code", field: "job_cost_code", width: 110, editor: "input" },
			{
				title: "Cost code desc.",
				field: "job_cost_code_description",
				minWidth: 120,
				widthGrow: 1,
				editor: "input",
			},
			{ title: "Status", field: "status", width: 100, editor: "input" },
			{ title: "Notes", field: "notes", minWidth: 100, widthGrow: 1, editor: "textarea" },
			{
				title: "Measure",
				field: "measurement_data",
				width: 100,
				editable: false,
				formatter: function (cell) {
					var v = cell.getValue();
					if (v == null) return "—";
					if (typeof v === "object") {
						var t = v.tool || v.type || "";
						var p = v.page != null ? "p" + v.page : "";
						return (t || "data") + (p ? " · " + p : "");
					}
					return String(v).slice(0, 24);
				},
			},
			{
				title: "Drawing",
				field: "drawing_id",
				width: 100,
				editable: false,
				formatter: function (cell) {
					var row = cell.getRow().getData();
					var did = row.drawing_id;
					if (!did) return "—";
					var q =
						(projectId ? "project_id=" + encodeURIComponent(projectId) + "&" : "") +
						"drawing_id=" +
						encodeURIComponent(did) +
						"&takeoff_line=" +
						encodeURIComponent(row.id) +
						"&lead_id=" +
						encodeURIComponent(leadKeyFromUrl() || "") +
						"&from=estimate";
					var a = document.createElement("a");
					a.className = "small";
					a.href = "construction/drawing-viewer.html?" + q;
					a.textContent = "View";
					return a;
				},
			},
			{
				title: "",
				field: "id",
				width: 64,
				headerSort: false,
				headerFilter: false,
				hozAlign: "center",
				editable: false,
				formatter: function (cell) {
					var btn = document.createElement("button");
					btn.type = "button";
					btn.className = "btn btn-outline-danger btn-sm py-0 px-1";
					btn.textContent = "Del";
					btn.addEventListener("click", function (ev) {
						ev.preventDefault();
						ev.stopPropagation();
						var row = cell.getRow();
						var id = row.getData().id;
						if (!id || !window.confirm("Delete this takeoff line?")) return;
						fetch(apiBase() + "/api/v1/takeoff-lines/" + encodeURIComponent(id), {
							method: "DELETE",
							credentials: "include",
						})
							.then(function (res) {
								return res.json().then(function (j) {
									if (!res.ok) throw new Error(j.error || res.status);
									return j;
								});
							})
							.then(function () {
								row.delete();
								if (window.USISNotify) window.USISNotify.success("Line deleted");
							})
							.catch(function (e) {
								notifyErr(e.message || e);
							});
					});
					return btn;
				},
			},
		];
	}

	function takeoffAfColumns() {
		return [
			{ key: "sort_order", label: "Sort", type: "number", sortable: true, filterable: false },
			{ key: "section", label: "Section", type: "text", sortable: true, filterable: true },
			{ key: "description", label: "Description", type: "text", sortable: true, filterable: true },
			{ key: "quantity", label: "Qty", type: "number", sortable: true, filterable: true },
			{
				key: "unit",
				label: "Unit",
				type: "singleSelect",
				sortable: true,
				filterable: true,
				valueOptions: ["SF", "LF", "EA", "SQ", "GAL"],
			},
			{ key: "unit_cost", label: "Unit cost", type: "number", sortable: true, filterable: true },
			{ key: "extended_total", label: "Ext.", type: "number", sortable: true, filterable: true },
			{
				key: "cost_type",
				label: "Type",
				type: "singleSelect",
				sortable: true,
				filterable: true,
				valueOptions: ["L", "M", "E", "S", "O"],
			},
			{ key: "job_cost_code", label: "Cost code", type: "text", sortable: true, filterable: true },
			{ key: "status", label: "Status", type: "singleSelect", sortable: true, filterable: true },
			{ key: "notes", label: "Notes", type: "text", sortable: true, filterable: true },
			{ key: "drawing_id", label: "Drawing", type: "text", sortable: true, filterable: true },
		];
	}

	function applyTakeoffGridFilter() {
		if (!takeoffTable || !takeoffAf) return;
		takeoffTable.setFilter(function (data) {
			return takeoffAf.matches(data);
		});
		var st = takeoffAf.getState().sort;
		if (st && st.dir && st.key) takeoffTable.setSort(st.key, st.dir);
		else if (typeof takeoffTable.clearSort === "function") takeoffTable.clearSort();
		var status = document.getElementById("usis-est-takeoff-af-status");
		var labels = takeoffAf.getActiveLabels();
		var shown = takeoffAf.filter(lastTakeoffRows).length;
		var total = lastTakeoffRows.length;
		if (status) {
			if (!labels.length && shown === total) {
				status.textContent = "";
				status.classList.add("d-none");
			} else {
				status.classList.remove("d-none");
				status.innerHTML =
					"Showing " +
					shown +
					" of " +
					total +
					" lines" +
					(labels.length ? " · Filters on: " + labels.join(", ") : "") +
					' <button type="button" class="btn btn-link btn-sm py-0 align-baseline" id="usis-est-takeoff-af-clear">Clear</button>';
			}
		}
		decorateTakeoffHeaders();
	}

	function decorateTakeoffHeaders() {
		var root = document.getElementById("usis-grid-est-takeoff");
		if (!root || !takeoffAf) return;
		var cols = root.querySelectorAll(".tabulator-col");
		for (var i = 0; i < cols.length; i++) {
			var colEl = cols[i];
			var field = colEl.getAttribute("tabulator-field");
			if (!field || field === "id" || field === "measurement_data") continue;
			if (colEl.querySelector(".usis-af-btn")) continue;
			var title = colEl.querySelector(".tabulator-col-title");
			if (!title) continue;
			var btn = document.createElement("button");
			btn.type = "button";
			btn.className = "usis-af-btn";
			btn.setAttribute("data-af-key", field);
			btn.setAttribute("aria-label", "Sort and filter " + field);
			btn.innerHTML = '<i class="fa fa-filter usis-af-funnel" aria-hidden="true"></i>';
			btn.addEventListener("click", function (e) {
				e.preventDefault();
				e.stopPropagation();
				var key = e.currentTarget.getAttribute("data-af-key");
				if (takeoffAf && takeoffAf.openColumn) takeoffAf.openColumn(key, e.currentTarget);
			});
			title.appendChild(btn);
		}
	}

	function bindTakeoffAutoFilter(estimateKey) {
		if (!window.USIS_TABLE_AUTOFILTER) return;
		takeoffAf = window.USIS_TABLE_AUTOFILTER.bind({
			table: null,
			tableId: "estimating.takeoff-grid:" + estimateKey,
			getRows: function () {
				return lastTakeoffRows;
			},
			resetButton: "#usis-est-takeoff-reset-view",
			mobileButton: "#usis-est-takeoff-sort-filter",
			columns: takeoffAfColumns(),
			onChange: applyTakeoffGridFilter,
		});
		var status = document.getElementById("usis-est-takeoff-af-status");
		if (status && !status.getAttribute("data-af-wired")) {
			status.setAttribute("data-af-wired", "1");
			status.addEventListener("click", function (e) {
				if (e.target && e.target.id === "usis-est-takeoff-af-clear" && takeoffAf) takeoffAf.reset();
			});
		}
	}

	function reloadTakeoff(estimateKey) {
		return fetch(
			apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/takeoff-lines",
			{
				credentials: "include",
				headers: { Accept: "application/json" },
			}
		)
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				var rows = data.items || [];
				lastTakeoffRows = rows;
				if (takeoffTable) takeoffTable.setData(rows);
				applyTakeoffGridFilter();
				return rows;
			})
			.catch(function (e) {
				notifyErr("Could not load takeoff lines: " + (e.message || e));
				if (takeoffTable) takeoffTable.setData([]);
				throw e;
			});
	}

	function renderBidScope(scope) {
		var src = document.getElementById("usis-est-scope-source");
		var pkg = document.getElementById("usis-est-scope-pkg");
		var tb = document.getElementById("usis-est-scope-rows");
		if (src && scope) src.value = scope.source || "standard";
		if (pkg && scope) pkg.value = scope.bidPackageLabel || "";
		if (!tb) return;
		tb.innerHTML = (scope && scope.items ? scope.items : [])
			.map(function (it) {
				return (
					"<tr data-id=\"" +
					esc(it.id) +
					"\"><td><input type=\"checkbox\" class=\"form-check-input usis-scope-inc\"" +
					(it.included ? " checked" : "") +
					"></td><td><input class=\"form-control form-control-sm usis-scope-code\" value=\"" +
					esc(it.specCode) +
					"\"></td><td><input class=\"form-control form-control-sm usis-scope-title\" value=\"" +
					esc(it.specTitle) +
					"\"></td><td><code>" +
					esc(it.scriptKey || "—") +
					"</code></td><td>" +
					esc(it.status || "") +
					"</td><td>" +
					(it.scriptKey
						? '<button type="button" class="btn btn-link btn-sm p-0 usis-scope-run" data-script="' +
						  esc(it.scriptKey) +
						  '">Run</button>'
						: "") +
					"</td></tr>"
				);
			})
			.join("");
	}

	function collectBidScope() {
		var src = document.getElementById("usis-est-scope-source");
		var pkg = document.getElementById("usis-est-scope-pkg");
		var rows = document.querySelectorAll("#usis-est-scope-rows tr");
		var items = Array.prototype.map.call(rows, function (tr, i) {
			return {
				spec_code: (tr.querySelector(".usis-scope-code") || {}).value || "",
				spec_title: (tr.querySelector(".usis-scope-title") || {}).value || "",
				included: !!(tr.querySelector(".usis-scope-inc") && tr.querySelector(".usis-scope-inc").checked),
				sort_order: i + 1,
			};
		});
		return {
			source: src ? src.value : "standard",
			bid_package_label: pkg ? pkg.value : "",
			items: items,
		};
	}

	function loadBidScope(estimateKey) {
		return fetch(apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/bid-scope", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j.item;
				});
			})
			.then(function (item) {
				renderBidScope(item);
				if (item && item.bidLocation) {
					var locEl = document.getElementById("usis-est-hygiene-locations");
					if (locEl) locEl.textContent = bidLocationLine(item.bidLocation);
				}
				return item;
			})
			.catch(function () {
				renderBidScope({ source: "standard", items: [] });
			});
	}

	function bidLocationLine(loc) {
		if (!loc) return "";
		var labels = (loc.locations || [])
			.map(function (x) {
				return x.label;
			})
			.filter(Boolean);
		var req = loc.requirement || "not_found";
		var head =
			req === "required"
				? "Bid by " + (loc.grain || "location") + " is required"
				: req === "unclear"
					? "Bid-by-location is unclear"
					: "No bid-by-location instruction found";
		if (labels.length) head += " — " + labels.join(", ");
		if (loc.reason) head += ". " + loc.reason;
		if (loc.needsAi) head += " Flagged for Grok later.";
		return head;
	}

	function renderHygiene(payload) {
		var el = document.getElementById("usis-est-hygiene-status");
		var locEl = document.getElementById("usis-est-hygiene-locations");
		if (el) {
			if (!payload) {
				el.textContent = "Not run yet. Check labels, sheet types, and bid-by-location before the overall pass.";
			} else {
				var c = payload.counts || {};
				el.textContent =
					(payload.total || 0) +
					" sheets — " +
					(c.ok || 0) +
					" labels ok, " +
					(c.needs_ai || 0) +
					" labels need AI, " +
					(c.unknown || 0) +
					" unlabeled · " +
					(c.typed || 0) +
					" typed, " +
					(c.type_needs_ai || 0) +
					" types need AI.";
			}
		}
		if (locEl) locEl.textContent = payload ? bidLocationLine(payload.bidLocation) : "";
	}

	function bindHygiene(estimateKey) {
		var btn = document.getElementById("usis-est-hygiene-run");
		if (!btn) return;
		btn.addEventListener("click", function () {
			btn.disabled = true;
			fetch(apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/drawings/hygiene", {
				method: "POST",
				credentials: "include",
				headers: { Accept: "application/json", "Content-Type": "application/json" },
				body: "{}",
			})
				.then(function (res) {
					return res.json().then(function (j) {
						if (!res.ok) throw new Error(j.error || res.status);
						return j;
					});
				})
				.then(function (payload) {
					renderHygiene(payload);
					if (window.USISNotify) window.USISNotify.success("Drawing hygiene complete.");
				})
				.catch(function (e) {
					notifyErr(e.message || e);
				})
				.then(function () {
					btn.disabled = false;
				});
		});
	}

	function bindBidScope(estimateKey, projectId) {
		bindHygiene(estimateKey);
		loadBidScope(estimateKey);
		if (window.USIS_AI_WORKFLOW) {
			window.USIS_AI_WORKFLOW.ensure({
				processKey: "estimator_scope",
				subjectType: "estimate",
				subjectId: estimateKey,
				projectId: projectId,
			})
				.then(function (inst) {
					window.USIS_AI_WORKFLOW.renderStepper(document.getElementById("usis-est-scope-stepper"), inst);
				})
				.catch(function () {});
		}
		var run = document.getElementById("usis-est-scope-run");
		if (run)
			run.addEventListener("click", function () {
				if (!window.USIS_AI_WORKFLOW) return;
				run.disabled = true;
				window.USIS_AI_WORKFLOW.runUntilHuman({
					processKey: "estimator_scope",
					subjectType: "estimate",
					subjectId: estimateKey,
					projectId: projectId,
					estimateId: estimateKey,
					stepperEl: document.getElementById("usis-est-scope-stepper"),
					subjectNote: "estimate_id=" + estimateKey,
					mode: "estimating_review",
				})
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Overall pass paused for bid-set confirm.");
						return loadBidScope(estimateKey);
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					})
					.then(function () {
						run.disabled = false;
					});
			});
		var save = document.getElementById("usis-est-scope-save");
		if (save)
			save.addEventListener("click", function () {
				fetch(apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/bid-scope", {
					method: "PUT",
					credentials: "include",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: JSON.stringify(collectBidScope()),
				})
					.then(function (res) {
						return res.json().then(function (j) {
							if (!res.ok) throw new Error(j.error || res.status);
							return j.item;
						});
					})
					.then(function (item) {
						renderBidScope(item);
						if (window.USISNotify) window.USISNotify.success("Bid set saved.");
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					});
			});
		var confirm = document.getElementById("usis-est-scope-confirm");
		if (confirm)
			confirm.addEventListener("click", function () {
				fetch(apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/bid-scope", {
					method: "PUT",
					credentials: "include",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: JSON.stringify(collectBidScope()),
				})
					.then(function () {
						return fetch(apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/bid-scope/enqueue", {
							method: "POST",
							credentials: "include",
							headers: { "Content-Type": "application/json", Accept: "application/json" },
							body: "{}",
						});
					})
					.then(function (res) {
						return res.json().then(function (j) {
							if (!res.ok) throw new Error(j.error || res.status);
							return j.item;
						});
					})
					.then(function (item) {
						renderBidScope(item);
						if (window.USISNotify) window.USISNotify.success("Spec scripts queued.");
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					});
			});
		var host = document.getElementById("usis-est-scope-rows");
		if (host)
			host.addEventListener("click", function (ev) {
				var btn = ev.target.closest && ev.target.closest(".usis-scope-run");
				if (!btn || !window.USIS_AI_WORKFLOW) return;
				var key = btn.getAttribute("data-script");
				btn.disabled = true;
				window.USIS_AI_WORKFLOW.runUntilHuman({
					processKey: key,
					subjectType: "estimate",
					subjectId: estimateKey,
					projectId: projectId,
					estimateId: estimateKey,
					subjectNote: "estimate_id=" + estimateKey + " script=" + key,
					mode: "estimating_review",
				})
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Spec script reached leftovers.");
						return loadBidScope(estimateKey);
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					})
					.then(function () {
						btn.disabled = false;
					});
			});
	}

	function mountGrid(root, estimateKey, projectId, leadKey) {
		var doorId = leadKey || estimateKey;
		root.innerHTML =
			'<div class="border rounded p-2 mb-3">' +
			'<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">' +
			'<strong class="small mb-0">Drawing hygiene</strong>' +
			'<button type="button" class="btn btn-sm btn-outline-secondary" id="usis-est-hygiene-run">Check labels, types &amp; bid locations</button>' +
			"</div>" +
			'<p class="small text-muted mb-1">CPU first. Drawing numbers, sheet types, and whether the GC wants the bid by floor, area, or building. Grok is not called yet.</p>' +
			'<p class="small mb-1" id="usis-est-hygiene-status">Not run yet. Check labels, sheet types, and bid-by-location before the overall pass.</p>' +
			'<p class="small mb-0" id="usis-est-hygiene-locations"></p>' +
			"</div>" +
			'<div class="border rounded p-2 mb-3 bg-light">' +
			'<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">' +
			'<strong class="small mb-0">Bid scope</strong>' +
			'<div class="d-flex flex-wrap gap-2">' +
			'<button type="button" class="btn btn-sm usis-ai-review" id="usis-est-scope-run">Run overall pass</button>' +
			'<button type="button" class="btn btn-sm btn-outline-primary" id="usis-est-scope-confirm">Confirm &amp; queue spec scripts</button>' +
			"</div></div>" +
			'<p class="small text-muted mb-2">Overall pass picks specs from USIS standards, or from a GC bid package. Then each included spec runs its own script.</p>' +
			'<p class="small mb-2" id="usis-est-scope-stepper"></p>' +
			'<div class="row g-2 align-items-end mb-2">' +
			'<div class="col-md-3"><label class="form-label small mb-0">Source</label>' +
			'<select class="form-select form-select-sm" id="usis-est-scope-source"><option value="standard">USIS standard specs</option>' +
			'<option value="bid_package">GC bid package (bid all listed)</option><option value="mixed">Mixed</option></select></div>' +
			'<div class="col-md-4"><label class="form-label small mb-0">Package name</label>' +
			'<input class="form-control form-control-sm" id="usis-est-scope-pkg" placeholder="e.g. Bid Package 3 — Interiors"></div>' +
			'<div class="col-md-2"><button type="button" class="btn btn-sm btn-outline-secondary" id="usis-est-scope-save">Save bid set</button></div>' +
			"</div>" +
			'<div class="table-responsive"><table class="table table-sm mb-0"><thead><tr>' +
			"<th></th><th>Spec</th><th>Title</th><th>Script</th><th>Status</th><th></th></tr></thead>" +
			'<tbody id="usis-est-scope-rows"></tbody></table></div></div>' +
			'<div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">' +
			'<h5 class="mb-0">Takeoff</h5>' +
			'<div class="d-flex flex-wrap gap-2 align-items-center">' +
			'<a class="btn btn-sm btn-outline-primary" href="construction/door-schedule.html?id=' +
			encodeURIComponent(doorId) +
			'">Door schedule (Div 08)</a>' +
			'<a class="btn btn-sm btn-outline-secondary" href="construction/drawing-viewer.html?' +
			(projectId ? "project_id=" + encodeURIComponent(projectId) + "&" : "") +
			(leadKey ? "lead_id=" + encodeURIComponent(leadKey) + "&" : "") +
			"estimate_id=" +
			encodeURIComponent(estimateKey) +
			"&from=estimate&return_url=" +
			encodeURIComponent(window.location.href) +
			'">Open drawing viewer</a>' +
			'<button type="button" class="btn btn-sm btn-outline-secondary d-md-none" id="usis-est-takeoff-sort-filter">' +
			'<i class="fa fa-filter me-1"></i> Sort &amp; Filter</button>' +
			'<button type="button" class="btn btn-sm btn-outline-secondary" id="usis-est-takeoff-reset-view">Reset view</button>' +
			'<button type="button" class="btn btn-sm usis-ai-review" id="usis-est-takeoff-firstpass">Run first-pass takeoff</button>' +
			'<button type="button" class="btn btn-sm btn-primary" id="usis-est-takeoff-add">Add line</button></div></div>' +
			'<p class="small mb-2" id="usis-est-takeoff-stepper"></p>' +
			'<div id="usis-grid-est-takeoff" class="border rounded overflow-hidden bg-white mb-2"></div>' +
			'<p class="small text-muted mb-2 d-none" id="usis-est-takeoff-af-status" aria-live="polite"></p>' +
			'<p class="text-muted small mb-0">Writes require <code>TAKEOFF_API_WRITES_ENABLED=1</code> on the API. Use <strong>View</strong> when a line has a drawing to measure on the PDF.</p>';

		var gridEl = document.getElementById("usis-grid-est-takeoff");
		if (typeof Tabulator === "undefined") {
			gridEl.innerHTML =
				'<div class="alert alert-warning mb-0">Takeoff grid requires Tabulator (loaded on this page).</div>';
			return;
		}

		takeoffTable = new Tabulator(gridEl, {
			data: [],
			layout: "fitColumns",
			pagination: "local",
			paginationSize: 25,
			paginationSizeSelector: [10, 25, 50, 100],
			movableColumns: true,
			placeholder: "No takeoff lines yet.",
			columns: buildColumns(projectId),
			cellEdited: function (cell) {
				var field = cell.getField();
				if (field === "id" || field === "extended_total" || field === "measurement_data" || field === "drawing_id") {
					return;
				}
				var oldVal = cell.getOldValue();
				var newVal = cell.getValue();
				if (valuesEqual(oldVal, newVal)) return;

				var row = cell.getRow();
				var id = row.getData().id;
				var body = {};
				body[field] = newVal;

				fetch(apiBase() + "/api/v1/takeoff-lines/" + encodeURIComponent(id), {
					method: "PATCH",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					credentials: "include",
					body: JSON.stringify(body),
				})
					.then(function (res) {
						return res.json().then(function (j) {
							return { res: res, j: j };
						});
					})
					.then(function (pair) {
						if (pair.res.status === 403) {
							var upd = {};
							upd[field] = oldVal;
							row.update(upd);
							notifyErr(pair.j.error || "Takeoff writes disabled");
							return;
						}
						if (!pair.res.ok) throw new Error(pair.j.error || pair.res.status);
						var item = pair.j.item;
						if (item) row.update(item);
					})
					.catch(function (e) {
						var upd = {};
						upd[field] = oldVal;
						row.update(upd);
						notifyErr(e.message || e);
					});
			},
		});

		bindTakeoffAutoFilter(estimateKey);
		if (takeoffTable && typeof takeoffTable.on === "function") {
			takeoffTable.on("tableBuilt", decorateTakeoffHeaders);
		} else {
			setTimeout(decorateTakeoffHeaders, 0);
		}

		bindBidScope(estimateKey, projectId);

		var firstPass = document.getElementById("usis-est-takeoff-firstpass");
		if (firstPass && window.USIS_AI_WORKFLOW) {
			window.USIS_AI_WORKFLOW.ensure({
				processKey: "takeoff",
				subjectType: "estimate",
				subjectId: estimateKey,
				projectId: projectId,
			})
				.then(function (inst) {
					window.USIS_AI_WORKFLOW.renderStepper(document.getElementById("usis-est-takeoff-stepper"), inst);
				})
				.catch(function () {});
			firstPass.addEventListener("click", function () {
				firstPass.disabled = true;
				window.USIS_AI_WORKFLOW.runUntilHuman({
					processKey: "takeoff",
					subjectType: "estimate",
					subjectId: estimateKey,
					projectId: projectId,
					stepperEl: document.getElementById("usis-est-takeoff-stepper"),
					subjectNote: "estimate_id=" + estimateKey + (projectId ? " project_id=" + projectId : ""),
					mode: "estimating_review",
				})
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("First-pass takeoff ready — apply leftovers.");
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					})
					.then(function () {
						firstPass.disabled = false;
					});
			});
		}

		var btn = document.getElementById("usis-est-takeoff-add");
		if (btn) {
			btn.addEventListener("click", function () {
				var desc = window.prompt("Description", "New line");
				if (desc == null) return;
				fetch(apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/takeoff-lines", {
					method: "POST",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					credentials: "include",
					body: JSON.stringify({
						description: String(desc).slice(0, 500),
						quantity: 1,
						unit: "EA",
						unit_cost: 0,
						cost_type: "M",
					}),
				})
					.then(function (res) {
						return res.json().then(function (j) {
							if (res.status === 403) {
								notifyErr(j.error || "Takeoff writes disabled");
								return null;
							}
							if (!res.ok) throw new Error(j.error || res.status);
							return j;
						});
					})
					.then(function (j) {
						if (!j || !j.item) return;
						takeoffTable.addRow(j.item, true);
						lastTakeoffRows = lastTakeoffRows.concat([j.item]);
						applyTakeoffGridFilter();
						if (window.USISNotify) window.USISNotify.success("Line added");
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					});
			});
		}

		reloadTakeoff(estimateKey).catch(function () {});

		var takeoffTab = document.getElementById("estd-tab-takeoff");
		if (takeoffTab && typeof bootstrap !== "undefined" && bootstrap.Tab) {
			takeoffTab.addEventListener("shown.bs.tab", function () {
				if (takeoffTable && typeof takeoffTable.redraw === "function") {
					takeoffTable.redraw(true);
				}
			});
		}
	}

	function onLeadLoaded(ev) {
		var root = document.getElementById("usis-estimate-takeoff-root");
		var lk = leadKeyFromUrl();
		if (!root || !lk) return;
		var detail = ev.detail || {};
		var item = detail.item;
		if (detail.missingEstimate) {
			root.innerHTML =
				'<div class="alert alert-light border mb-0">' +
				'<div class="fw-semibold mb-1">Create an estimate to start takeoff</div>' +
				'<p class="text-muted small mb-2">Takeoff lines are saved on the estimate, not the lead.</p>' +
				'<button type="button" class="btn btn-primary btn-sm" id="usis-estd-takeoff-create">Create estimate</button>' +
				"</div>";
			var takeoffCreate = document.getElementById("usis-estd-takeoff-create");
			if (takeoffCreate) {
				takeoffCreate.addEventListener("click", function () {
					var newEst = document.getElementById("usis-estd-new-estimate");
					if (newEst) newEst.click();
				});
			}
			return;
		}
		if (!item) {
			root.innerHTML =
				'<p class="text-danger small mb-0">' +
				(detail.error ? String(detail.error) : "Could not load estimate.") +
				"</p>";
			return;
		}
		var estimateKey = item.id || lk;
		var leadKey =
			(window.USISEstimateApi && window.USISEstimateApi.leadIdFromItem(item)) ||
			item.lead_id ||
			item.lead_estimate_id ||
			lk;
		var pid = item.drawing_project_id || item.project_id || null;
		if (mountedEstimateKey === estimateKey && activeProjectId === pid) {
			reloadTakeoff(estimateKey).catch(function () {});
			return;
		}
		mountedEstimateKey = estimateKey;
		parentLeadKey = leadKey;
		activeProjectId = pid;
		mountGrid(root, estimateKey, pid, leadKey);
	}

	function init() {
		var lk = leadKeyFromUrl();
		var root = document.getElementById("usis-estimate-takeoff-root");
		var noLead = document.getElementById("usis-estimate-takeoff-no-lead");
		if (!root) return;
		if (!lk) {
			if (noLead) noLead.classList.remove("d-none");
			root.classList.add("d-none");
			return;
		}
		if (noLead) noLead.classList.add("d-none");
		root.classList.remove("d-none");
		root.innerHTML = '<p class="text-muted small mb-0">Loading takeoff…</p>';
		document.addEventListener("usis-lead-estimate-loaded", onLeadLoaded);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
