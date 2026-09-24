/**
 * Estimate Takeoff → Openings workspace (door / frame / hardware).
 */
(function (global) {
	"use strict";

	var estimateKey = null;
	var openingsTable = null;
	var openingsAf = null;
	var lastOpeningRows = [];
	var state = { openings: [], sets: [], reconcile: {}, labor: {}, selectedSetId: null };

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string") return window.USIS_API_BASE.trim().replace(/\/$/, "");
		return "";
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function notifyErr(msg) {
		if (window.USISNotify && window.USISNotify.error) window.USISNotify.error(String(msg));
		else window.alert(String(msg));
	}

	function fetchJson(path, opts) {
		opts = opts || {};
		return fetch(apiBase() + path, {
			method: opts.method || "GET",
			headers: { Accept: "application/json", "Content-Type": "application/json" },
			credentials: "include",
			body: opts.body ? JSON.stringify(opts.body) : undefined,
		}).then(function (res) {
			return res.json().then(function (j) {
				if (!res.ok) throw new Error(j.error || res.statusText);
				return j;
			});
		});
	}

	function chip(key) {
		var sev = {
			missing_set: "critical",
			unknown_set: "critical",
			unconfirmed: "critical",
			pair_mismatch: "critical",
			rating_mismatch: "critical",
			hinge_count: "major",
			no_size: "major",
			addendum: "major",
			no_hand: "minor",
			orphan_set: "minor",
			electrified: "info",
			nic: "info",
		}[key] || "info";
		if (window.USISUi && window.USISUi.severityChip) {
			return '<span class="me-1" title="' + esc(key) + '">' + window.USISUi.severityChip(sev) + " " + esc(key) + "</span>";
		}
		return '<span class="badge text-bg-light me-1">' + esc(key) + "</span>";
	}

	function sizeLabel(row) {
		if (row.width_in && row.height_in) return row.width_in + '" × ' + row.height_in + '"';
		return "—";
	}

	function emptyHtml() {
		if (window.USISUi && window.USISUi.emptyState) {
			return window.USISUi.emptyState({
				icon: "icon-grid",
				title: "No openings yet",
				body: "Import a door schedule CSV, add a mark, or extract from a schedule sheet.",
			});
		}
		return '<p class="text-muted small mb-0">No openings yet.</p>';
	}

	function reconcileBar(recon) {
		recon = recon || {};
		var chips = [
			["In scope", recon.openings_in_scope || 0],
			["Missing set", recon.missing_set || 0],
			["Unknown set", recon.unknown_set || 0],
			["Orphan set", recon.orphan_set || 0],
			["Pair mismatch", recon.pair_mismatch || 0],
			["Unconfirmed", recon.unconfirmed || 0],
			["Electrified", recon.electrified || 0],
		];
		return (
			'<div class="d-flex flex-wrap gap-2 align-items-center small" id="usis-openings-reconcile">' +
			chips
				.map(function (c) {
					return (
						'<span class="badge text-bg-light">' +
						esc(c[0]) +
						": <strong>" +
						c[1] +
						"</strong></span>"
					);
				})
				.join("") +
			(recon.apply_blocked
				? '<span class="badge text-bg-warning">Apply blocked</span>'
				: '<span class="badge text-bg-success">Ready to apply</span>') +
			"</div>"
		);
	}

	function setListHtml() {
		if (!state.sets.length) {
			return '<p class="text-muted small mb-0">No hardware sets. Import 08 71 00 or add a set.</p>';
		}
		return state.sets
			.map(function (s) {
				var active = s.id === state.selectedSetId ? " active" : "";
				return (
					'<button type="button" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center' +
					active +
					'" data-set-id="' +
					esc(s.id) +
					'"><span><strong>' +
					esc(s.set_no) +
					"</strong> " +
					esc(s.title || "") +
					'</span><span class="badge text-bg-light">' +
					(s.opening_count || 0) +
					"</span></button>"
				);
			})
			.join("");
	}

	function selectedSet() {
		return state.sets.find(function (s) {
			return s.id === state.selectedSetId;
		});
	}

	function setDetailHtml() {
		var s = selectedSet();
		if (!s) return '<p class="text-muted small mb-0">Select a set.</p>';
		var items = (s.items || [])
			.map(function (it) {
				return (
					"<tr><td>" +
					esc(it.qty) +
					"</td><td>" +
					esc(it.category) +
					"</td><td>" +
					esc(it.description) +
					"</td><td>" +
					esc(it.manufacturer || "") +
					"</td><td>" +
					esc(it.catalog || "") +
					"</td><td>" +
					esc(it.finish || "") +
					"</td></tr>"
				);
			})
			.join("");
		return (
			'<div class="d-flex justify-content-between align-items-start mb-2"><div><h6 class="mb-0">Set ' +
			esc(s.set_no) +
			"</h6><p class=\"small text-muted mb-1\">Used by: " +
			esc((s.used_by || []).join(", ") || "—") +
			"</p></div>" +
			'<button type="button" class="btn btn-sm btn-outline-danger" id="usis-openings-set-del">Delete set</button></div>' +
			'<div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>Qty</th><th>Cat</th><th>Description</th><th>Mfr</th><th>Catalog</th><th>Finish</th></tr></thead><tbody>' +
			(items || '<tr><td colspan="6" class="text-muted">No items</td></tr>') +
			"</tbody></table></div>"
		);
	}

	function laborFields(labor) {
		labor = labor || {};
		var fields = [
			["frame_kd_hm", "Frame KD HM"],
			["frame_welded_hm", "Frame welded HM"],
			["door_standard", "Door + standard HW"],
			["door_exit_device", "Door + exit device"],
			["closer_adjust", "Closer adjust"],
			["rated_extra", "Rated extra"],
		];
		return fields
			.map(function (f) {
				return (
					'<div class="col-6 col-md-4"><label class="form-label small mb-0">' +
					esc(f[1]) +
					'</label><input type="number" step="0.05" class="form-control form-control-sm" data-labor-key="' +
					f[0] +
					'" value="' +
					esc(labor[f[0]] != null ? labor[f[0]] : "") +
					'"></div>'
				);
			})
			.join("");
	}

	function editorFields(row) {
		row = row || {};
		function inp(name, label, val) {
			return (
				'<div class="col-md-4 mb-2"><label class="form-label small mb-0">' +
				esc(label) +
				'</label><input class="form-control form-control-sm" name="' +
				name +
				'" value="' +
				esc(val == null ? "" : val) +
				'"></div>'
			);
		}
		return (
			'<form id="usis-openings-editor-form" class="row g-2">' +
			inp("mark", "Mark", row.mark) +
			inp("qty", "Qty", row.qty || 1) +
			inp("leaf_count", "Leaf count", row.leaf_count || 1) +
			inp("width_in", "Width in", row.width_in) +
			inp("height_in", "Height in", row.height_in) +
			inp("hand", "Hand", row.hand) +
			inp("fire_rating_min", "Rating min", row.fire_rating_min) +
			inp("material", "Material", row.material) +
			inp("door_type_code", "Door type", row.door_type_code) +
			inp("frame_type_code", "Frame type", row.frame_type_code) +
			inp("frame_material", "Frame material", row.frame_material) +
			inp("frame_construction", "Frame construction", row.frame_construction) +
			inp("wall_thickness_in", "Wall / throat in", row.wall_thickness_in) +
			inp("frame_gauge", "Frame gauge", row.frame_gauge) +
			inp("hardware_set_no", "Hardware set", row.hardware_set_no) +
			inp("location", "Location", row.location) +
			inp("sheet_ref", "Sheet", row.sheet_ref) +
			inp("scope_flag", "Scope", row.scope_flag || "in") +
			'<div class="col-12 mb-2"><label class="form-label small mb-0">Remarks</label><textarea class="form-control form-control-sm" name="remarks" rows="2">' +
			esc(row.remarks || "") +
			"</textarea></div></form>"
		);
	}

	function formPayload(form) {
		var data = {};
		Array.prototype.forEach.call(form.elements, function (el) {
			if (!el.name) return;
			data[el.name] = el.value;
		});
		["qty", "leaf_count", "width_in", "height_in", "wall_thickness_in", "fire_rating_min"].forEach(function (k) {
			if (data[k] === "") data[k] = null;
			else if (data[k] != null) data[k] = Number(data[k]);
		});
		return data;
	}

	function showEditor(row) {
		var body = document.getElementById("usis-openings-offcanvas-body");
		if (!body) return;
		body.innerHTML =
			editorFields(row) +
			'<div class="mt-3 d-flex gap-2"><button type="button" class="btn btn-primary btn-sm" id="usis-openings-save">Save</button>' +
			(row && row.id
				? '<button type="button" class="btn btn-outline-danger btn-sm" id="usis-openings-del">Delete</button>'
				: "") +
			"</div>";
		var canvas = document.getElementById("usis-openings-offcanvas");
		if (canvas && window.bootstrap && bootstrap.Offcanvas) {
			bootstrap.Offcanvas.getOrCreateInstance(canvas).show();
		}
		var save = document.getElementById("usis-openings-save");
		if (save) {
			save.addEventListener("click", function () {
				var form = document.getElementById("usis-openings-editor-form");
				var payload = formPayload(form);
				var req = row && row.id
					? fetchJson("/api/v1/estimates/" + estimateKey + "/openings/" + row.id, { method: "PATCH", body: payload })
					: fetchJson("/api/v1/estimates/" + estimateKey + "/openings", { method: "POST", body: payload });
				req.then(function () {
					if (window.USISNotify) window.USISNotify.success("Opening saved");
					return reload();
				}).catch(function (e) {
					notifyErr(e.message || e);
				});
			});
		}
		var del = document.getElementById("usis-openings-del");
		if (del && row && row.id) {
			del.addEventListener("click", function () {
				if (!window.confirm("Delete opening " + (row.mark || "") + "?")) return;
				fetchJson("/api/v1/estimates/" + estimateKey + "/openings/" + row.id, { method: "DELETE" })
					.then(reload)
					.catch(function (e) {
						notifyErr(e.message || e);
					});
			});
		}
	}

	function bindSetList() {
		var list = document.getElementById("usis-openings-set-list");
		if (!list) return;
		list.querySelectorAll("[data-set-id]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				state.selectedSetId = btn.getAttribute("data-set-id");
				document.getElementById("usis-openings-set-detail").innerHTML = setDetailHtml();
				bindSetDetail();
				list.querySelectorAll(".list-group-item").forEach(function (el) {
					el.classList.toggle("active", el.getAttribute("data-set-id") === state.selectedSetId);
				});
			});
		});
	}

	function bindSetDetail() {
		var del = document.getElementById("usis-openings-set-del");
		if (!del || !state.selectedSetId) return;
		del.addEventListener("click", function () {
			if (!window.confirm("Delete this hardware set? Openings will show unknown_set.")) return;
			fetchJson("/api/v1/estimates/" + estimateKey + "/hardware-sets/" + state.selectedSetId, { method: "DELETE" })
				.then(function () {
					state.selectedSetId = null;
					return reload();
				})
				.catch(function (e) {
					notifyErr(e.message || e);
				});
		});
	}

	function laborPayload() {
		var hours = {};
		document.querySelectorAll("[data-labor-key]").forEach(function (el) {
			hours[el.getAttribute("data-labor-key")] = Number(el.value || 0);
		});
		return hours;
	}

	function bindToolbar() {
		var add = document.getElementById("usis-openings-add");
		if (add) add.addEventListener("click", function () { showEditor({ qty: 1, leaf_count: 1, scope_flag: "in" }); });
		var addSet = document.getElementById("usis-openings-add-set");
		if (addSet) {
			addSet.addEventListener("click", function () {
				var no = window.prompt("Set number", "08");
				if (!no) return;
				fetchJson("/api/v1/estimates/" + estimateKey + "/hardware-sets", { method: "POST", body: { set_no: no } })
					.then(reload)
					.catch(function (e) { notifyErr(e.message || e); });
			});
		}
		var exp = document.getElementById("usis-openings-export");
		if (exp) {
			exp.addEventListener("click", function () {
				window.location.href = apiBase() + "/api/v1/estimates/" + estimateKey + "/openings/export";
			});
		}
		var imp = document.getElementById("usis-openings-import");
		var file = document.getElementById("usis-openings-import-file");
		if (imp && file) {
			imp.addEventListener("click", function () { file.click(); });
			file.addEventListener("change", function () {
				var f = file.files && file.files[0];
				if (!f) return;
				var reader = new FileReader();
				reader.onload = function () {
					var text = String(reader.result || "");
					var lines = text.split(/\r?\n/).filter(Boolean);
					if (!lines.length) return;
					var headers = lines[0].split(",").map(function (h) { return h.trim(); });
					var rows = lines.slice(1).map(function (ln) {
						var cols = ln.split(",");
						var o = {};
						headers.forEach(function (h, i) { o[h] = cols[i]; });
						return o;
					});
					fetchJson("/api/v1/estimates/" + estimateKey + "/openings/import", { method: "POST", body: { rows: rows } })
						.then(function () {
							if (window.USISNotify) window.USISNotify.success("Openings imported");
							return reload();
						})
						.catch(function (e) { notifyErr(e.message || e); });
				};
				reader.readAsText(f);
				file.value = "";
			});
		}
		var apply = document.getElementById("usis-openings-apply");
		if (apply) {
			apply.addEventListener("click", function () {
				var body = {
					roll_up: document.getElementById("usis-openings-rollup") ? document.getElementById("usis-openings-rollup").checked : true,
					include_labor: document.getElementById("usis-openings-labor") ? document.getElementById("usis-openings-labor").checked : false,
					door_frame_only: document.getElementById("usis-openings-dfonly") ? document.getElementById("usis-openings-dfonly").checked : false,
					labor_hours: laborPayload(),
					preview: true,
				};
				fetchJson("/api/v1/estimates/" + estimateKey + "/openings/apply", { method: "POST", body: body })
					.then(function (prev) {
						var lines = (prev.diffs || []).map(function (d) {
							return (d.line_role || "") + " " + (d.description || "") + ": " + d.from_qty + " → " + d.to_qty;
						});
						if (!window.confirm((lines.length ? lines.join("\n") : "Apply openings to takeoff?") + "\n\nConfirm Apply?")) return;
						body.preview = false;
						return fetchJson("/api/v1/estimates/" + estimateKey + "/openings/apply", { method: "POST", body: body });
					})
					.then(function (res) {
						if (!res) return;
						if (window.USISNotify) window.USISNotify.success("Applied " + (res.line_count || 0) + " takeoff lines");
					})
					.catch(function (e) { notifyErr(e.message || e); });
			});
		}
		var rfp = document.getElementById("usis-openings-draft-rfps");
		if (rfp) {
			rfp.addEventListener("click", function () {
				fetchJson("/api/v1/estimates/" + estimateKey + "/openings/draft-rfps", { method: "POST", body: {} })
					.then(function (d) {
						if (window.USISNotify) window.USISNotify.success("Drafted " + ((d.items || []).length) + " RFPs");
					})
					.catch(function (e) { notifyErr(e.message || e); });
			});
		}
		["usis-openings-extract-sched", "usis-openings-extract-hw"].forEach(function (id) {
			var btn = document.getElementById(id);
			if (!btn) return;
			btn.addEventListener("click", function () {
				var mode = id.indexOf("hw") >= 0 ? "hardware_set_extract" : "door_schedule_extract";
				if (window.USIS_AI_CHAT && window.USIS_AI_CHAT.setMode) window.USIS_AI_CHAT.setMode(mode);
				if (window.aiReviewBus) window.aiReviewBus.emit("review-request", { mode: mode, estimateId: estimateKey });
				var pasted = window.prompt("Paste TSV / CSV for review (Confirm writes). Empty cancels.", "");
				if (pasted == null || !String(pasted).trim()) return;
				fetchJson("/api/v1/estimates/" + estimateKey + "/openings/extract", {
					method: "POST",
					body: { mode: mode, tsv: pasted },
				})
					.then(function (review) {
						var n = (review.openings || []).length + (review.sets || []).length;
						if (!window.confirm("Review " + n + " proposed rows. Confirm write to register?")) return;
						return fetchJson("/api/v1/estimates/" + estimateKey + "/openings/extract/confirm", {
							method: "POST",
							body: { mode: mode, tsv: pasted, confirm: true },
						});
					})
					.then(function (res) {
						if (!res) return;
						return reload();
					})
					.catch(function (e) { notifyErr(e.message || e); });
			});
		});
	}

	function bindTakeoffAutoFilter() {
		if (!window.USIS_TABLE_AUTOFILTER) return;
		if (openingsAf && openingsAf.destroy) openingsAf.destroy();
		openingsAf = window.USIS_TABLE_AUTOFILTER.bind({
			table: null,
			tableId: "estimate.openings:" + estimateKey,
			getRows: function () {
				return lastOpeningRows;
			},
		});
	}

	function renderGrid() {
		var el = document.getElementById("usis-openings-grid");
		if (!el || typeof Tabulator === "undefined") return;
		lastOpeningRows = state.openings || [];
		if (openingsTable) {
			openingsTable.replaceData(lastOpeningRows);
			return;
		}
		openingsTable = new Tabulator(el, {
			data: lastOpeningRows,
			layout: "fitColumns",
			placeholder: "No openings yet.",
			columns: [
				{ title: "Mark", field: "mark", width: 80 },
				{ title: "Qty", field: "qty", width: 60 },
				{ title: "Size", field: "width_in", width: 110, formatter: function (c) { return sizeLabel(c.getData()); } },
				{ title: "Hand", field: "hand", width: 70 },
				{ title: "Rating", field: "fire_rating_min", width: 80 },
				{ title: "Door", field: "door_type_code", width: 80 },
				{ title: "Frame", field: "frame_type_code", width: 80 },
				{ title: "Mat", field: "material", width: 70 },
				{ title: "Set", field: "hardware_set_no", width: 70 },
				{ title: "Location", field: "location" },
				{ title: "Scope", field: "scope_flag", width: 70 },
				{
					title: "Conflicts",
					field: "conflicts",
					formatter: function (c) {
						var active = ((c.getValue() || {}).active) || [];
						return active.map(chip).join("") || "—";
					},
				},
			],
		});
		openingsTable.on("rowClick", function (e, row) {
			showEditor(row.getData());
		});
		bindTakeoffAutoFilter();
	}

	function applyState(data) {
		state.openings = data.openings || [];
		state.sets = data.sets || [];
		state.reconcile = data.reconcile || {};
		state.labor = data.labor_defaults || {};
		if (!state.selectedSetId && state.sets[0]) state.selectedSetId = state.sets[0].id;
		var bar = document.getElementById("usis-openings-reconcile-wrap");
		if (bar) bar.innerHTML = reconcileBar(state.reconcile);
		var empty = document.getElementById("usis-openings-empty");
		if (empty) empty.innerHTML = state.openings.length ? "" : emptyHtml();
		var list = document.getElementById("usis-openings-set-list");
		if (list) list.innerHTML = setListHtml();
		var detail = document.getElementById("usis-openings-set-detail");
		if (detail) detail.innerHTML = setDetailHtml();
		var labor = document.getElementById("usis-openings-labor-fields");
		if (labor) labor.innerHTML = laborFields(state.labor);
		bindSetList();
		bindSetDetail();
		renderGrid();
	}

	function reload() {
		if (!estimateKey) return Promise.resolve();
		return fetchJson("/api/v1/estimates/" + encodeURIComponent(estimateKey) + "/openings").then(applyState);
	}

	function shellHtml() {
		return (
			'<div class="border rounded p-2 mb-3 bg-light" id="usis-openings-reconcile-wrap"></div>' +
			'<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">' +
			'<div class="d-flex flex-wrap gap-2">' +
			'<button type="button" class="btn btn-sm btn-primary" id="usis-openings-add">Add opening</button>' +
			'<button type="button" class="btn btn-sm btn-outline-primary" id="usis-openings-import">Import CSV</button>' +
			'<input type="file" accept=".csv,.txt" class="d-none" id="usis-openings-import-file">' +
			'<button type="button" class="btn btn-sm btn-outline-secondary" id="usis-openings-export">Export CSV</button>' +
			'<button type="button" class="btn btn-sm usis-ai-review" id="usis-openings-extract-sched">Extract schedule</button>' +
			'<button type="button" class="btn btn-sm usis-ai-review" id="usis-openings-extract-hw">Extract hardware sets</button>' +
			"</div>" +
			'<a class="btn btn-sm btn-outline-secondary" href="construction/hardware-schedules.html">Company hardware library</a>' +
			"</div>" +
			'<div id="usis-openings-empty"></div>' +
			'<div id="usis-openings-grid" class="border rounded overflow-hidden bg-white mb-3"></div>' +
			'<div class="row g-3 mb-3"><div class="col-md-4"><div class="card"><div class="card-header py-2 d-flex justify-content-between"><span class="fw-semibold">Hardware sets</span>' +
			'<button type="button" class="btn btn-sm btn-outline-primary" id="usis-openings-add-set">New set</button></div>' +
			'<div class="list-group list-group-flush" id="usis-openings-set-list"></div></div></div>' +
			'<div class="col-md-8"><div class="card"><div class="card-body" id="usis-openings-set-detail"></div></div></div></div>' +
			'<div class="border rounded p-3"><h6>Apply to estimate</h6>' +
			'<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="usis-openings-rollup" checked><label class="form-check-label small" for="usis-openings-rollup">Roll up</label></div>' +
			'<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="usis-openings-labor"><label class="form-check-label small" for="usis-openings-labor">Include labor</label></div>' +
			'<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" id="usis-openings-dfonly"><label class="form-check-label small" for="usis-openings-dfonly">Door / frame only</label></div>' +
			'<div class="row g-2 mt-2" id="usis-openings-labor-fields"></div>' +
			'<div class="mt-3 d-flex gap-2"><button type="button" class="btn btn-sm btn-primary" id="usis-openings-apply">Apply / Re-apply</button>' +
			'<button type="button" class="btn btn-sm btn-outline-primary" id="usis-openings-draft-rfps">Create draft RFPs</button></div></div>' +
			'<div class="offcanvas offcanvas-end" tabindex="-1" id="usis-openings-offcanvas"><div class="offcanvas-header"><h5 class="offcanvas-title">Opening</h5>' +
			'<button type="button" class="btn-close" data-bs-dismiss="offcanvas"></button></div><div class="offcanvas-body" id="usis-openings-offcanvas-body"></div></div>'
		);
	}

	function mount(root, key) {
		if (!root) return;
		estimateKey = key;
		root.innerHTML = shellHtml();
		bindToolbar();
		reload().catch(function (e) {
			notifyErr(e.message || e);
		});
	}

	global.USISEstimateOpenings = { mount: mount, reload: reload };
})(window);
