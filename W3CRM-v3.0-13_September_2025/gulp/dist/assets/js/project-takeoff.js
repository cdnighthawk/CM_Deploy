/**
 * Project-scoped takeoff (Plan 3) — GET/POST /api/v1/projects/<id>/takeoff-lines,
 * PATCH/DELETE /api/v1/takeoff-lines/<line_id>. Editable Tabulator grid.
 */
(function () {
	"use strict";

	var takeoffTable = null;

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				if (s && new URL(s).origin !== window.location.origin) return s;
			} catch (e) {
				if (s) return s;
			}
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		if (["3000", "3001", "5173", "8080"].indexOf(port) >= 0) return proto + "//" + host + ":5000";
		if ((host === "localhost" || host === "127.0.0.1") && port && port !== "5000") return proto + "//" + host + ":5000";
		return "";
	}

	function projectId() {
		return new URLSearchParams(window.location.search).get("id");
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

	function buildColumns(pid) {
		return [
			{ title: "Sort", field: "sort_order", width: 72, editor: "number", hozAlign: "right" },
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
					if (!did || !pid) return "—";
					var href =
						"construction/drawing-viewer.html?project_id=" +
						encodeURIComponent(pid) +
						"&drawing_id=" +
						encodeURIComponent(did) +
						"&takeoff_line=" +
						encodeURIComponent(row.id);
					var a = document.createElement("a");
					a.className = "small";
					a.href = href;
					a.textContent = "View";
					return a;
				},
			},
			{
				title: "",
				field: "id",
				width: 64,
				headerSort: false,
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
							credentials: "omit",
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

	function reloadTakeoff(pid) {
		return fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(pid) + "/takeoff-lines", {
			credentials: "omit",
		})
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				var rows = data.items || [];
				if (takeoffTable) takeoffTable.setData(rows);
				return rows;
			})
			.catch(function (e) {
				notifyErr("Could not load takeoff lines: " + (e.message || e));
				if (takeoffTable) takeoffTable.setData([]);
				throw e;
			});
	}

	function mountGrid(root, pid) {
		root.innerHTML =
			'<div class="d-flex justify-content-between align-items-center mb-2">' +
			'<h5 class="mb-0">Takeoff</h5>' +
			'<button type="button" class="btn btn-sm btn-primary" id="usis-proj-takeoff-add">Add line</button></div>' +
			'<div id="usis-grid-takeoff" class="border rounded overflow-hidden bg-white mb-2"></div>' +
			'<p class="text-muted small mb-0">Writes require <code>TAKEOFF_API_WRITES_ENABLED=1</code> on the API.</p>';

		var gridEl = document.getElementById("usis-grid-takeoff");
		if (typeof Tabulator === "undefined") {
			gridEl.innerHTML =
				'<div class="alert alert-warning mb-0">Takeoff grid requires Tabulator (same CDN as Drawings tab).</div>';
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
			columns: buildColumns(pid),
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
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
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

		var btn = document.getElementById("usis-proj-takeoff-add");
		if (btn) {
			btn.addEventListener("click", function () {
				var desc = window.prompt("Description", "New line");
				if (desc == null) return;
				fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(pid) + "/takeoff-lines", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
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
						if (window.USISNotify) window.USISNotify.success("Line added");
					})
					.catch(function (e) {
						notifyErr(e.message || e);
					});
			});
		}

		reloadTakeoff(pid).catch(function () {});

		var takeoffTab = document.getElementById("proj-tab-takeoff");
		if (takeoffTab && typeof bootstrap !== "undefined" && bootstrap.Tab) {
			takeoffTab.addEventListener("shown.bs.tab", function () {
				if (takeoffTable && typeof takeoffTable.redraw === "function") {
					takeoffTable.redraw(true);
				}
			});
		}
	}

	function init() {
		var root = document.getElementById("usis-project-takeoff-root");
		if (!root) return;
		var pid = projectId();
		if (!pid) {
			root.innerHTML = '<p class="text-muted">Open from Projects with a project id in the URL.</p>';
			return;
		}
		mountGrid(root, pid);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
