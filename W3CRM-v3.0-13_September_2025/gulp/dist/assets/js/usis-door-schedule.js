/**
 * Door schedule takeoff — CSV import, opening grid, exploded LEMOS lines via USISPricingLines.
 * Requires URL ?id=<lead_estimate external_id or UUID>.
 */
(function () {
	"use strict";

	var PL = window.USISPricingLines;
	var leadId = null;
	var scheduleData = null;
	var selectedOpeningId = null;
	var scheduleTable = null;
	var pendingCsv = null;
	var hardwareSetCodes = [];

	var DOOR_FIELDS = [
		{ key: "mark", label: "Mark / door no." },
		{ key: "room", label: "Room / location" },
		{ key: "width", label: "Width" },
		{ key: "height", label: "Height" },
		{ key: "size", label: "Size (WxH combined)" },
		{ key: "door_type", label: "Door type" },
		{ key: "frame_type", label: "Frame type" },
		{ key: "hardware_set_code", label: "Hardware set" },
		{ key: "fire_rating", label: "Fire rating" },
		{ key: "handing", label: "Handing" },
		{ key: "remarks", label: "Remarks" },
	];

	var HEADER_ALIASES = {
		mark: ["door no.", "door no", "mark", "door #", "door", "#"],
		room: ["room", "location", "loc"],
		width: ["width", "w"],
		height: ["height", "h"],
		size: ["size", "dimensions"],
		door_type: ["door type", "type", "door"],
		frame_type: ["frame", "frame type"],
		hardware_set_code: ["hardware set", "hw", "hd", "set", "hardware"],
		fire_rating: ["fire rating", "rating"],
		handing: ["hand", "handing", "swing"],
		remarks: ["remarks", "notes", "comment"],
	};

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var port = String(loc.port || "");
		if (["3000", "3001", "3002", "3003"].indexOf(port) >= 0) return "";
		if (loc.hostname === "localhost" || loc.hostname === "127.0.0.1") {
			return loc.protocol + "//" + loc.hostname + ":5000";
		}
		return "";
	}

	function leadKeyFromUrl() {
		return new URLSearchParams(window.location.search).get("id");
	}

	function showErr(msg) {
		var el = document.getElementById("usis-ds-error");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function fetchJson(path, opts) {
		opts = opts || {};
		return fetch(apiBase() + path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts)).then(
			function (r) {
				if (!r.ok) {
					return r.json().then(function (j) {
						throw new Error((j && j.error) || "HTTP " + r.status);
					});
				}
				return r.json();
			}
		);
	}

	function parseCsv(text) {
		var rows = [];
		var i = 0;
		var line = [];
		var cell = "";
		var inQuotes = false;
		while (i < text.length) {
			var ch = text[i];
			if (inQuotes) {
				if (ch === '"') {
					if (text[i + 1] === '"') {
						cell += '"';
						i += 2;
						continue;
					}
					inQuotes = false;
					i++;
					continue;
				}
				cell += ch;
				i++;
				continue;
			}
			if (ch === '"') {
				inQuotes = true;
				i++;
				continue;
			}
			if (ch === ",") {
				line.push(cell);
				cell = "";
				i++;
				continue;
			}
			if (ch === "\r") {
				i++;
				continue;
			}
			if (ch === "\n") {
				line.push(cell);
				rows.push(line);
				line = [];
				cell = "";
				i++;
				continue;
			}
			cell += ch;
			i++;
		}
		if (cell.length || line.length) {
			line.push(cell);
			rows.push(line);
		}
		if (!rows.length) return { headers: [], records: [] };
		var headers = rows[0].map(function (h) {
			return String(h || "").trim();
		});
		var records = [];
		for (var r = 1; r < rows.length; r++) {
			var raw = rows[r];
			if (!raw || !raw.length) continue;
			var empty = true;
			for (var c = 0; c < raw.length; c++) {
				if (String(raw[c] || "").trim()) empty = false;
			}
			if (empty) continue;
			var obj = {};
			for (var j = 0; j < headers.length; j++) {
				if (headers[j]) obj[headers[j]] = raw[j] != null ? String(raw[j]).trim() : "";
			}
			records.push(obj);
		}
		return { headers: headers, records: records };
	}

	function guessColumnMap(headers) {
		var map = {};
		var lower = headers.map(function (h) {
			return String(h || "").trim().toLowerCase();
		});
		DOOR_FIELDS.forEach(function (f) {
			var aliases = HEADER_ALIASES[f.key] || [f.key];
			for (var a = 0; a < aliases.length; a++) {
				var ix = lower.indexOf(aliases[a]);
				if (ix >= 0 && headers[ix]) {
					map[f.key] = headers[ix];
					break;
				}
			}
		});
		return map;
	}

	function loadColumnMapFromStorage() {
		try {
			var raw = sessionStorage.getItem("usis_door_csv_map");
			if (raw) return JSON.parse(raw);
		} catch (e) {
			/* ignore */
		}
		return null;
	}

	function saveColumnMap(map) {
		try {
			sessionStorage.setItem("usis_door_csv_map", JSON.stringify(map));
		} catch (e) {
			/* ignore */
		}
	}

	function renderMapModal(parsed) {
		var headers = parsed.headers;
		var saved = loadColumnMapFromStorage() || guessColumnMap(headers);
		var wrap = document.getElementById("usis-ds-map-fields");
		if (!wrap) return;
		wrap.innerHTML = DOOR_FIELDS.map(function (f) {
			var opts =
				'<option value="">— skip —</option>' +
				headers
					.map(function (h) {
						var sel = saved[f.key] === h ? " selected" : "";
						return '<option value="' + PL.escAttr(h) + '"' + sel + ">" + PL.esc(h) + "</option>";
					})
					.join("");
			return (
				'<div class="col-md-6 col-lg-4">' +
				'<label class="form-label small mb-0">' +
				PL.esc(f.label) +
				"</label>" +
				'<select class="form-select form-select-sm usis-ds-map-sel" data-field="' +
				f.key +
				'">' +
				opts +
				"</select></div>"
			);
		}).join("");

		var thead = document.querySelector("#usis-ds-preview-table thead");
		var tbody = document.querySelector("#usis-ds-preview-table tbody");
		if (thead) {
			thead.innerHTML = "<tr>" + headers.map(function (h) { return "<th>" + PL.esc(h) + "</th>"; }).join("") + "</tr>";
		}
		if (tbody) {
			var preview = parsed.records.slice(0, 5);
			tbody.innerHTML = preview
				.map(function (rec) {
					return (
						"<tr>" +
						headers
							.map(function (h) {
								return "<td>" + PL.esc(rec[h] || "") + "</td>";
							})
							.join("") +
						"</tr>"
					);
				})
				.join("");
		}
	}

	function collectColumnMap() {
		var map = {};
		document.querySelectorAll(".usis-ds-map-sel").forEach(function (sel) {
			var field = sel.getAttribute("data-field");
			var val = sel.value;
			if (field && val) map[field] = val;
		});
		return map;
	}

	function openingSizeLabel(op) {
		var parts = [];
		if (op.width) parts.push(op.width);
		if (op.height) parts.push(op.height);
		return parts.join(" × ");
	}

	function patchOpeningField(openingId, body) {
		return fetchJson("/api/v1/door-openings/" + encodeURIComponent(openingId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		});
	}

	function buildScheduleTable(openings) {
		var el = document.getElementById("usis-ds-schedule-tabulator");
		if (!el || typeof Tabulator === "undefined") return;
		if (scheduleTable) {
			scheduleTable.destroy();
			scheduleTable = null;
		}
		scheduleTable = new Tabulator(el, {
			data: openings,
			layout: "fitColumns",
			height: "420px",
			selectable: 1,
			columns: [
				{ title: "Mark", field: "mark", width: 80 },
				{ title: "Room", field: "room", width: 110 },
				{
					title: "Size",
					field: "width",
					width: 110,
					formatter: function (cell) {
						var d = cell.getRow().getData();
						return openingSizeLabel(d) || "—";
					},
				},
				{ title: "Door", field: "door_type", width: 100 },
				{ title: "Frame", field: "frame_type", width: 100 },
				{
					title: "HD",
					field: "hardware_set_code",
					width: 80,
					editor: "list",
					editorParams: { values: hardwareEditorValues(), autocomplete: true, listOnEmpty: true },
				},
				{
					title: "Lines",
					field: "takeoff_line_count",
					width: 64,
					hozAlign: "right",
				},
				{
					title: "Subtotal",
					field: "extended_total",
					width: 100,
					hozAlign: "right",
					formatter: function (cell) {
						return "$" + PL.money(cell.getValue());
					},
				},
			],
			rowClick: function (e, row) {
				selectOpening(row.getData());
			},
			cellEdited: function (cell) {
				var field = cell.getField();
				if (field !== "hardware_set_code") return;
				var row = cell.getRow().getData();
				if (!row.id) return;
				var val = cell.getValue();
				patchOpeningField(row.id, { hardware_set_code: val == null ? "" : String(val), rebuild_lines: true })
					.then(function (data) {
						var idx = (scheduleData.openings || []).findIndex(function (o) {
							return o.id === row.id;
						});
						if (idx >= 0 && scheduleData.openings) {
							scheduleData.openings[idx] = data.item;
						}
						selectOpening(data.item);
						updateTotals();
					})
					.catch(function (e) {
						showErr(e.message);
						loadSchedule();
					});
			},
		});
	}

	function hardwareEditorValues() {
		var vals = { "": "—" };
		hardwareSetCodes.forEach(function (code) {
			if (code) vals[String(code)] = String(code);
		});
		return vals;
	}

	function loadHardwareSetCodes() {
		return fetchJson("/api/v1/door-hardware-sets").then(function (data) {
			hardwareSetCodes = (data.items || []).map(function (x) {
				return x.code;
			});
		});
	}

	function allTakeoffLines() {
		if (!scheduleData || !scheduleData.openings) return [];
		var out = [];
		scheduleData.openings.forEach(function (op) {
			(op.takeoff_lines || []).forEach(function (ln) {
				out.push(ln);
			});
		});
		return out;
	}

	function selectOpening(op) {
		if (!op) return;
		selectedOpeningId = op.id;
		var markEl = document.getElementById("usis-ds-selected-mark");
		if (markEl) markEl.textContent = op.mark || op.id;
		var lines = op.takeoff_lines || [];
		PL.renderTableBody(lines, {
			tbodyId: "usis-ds-lines-tbody",
			colSpan: 8,
			inputClass: "usis-ds-inp",
		});
		var sub = 0;
		for (var i = 0; i < lines.length; i++) sub += Number(lines[i].extended_total) || 0;
		var ot = document.getElementById("usis-ds-opening-total");
		if (ot) ot.textContent = "$" + PL.money(sub);
		var by = PL.rollupByType(lines);
		var lemos = document.getElementById("usis-ds-lemos-roll");
		if (lemos) {
			lemos.textContent =
				"L " +
				PL.money(by.L) +
				" · M " +
				PL.money(by.M) +
				" · E " +
				PL.money(by.E) +
				" · S " +
				PL.money(by.S) +
				" · O " +
				PL.money(by.O);
		}
	}

	function updateTotals() {
		if (!scheduleData) return;
		var grand = Number(scheduleData.grand_total) || 0;
		var gt = document.getElementById("usis-ds-grand-total");
		if (gt) gt.textContent = "$" + PL.money(grand);
		var oc = document.getElementById("usis-ds-opening-count");
		if (oc) oc.textContent = (scheduleData.opening_count || 0) + " openings";
	}

	function renderSchedule(data) {
		scheduleData = data;
		updateTotals();
		buildScheduleTable(data.openings || []);
		if (data.openings && data.openings.length) {
			var pick = selectedOpeningId
				? data.openings.find(function (o) {
						return o.id === selectedOpeningId;
				  })
				: data.openings[0];
			selectOpening(pick || data.openings[0]);
		}
	}

	function loadSchedule() {
		if (!leadId) return Promise.resolve();
		showErr("");
		return fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(leadId) + "/door-schedule").then(function (data) {
			renderSchedule(data);
			return data;
		});
	}

	function runImport(rows, columnMap, mode) {
		return fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(leadId) + "/door-schedule/import", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ rows: rows, column_map: columnMap, mode: mode || "merge" }),
		}).then(function (data) {
			saveColumnMap(columnMap);
			renderSchedule({
				openings: data.openings || [],
				opening_count: data.opening_count,
				grand_total: (data.openings || []).reduce(function (s, o) {
					return s + (Number(o.extended_total) || 0);
				}, 0),
			});
			if (window.USISNotify) window.USISNotify.success("Imported " + (data.opening_count || 0) + " openings");
		});
	}

	function wirePricingTable() {
		PL.wireTable({
			tbodyId: "usis-ds-lines-tbody",
			inputClass: "usis-ds-inp",
			onLinePatched: function () {
				loadSchedule().catch(function (e) {
					showErr(e.message);
				});
			},
			onReload: function () {
				return loadSchedule();
			},
			onError: showErr,
		});
	}

	function initUi() {
		leadId = leadKeyFromUrl();
		var noLead = document.getElementById("usis-ds-no-lead");
		var root = document.getElementById("usis-ds-root");
		if (!leadId) {
			if (noLead) noLead.classList.remove("d-none");
			if (root) root.classList.add("d-none");
			return;
		}
		if (noLead) noLead.classList.add("d-none");
		if (root) root.classList.remove("d-none");

		var estLink = document.getElementById("usis-ds-estimate-link");
		if (estLink) estLink.href = "estimate-detail.html?id=" + encodeURIComponent(leadId);

		var leadLine = document.getElementById("usis-ds-lead-line");
		if (leadLine) leadLine.textContent = "Lead: " + leadId;

		fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(leadId))
			.then(function (body) {
				var item = body.item || {};
				if (leadLine) {
					leadLine.textContent = (item.name || item.number || leadId) + " (" + leadId + ")";
				}
				if (item.project_id) {
					var pl = document.getElementById("usis-ds-pricing-link");
					if (pl) {
						pl.href = "construction-pricing.html?project_id=" + encodeURIComponent(item.project_id);
						pl.classList.remove("d-none");
					}
				}
			})
			.catch(function () {
				/* optional */
			});

		wirePricingTable();

		document.getElementById("usis-ds-refresh").addEventListener("click", function () {
			loadSchedule().catch(function (e) {
				showErr(e.message);
			});
		});

		document.getElementById("usis-ds-add-opening").addEventListener("click", function () {
			var mark = window.prompt("Door mark (e.g. 101):", "");
			if (mark === null) return;
			fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(leadId) + "/door-openings", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ mark: mark }),
			})
				.then(function () {
					return loadSchedule();
				})
				.catch(function (e) {
					showErr(e.message);
				});
		});

		var fileInput = document.getElementById("usis-ds-csv-file");
		document.getElementById("usis-ds-import-btn").addEventListener("click", function () {
			if (fileInput) fileInput.click();
		});
		fileInput.addEventListener("change", function () {
			var file = fileInput.files && fileInput.files[0];
			fileInput.value = "";
			if (!file) return;
			var reader = new FileReader();
			reader.onload = function () {
				pendingCsv = parseCsv(String(reader.result || ""));
				if (!pendingCsv.records.length) {
					showErr("No data rows found in CSV.");
					return;
				}
				renderMapModal(pendingCsv);
				var modal = document.getElementById("usis-ds-map-modal");
				if (modal && window.bootstrap) {
					window.bootstrap.Modal.getOrCreateInstance(modal).show();
				}
			};
			reader.readAsText(file);
		});

		document.getElementById("usis-ds-map-confirm").addEventListener("click", function () {
			if (!pendingCsv) return;
			var map = collectColumnMap();
			if (!map.mark) {
				showErr("Mark / door number column is required.");
				return;
			}
			var mode = document.getElementById("usis-ds-import-mode").value || "merge";
			runImport(pendingCsv.records, map, mode)
				.then(function () {
					pendingCsv = null;
					var modal = document.getElementById("usis-ds-map-modal");
					if (modal && window.bootstrap) {
						window.bootstrap.Modal.getInstance(modal).hide();
					}
					showErr("");
				})
				.catch(function (e) {
					showErr(e.message);
				});
		});

		loadHardwareSetCodes()
			.then(function () {
				return loadSchedule();
			})
			.catch(function (e) {
				showErr(e.message);
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", initUi);
	} else {
		initUi();
	}
})();
