/**
 * Active project detail — Job info tab from GET /api/v1/projects/<uuid>.
 */
(function () {
	"use strict";

	var lastProjectId = null;
	var lastProjectItem = null;
	var lastLeadItem = null;
	var lastSageProjectIdStr = "";
	var lastContractItems = [];
	var lastPrimeContractValueNum = null;
	var invoiceMethods = [];
	var lastOffices = [];
	var INVOICE_ADD_NEW = "__add_new__";

	function metaApiBase() {
		if (typeof document === "undefined" || !document.querySelector) return null;
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		return window.USIS_API.apiBase();
	}

	function projectIdFromQuery() {
		if (window.USISProjectContext && typeof window.USISProjectContext.projectIdFromQuery === "function") {
			return window.USISProjectContext.projectIdFromQuery();
		}
		var p = new URLSearchParams(window.location.search);
		var id = (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim();
		return id || null;
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fmtDash(s) {
		if (s == null || String(s).trim() === "") return '<span class="text-muted">—</span>';
		return esc(String(s).trim());
	}

	function fmtDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			return esc(d.toLocaleDateString());
		} catch (e) {
			return esc(String(iso));
		}
	}

	function fmtMoney(n) {
		if (n == null || n === "") return '<span class="text-muted">—</span>';
		var x = Number(n);
		if (isNaN(x)) return esc(String(n));
		try {
			return esc(
				x.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
			);
		} catch (e) {
			return esc(String(x));
		}
	}

	function fmtBool(b) {
		return b ? "Yes" : "No";
	}

	function isoToInputDate(iso) {
		if (!iso) return "";
		return String(iso).slice(0, 10);
	}

	function fmtDatePlain(iso) {
		if (!iso) return "—";
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return String(iso);
			return d.toLocaleDateString();
		} catch (e) {
			return "—";
		}
	}

	function moneyPlain(n) {
		if (n == null || n === "") return "—";
		var x = Number(n);
		if (isNaN(x)) return String(n);
		try {
			return x.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
		} catch (e) {
			return String(x);
		}
	}

	function setTextById(id, text) {
		var el = document.getElementById(id);
		if (el) el.textContent = text == null ? "—" : String(text);
	}

	function parseCommitmentAmount(raw) {
		if (raw == null || raw === "") return 0;
		var n = Number(raw);
		return isNaN(n) ? 0 : n;
	}

	function updateCopySageButton() {
		var copyBtn = document.getElementById("usis-ca-copy-sage");
		if (!copyBtn) return;
		if (lastSageProjectIdStr) {
			copyBtn.classList.remove("d-none");
			copyBtn.removeAttribute("disabled");
		} else {
			copyBtn.classList.add("d-none");
			copyBtn.setAttribute("disabled", "disabled");
		}
	}

	function copyTextToClipboard(text) {
		if (!text) return Promise.reject(new Error("empty"));
		if (navigator.clipboard && navigator.clipboard.writeText) {
			return navigator.clipboard.writeText(text);
		}
		return new Promise(function (resolve, reject) {
			var ta = document.createElement("textarea");
			ta.value = text;
			ta.setAttribute("readonly", "");
			ta.style.position = "fixed";
			ta.style.left = "-9999px";
			document.body.appendChild(ta);
			ta.select();
			try {
				if (document.execCommand("copy")) resolve();
				else reject(new Error("copy failed"));
			} catch (e) {
				reject(e);
			}
			document.body.removeChild(ta);
		});
	}

	function fillContractAdminFromProject(item) {
		lastSageProjectIdStr =
			item && item.sage_project_id && String(item.sage_project_id).trim()
				? String(item.sage_project_id).trim()
				: "";
		lastPrimeContractValueNum =
			item && item.contract_value != null && String(item.contract_value).trim() !== ""
				? Number(item.contract_value)
				: null;
		if (lastPrimeContractValueNum != null && isNaN(lastPrimeContractValueNum)) {
			lastPrimeContractValueNum = null;
		}
		setTextById("usis-ca-prime-contract-value", moneyPlain(item.contract_value));
		setTextById("usis-ca-prime-contract-date", fmtDatePlain(item.contract_date));
		setTextById("usis-ca-prime-start", fmtDatePlain(item.start_date));
		setTextById("usis-ca-prime-substantial", fmtDatePlain(item.substantial_completion_date));
		setTextById("usis-ca-prime-closeout", fmtDatePlain(item.closeout_date));
		setTextById(
			"usis-ca-prime-retention",
			item.retention_percentage != null ? String(item.retention_percentage) : "—"
		);
		setTextById("usis-ca-prime-sage-id", lastSageProjectIdStr ? lastSageProjectIdStr : "—");
		setTextById("usis-ca-prevailing", fmtBool(!!item.prevailing_wage));
		setTextById("usis-ca-dbe", fmtBool(!!item.dbe_required));
		updateCopySageButton();
		loadProjectContracts();
	}

	function setContractErr(msg) {
		var el = document.getElementById("usis-ca-c-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function contractModal() {
		var el = document.getElementById("usis-modal-project-contract");
		if (!el || !window.bootstrap) return null;
		return window.bootstrap.Modal.getOrCreateInstance(el);
	}

	function fillContractForm(item) {
		document.getElementById("usis-ca-c-id").value = item && item.id ? item.id : "";
		document.getElementById("usis-ca-c-number").value = (item && item.contract_number) || "";
		document.getElementById("usis-ca-c-title").value = (item && item.title) || "";
		document.getElementById("usis-ca-c-value").value =
			item && item.contract_value != null ? String(item.contract_value) : "";
		document.getElementById("usis-ca-c-date").value = isoToInputDate(item && item.contract_date);
		document.getElementById("usis-ca-c-retention").value =
			item && item.retention_percentage != null ? String(item.retention_percentage) : "";
		document.getElementById("usis-ca-c-start").value = isoToInputDate(item && item.start_date);
		document.getElementById("usis-ca-c-substantial").value = isoToInputDate(
			item && item.substantial_completion_date
		);
		document.getElementById("usis-ca-c-closeout").value = isoToInputDate(item && item.closeout_date);
		document.getElementById("usis-ca-c-notes").value = (item && item.notes) || "";
		document.getElementById("usis-ca-c-primary").checked = !!(item && item.is_primary);
		var label = document.getElementById("usis-modal-project-contract-label");
		if (label) label.textContent = item && item.id ? "Edit contract" : "Add contract";
		setContractErr("");
	}

	function contractFormPayload() {
		return {
			contract_number: document.getElementById("usis-ca-c-number").value.trim() || null,
			title: document.getElementById("usis-ca-c-title").value.trim(),
			contract_value: document.getElementById("usis-ca-c-value").value.trim() || null,
			contract_date: document.getElementById("usis-ca-c-date").value || null,
			retention_percentage: document.getElementById("usis-ca-c-retention").value.trim() || null,
			start_date: document.getElementById("usis-ca-c-start").value || null,
			substantial_completion_date: document.getElementById("usis-ca-c-substantial").value || null,
			closeout_date: document.getElementById("usis-ca-c-closeout").value || null,
			notes: document.getElementById("usis-ca-c-notes").value.trim() || null,
			is_primary: document.getElementById("usis-ca-c-primary").checked,
		};
	}

	function renderProjectContracts(data) {
		var ownerEl = document.getElementById("usis-ca-contract-owner");
		if (ownerEl) {
			var ownerName = (data && data.owner_company_name) || (lastProjectItem && lastProjectItem.owner_company_name);
			ownerEl.textContent = "Owner: " + (ownerName && String(ownerName).trim() ? ownerName : "— (set on Job info)");
		}
		var items = (data && data.items) || [];
		lastContractItems = items;
		var totalEl = document.getElementById("usis-ca-contract-total");
		if (totalEl) {
			var total = data && data.total_contract_value;
			if (items.length > 1 && total != null) {
				totalEl.textContent = items.length + " contracts · combined value " + moneyPlain(total);
			} else if (items.length > 1) {
				totalEl.textContent = items.length + " contracts";
			} else {
				totalEl.textContent = "";
			}
		}
		var tbody = document.getElementById("usis-ca-contract-tbody");
		if (!tbody) return;
		var rows = (data && data.items) || [];
		if (!rows.length) {
			tbody.innerHTML =
				'<tr><td colspan="6" class="text-muted">No owner contracts yet. Add the first contract for this job.</td></tr>';
			return;
		}
		tbody.innerHTML = rows
			.map(function (row) {
				var badge = row.is_primary
					? '<span class="badge text-bg-primary">Primary</span>'
					: "";
				var delBtn = row.is_primary
					? ""
					: '<button type="button" class="btn btn-link btn-sm text-danger p-0 usis-ca-c-del" data-id="' +
						esc(row.id) +
						'">Delete</button>';
				return (
					"<tr>" +
					"<td>" +
					fmtDash(row.contract_number) +
					"</td>" +
					"<td>" +
					fmtDash(row.title) +
					"</td>" +
					'<td class="text-end">' +
					fmtMoney(row.contract_value) +
					"</td>" +
					"<td>" +
					fmtDate(row.contract_date) +
					"</td>" +
					"<td>" +
					badge +
					"</td>" +
					'<td class="text-nowrap text-end">' +
					'<button type="button" class="btn btn-link btn-sm p-0 me-2 usis-ca-c-edit" data-id="' +
					esc(row.id) +
					'">Edit</button>' +
					delBtn +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
		tbody.querySelectorAll(".usis-ca-c-edit").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var id = btn.getAttribute("data-id");
				var found = rows.filter(function (r) {
					return r.id === id;
				})[0];
				if (!found) return;
				fillContractForm(found);
				var modal = contractModal();
				if (modal) modal.show();
			});
		});
		tbody.querySelectorAll(".usis-ca-c-del").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var id = btn.getAttribute("data-id");
				if (!id || !lastProjectId) return;
				if (!window.confirm("Delete this contract from the project?")) return;
				fetch(
					apiBase() +
						"/api/v1/projects/" +
						encodeURIComponent(lastProjectId) +
						"/contracts/" +
						encodeURIComponent(id),
					{
						method: "DELETE",
						credentials: "include",
						headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
					}
				)
					.then(function (res) {
						if (res.status === 204) return { ok: true, body: {} };
						return res.json().then(function (j) {
							return { ok: res.ok, body: j };
						});
					})
					.then(function (res) {
						if (!res.ok) {
							window.alert((res.body && res.body.error) || "Could not delete contract.");
							return;
						}
						loadProjectContracts();
					})
					.catch(function () {
						window.alert("Network error deleting contract.");
					});
			});
		});
	}

	function loadProjectContracts() {
		var tbody = document.getElementById("usis-ca-contract-tbody");
		if (!lastProjectId || !tbody) return;
		fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(lastProjectId) + "/contracts", {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					tbody.innerHTML =
						'<tr><td colspan="6" class="text-danger">' +
						esc((res.body && res.body.error) || "Could not load contracts.") +
						"</td></tr>";
					return;
				}
				renderProjectContracts(res.body);
			})
			.catch(function () {
				tbody.innerHTML = '<tr><td colspan="6" class="text-danger">Network error loading contracts.</td></tr>';
			});
	}

	function saveProjectContract() {
		if (!lastProjectId) return;
		var payload = contractFormPayload();
		if (!payload.title) {
			setContractErr("Title is required.");
			return;
		}
		var id = document.getElementById("usis-ca-c-id").value.trim();
		var url =
			apiBase() +
			"/api/v1/projects/" +
			encodeURIComponent(lastProjectId) +
			"/contracts" +
			(id ? "/" + encodeURIComponent(id) : "");
		setContractErr("");
		fetch(url, {
			method: id ? "PATCH" : "POST",
			credentials: "include",
			headers: Object.assign(
				{ Accept: "application/json", "Content-Type": "application/json" },
				actorHeaders()
			),
			body: JSON.stringify(payload),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					setContractErr((res.body && res.body.error) || "Save failed.");
					return;
				}
				var modal = contractModal();
				if (modal) modal.hide();
				loadProjectContracts();
				if (res.body.item && res.body.item.is_primary) {
					reloadProjectAndContractAdmin();
				}
			})
			.catch(function () {
				setContractErr("Network error saving contract.");
			});
	}

	function actorHeaders() {
		return window.USIS_API.actorHeaders();
	}

	function parseMoneyInput(raw) {
		if (raw == null || String(raw).trim() === "") return 0;
		var n = Number(String(raw).replace(/[$,\s]/g, ""));
		return isNaN(n) ? 0 : n;
	}

	function splitCsvLine(line) {
		var out = [];
		var cur = "";
		var inQ = false;
		for (var i = 0; i < line.length; i++) {
			var c = line[i];
			if (c === '"') {
				inQ = !inQ;
				continue;
			}
			if (!inQ && c === ",") {
				out.push(cur.trim());
				cur = "";
				continue;
			}
			cur += c;
		}
		out.push(cur.trim());
		return out;
	}

	function csvRowLooksLikeHeader(cells) {
		if (!cells || cells.length < 2) return false;
		var joined = cells.join(" ").toLowerCase();
		if (joined.indexOf("description") >= 0 && (joined.indexOf("phase") >= 0 || joined.indexOf("cost") >= 0 || joined.indexOf("div") >= 0)) {
			return true;
		}
		if (joined.indexOf("scheduled") >= 0 && joined.indexOf("value") >= 0) return true;
		var last = cells[cells.length - 1] || "";
		if (!/\d/.test(String(last)) && (joined.indexOf("amount") >= 0 || joined.indexOf("value") >= 0)) return true;
		return false;
	}

	function parsePrimeSovCsvText(text) {
		var rawLines = String(text || "")
			.split(/\r?\n/)
			.map(function (ln) {
				return ln.trim();
			})
			.filter(Boolean);
		if (!rawLines.length) {
			return { error: "No rows found in file." };
		}
		var rows = rawLines.map(splitCsvLine);
		var start = 0;
		if (rows.length && csvRowLooksLikeHeader(rows[0])) {
			start = 1;
		}
		var out = [];
		for (var r = start; r < rows.length; r++) {
			var cells = rows[r];
			if (!cells.length) continue;
			if (cells.length === 1) continue;
			var phase = "";
			var desc = "";
			var valCell = "0";
			if (cells.length === 2) {
				desc = (cells[0] || "").trim();
				valCell = cells[1] || "0";
			} else {
				phase = (cells[0] || "").trim();
				valCell = cells[cells.length - 1] || "0";
				desc = cells
					.slice(1, cells.length - 1)
					.join(", ")
					.trim();
			}
			var amt = parseMoneyInput(valCell);
			if (!desc && !phase && !amt) continue;
			if (!desc) desc = phase ? "Line " + (out.length + 1) : "Imported line " + (out.length + 1);
			out.push({
				phase_code: phase || null,
				description: desc,
				scheduled_value: String(amt.toFixed(2)),
			});
		}
		if (!out.length) {
			return {
				error:
					"No data rows parsed. Expected columns: Phase, Description…, Scheduled value (last column is the amount).",
			};
		}
		return { lines: out };
	}

	function onPrimeSovImportFileSelected(ev) {
		var inp = ev.target;
		var f = inp && inp.files && inp.files[0];
		if (inp) inp.value = "";
		if (!f) return;
		var reader = new FileReader();
		reader.onload = function () {
			var parsed = parsePrimeSovCsvText(String(reader.result || ""));
			if (parsed.error) {
				setPrimeSovAlert(parsed.error);
				return;
			}
			setPrimeSovAlert("");
			renderPrimeSovRows(parsed.lines, PRIME_SOV_MODAL_IDS);
			var n = parsed.lines.length;
			if (window.USISNotify && window.USISNotify.success) {
				window.USISNotify.success("Imported " + n + " SOV line" + (n === 1 ? "" : "s") + " from file. Save SOV to persist.");
			}
		};
		reader.onerror = function () {
			setPrimeSovAlert("Could not read the selected file.");
		};
		reader.readAsText(f);
	}

	var PRIME_SOV_MODAL_IDS = {
		tbody: "usis-ca-sov-modal-tbody",
		alert: "usis-ca-sov-modal-alert",
		total: "usis-ca-sov-modal-total",
		vs: "usis-ca-sov-modal-vs",
	};

	function setPrimeSovAlert(msg, alertId) {
		var el = document.getElementById(alertId || PRIME_SOV_MODAL_IDS.alert);
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function hidePrimeSovModal() {
		var el = document.getElementById("usis-modal-prime-sov");
		if (!el || !window.bootstrap || !window.bootstrap.Modal) return;
		var inst = window.bootstrap.Modal.getInstance(el);
		if (inst) inst.hide();
	}

	function renderPrimeSovRows(lines, ids) {
		ids = ids || PRIME_SOV_MODAL_IDS;
		var tbody = document.getElementById(ids.tbody);
		if (!tbody) return;
		var rows = lines && lines.length ? lines : [];
		if (!rows.length) {
			tbody.innerHTML =
				"<tr class=\"text-muted\"><td colspan=\"4\" class=\"text-center py-2\">No SOV lines yet. Use <strong>+ Add row</strong> below.</td></tr>";
		} else {
			tbody.innerHTML = rows
				.map(function (li, idx) {
					var phase = esc(li.phase_code || "");
					var desc = esc(li.description || "");
					var sv = li.scheduled_value != null ? esc(String(li.scheduled_value)) : "0.00";
					return (
						"<tr data-sort=\"" +
						idx +
						"\">" +
						"<td><input type=\"text\" class=\"form-control form-control-sm\" data-field=\"phase_code\" value=\"" +
						phase +
						"\" /></td>" +
						"<td><input type=\"text\" class=\"form-control form-control-sm\" data-field=\"description\" value=\"" +
						desc +
						"\" /></td>" +
						"<td class=\"text-end\"><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"scheduled_value\" value=\"" +
						sv +
						"\" /></td>" +
						"<td class=\"text-center\"><button type=\"button\" class=\"btn btn-link btn-sm text-danger p-0\" data-action=\"sov-remove\" title=\"Remove row\">×</button></td>" +
						"</tr>"
					);
				})
				.join("");
		}
		updatePrimeSovTotalsFromInputs(ids);
	}

	function updatePrimeSovTotalsFromInputs(ids) {
		ids = ids || PRIME_SOV_MODAL_IDS;
		var tbody = document.getElementById(ids.tbody);
		var totalEl = document.getElementById(ids.total);
		var vsEl = document.getElementById(ids.vs);
		if (!tbody || !totalEl || !vsEl) return;
		var sum = 0;
		tbody.querySelectorAll("tr").forEach(function (tr) {
			var inp = tr.querySelector('input[data-field="scheduled_value"]');
			if (inp) sum += parseMoneyInput(inp.value);
		});
		totalEl.textContent = moneyPlain(sum);
		if (lastPrimeContractValueNum != null && !isNaN(lastPrimeContractValueNum)) {
			var diff = sum - lastPrimeContractValueNum;
			if (Math.abs(diff) < 0.005) {
				vsEl.textContent = "Matches contract value.";
				vsEl.className = "text-success ms-2";
			} else {
				vsEl.textContent =
					(diff > 0 ? "Over contract by " : "Under contract by ") + moneyPlain(Math.abs(diff)) + ".";
				vsEl.className = "text-warning ms-2";
			}
		} else {
			vsEl.textContent = "";
			vsEl.className = "text-muted ms-2";
		}
	}

	function collectPrimeSovLinesForPut(ids) {
		ids = ids || PRIME_SOV_MODAL_IDS;
		var tbody = document.getElementById(ids.tbody);
		if (!tbody) return [];
		var out = [];
		var idx = 0;
		tbody.querySelectorAll("tr").forEach(function (tr) {
			if (tr.querySelector("td.text-muted")) return;
			var p = tr.querySelector('input[data-field="phase_code"]');
			var d = tr.querySelector('input[data-field="description"]');
			var s = tr.querySelector('input[data-field="scheduled_value"]');
			if (!d || !s) return;
			out.push({
				sort_order: idx,
				phase_code: p && p.value ? p.value.trim() : "",
				description: d.value.trim() || "Line " + (idx + 1),
				scheduled_value: String(parseMoneyInput(s.value).toFixed(2)),
			});
			idx++;
		});
		return out;
	}

	function refreshPrimeSovSummary(projectId) {
		var sumEl = document.getElementById("usis-ca-sov-summary");
		if (!sumEl || !projectId) return;
		sumEl.textContent = "Loading SOV summary…";
		sumEl.className = "small mb-0 text-muted";
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/prime-contract/sov";
		var opts = {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		};
		fetch(url, opts)
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var n = (data.lines || []).length;
				var bits = [
					n + " SOV line" + (n === 1 ? "" : "s"),
					"total " + moneyPlain(data.total_scheduled_value != null ? data.total_scheduled_value : "0"),
				];
				if (data.sov_matches_contract_value === true) {
					bits.push("matches contract value.");
				} else if (data.sov_matches_contract_value === false) {
					bits.push("does not match contract value.");
				}
				sumEl.textContent = bits.join(" — ");
				sumEl.className = "small mb-0 text-body";
			})
			.catch(function () {
				sumEl.textContent = "Could not load SOV summary.";
				sumEl.className = "small mb-0 text-danger";
			});
	}

	function loadPrimeContractSovModal(projectId) {
		if (!projectId) return;
		var tbody = document.getElementById(PRIME_SOV_MODAL_IDS.tbody);
		if (!tbody) return;
		setPrimeSovAlert("");
		tbody.innerHTML =
			"<tr><td colspan=\"4\" class=\"text-muted text-center py-2\">Loading SOV…</td></tr>";
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/prime-contract/sov";
		var opts = {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		};
		fetch(url, opts)
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var lines = data.lines || [];
				renderPrimeSovRows(lines, PRIME_SOV_MODAL_IDS);
				var totalEl = document.getElementById(PRIME_SOV_MODAL_IDS.total);
				var vsEl = document.getElementById(PRIME_SOV_MODAL_IDS.vs);
				if (totalEl && data.total_scheduled_value != null) {
					totalEl.textContent = moneyPlain(data.total_scheduled_value);
				}
				if (vsEl) {
					if (data.sov_matches_contract_value === true) {
						vsEl.textContent = "Matches contract value.";
						vsEl.className = "text-success ms-2";
					} else if (data.sov_matches_contract_value === false) {
						vsEl.textContent = "SOV total differs from contract value.";
						vsEl.className = "text-warning ms-2";
					} else {
						vsEl.textContent = "";
						vsEl.className = "text-muted ms-2";
					}
				}
			})
			.catch(function (err) {
				renderPrimeSovRows([], PRIME_SOV_MODAL_IDS);
				setPrimeSovAlert("Could not load prime SOV: " + (err.message || String(err)));
			});
	}

	function savePrimeContractSov() {
		var pid = lastProjectId || projectIdFromQuery();
		if (!pid) return;
		setPrimeSovAlert("");
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(pid) + "/prime-contract/sov";
		var body = { lines: collectPrimeSovLinesForPut(PRIME_SOV_MODAL_IDS) };
		var opts = {
			method: "PUT",
			credentials: "include",
			headers: Object.assign(
				{ "Content-Type": "application/json", Accept: "application/json" },
				actorHeaders()
			),
			body: JSON.stringify(body),
		};
		fetch(url, opts)
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var lines = data.lines || [];
				renderPrimeSovRows(lines, PRIME_SOV_MODAL_IDS);
				refreshPrimeSovSummary(pid);
				hidePrimeSovModal();
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success("Prime contract SOV saved.");
				}
			})
			.catch(function (err) {
				setPrimeSovAlert("Save failed: " + (err.message || String(err)));
			});
	}

	function wirePrimeSovModalOnce() {
		if (wirePrimeSovModalOnce._done) return;
		wirePrimeSovModalOnce._done = true;
		var modal = document.getElementById("usis-modal-prime-sov");
		if (modal) {
			modal.addEventListener("shown.bs.modal", function () {
				var p = lastProjectId || projectIdFromQuery();
				if (p) loadPrimeContractSovModal(p);
			});
		}
		var tbody = document.getElementById(PRIME_SOV_MODAL_IDS.tbody);
		if (tbody) {
			tbody.addEventListener("input", function (e) {
				if (e.target && e.target.getAttribute && e.target.getAttribute("data-field") === "scheduled_value") {
					updatePrimeSovTotalsFromInputs(PRIME_SOV_MODAL_IDS);
				}
			});
			tbody.addEventListener("click", function (e) {
				var btn = e.target && e.target.closest ? e.target.closest("[data-action=\"sov-remove\"]") : null;
				if (!btn) return;
				var tr = btn.closest("tr");
				if (tr && tr.parentNode) {
					tr.parentNode.removeChild(tr);
					updatePrimeSovTotalsFromInputs(PRIME_SOV_MODAL_IDS);
				}
			});
		}
		var addBtn = document.getElementById("usis-ca-sov-modal-add-row");
		if (addBtn) {
			addBtn.addEventListener("click", function () {
				var tb = document.getElementById(PRIME_SOV_MODAL_IDS.tbody);
				if (!tb) return;
				var placeholder = tb.querySelector("td.text-muted");
				if (placeholder && placeholder.closest("tr")) {
					tb.removeChild(placeholder.closest("tr"));
				}
				var tr = document.createElement("tr");
				tr.innerHTML =
					"<td><input type=\"text\" class=\"form-control form-control-sm\" data-field=\"phase_code\" value=\"\" /></td>" +
					"<td><input type=\"text\" class=\"form-control form-control-sm\" data-field=\"description\" value=\"\" /></td>" +
					"<td class=\"text-end\"><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"scheduled_value\" value=\"0.00\" /></td>" +
					"<td class=\"text-center\"><button type=\"button\" class=\"btn btn-link btn-sm text-danger p-0\" data-action=\"sov-remove\" title=\"Remove row\">×</button></td>";
				tb.appendChild(tr);
				updatePrimeSovTotalsFromInputs(PRIME_SOV_MODAL_IDS);
			});
		}
		var rel = document.getElementById("usis-ca-sov-modal-reload");
		if (rel) {
			rel.addEventListener("click", function () {
				var p = lastProjectId || projectIdFromQuery();
				if (p) loadPrimeContractSovModal(p);
			});
		}
		var imp = document.getElementById("usis-ca-sov-modal-import");
		var impFile = document.getElementById("usis-ca-sov-modal-import-file");
		if (imp && impFile) {
			imp.addEventListener("click", function () {
				impFile.click();
			});
			impFile.addEventListener("change", onPrimeSovImportFileSelected);
		}
		var sav = document.getElementById("usis-ca-sov-modal-save");
		if (sav) {
			sav.addEventListener("click", savePrimeContractSov);
		}
	}

	function loadContractAdminCommitmentSummary(projectId) {
		var sumEl = document.getElementById("usis-ca-proc-summary");
		if (!sumEl || !projectId) return;
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments";
		fetch(url, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var items = data.items || [];
				var nPo = 0;
				var nSub = 0;
				var nAppr = 0;
				var approvedCommitted = 0;
				var nRules = 0;
				var nDraft = 0;
				var nPending = 0;
				var nNotApproved = 0;
				items.forEach(function (row) {
					if (row.commitment_kind === "purchase_order") nPo++;
					if (row.commitment_kind === "subcontract") nSub++;
					var st = String(row.status || "").toLowerCase();
					if (st === "approved") {
						nAppr++;
						approvedCommitted += parseCommitmentAmount(row.total_amount);
					}
					if (row.workflow_rule_active === true) nRules++;
					if (st === "draft") nDraft++;
					else if (st === "pending_submission" || st === "pending") nPending++;
					else if (st === "not_approved") nNotApproved++;
				});
				sumEl.innerHTML =
					"<li><strong>Approved committed value:</strong> " +
					moneyPlain(approvedCommitted) +
					"</li>" +
					"<li><strong>Workflow rules active:</strong> " +
					nRules +
					"</li>" +
					"<li>POs: " +
					nPo +
					"</li><li>Subcontracts: " +
					nSub +
					"</li>" +
					"<li class=\"text-muted small mt-1\">Status — draft: " +
					nDraft +
					" · pending: " +
					nPending +
					" · not approved: " +
					nNotApproved +
					" · approved: " +
					nAppr +
					"</li>" +
					"<li>Total rows: " +
					items.length +
					"</li>";
			})
			.catch(function (err) {
				sumEl.innerHTML =
					'<li class="text-danger">Could not load commitments: ' +
					esc(err.message || String(err)) +
					"</li>";
			});
	}

	function showJobInfoTab() {
		var tabBtn = document.getElementById("proj-tab-job");
		if (tabBtn && window.bootstrap && window.bootstrap.Tab) {
			window.bootstrap.Tab.getOrCreateInstance(tabBtn).show();
		}
	}

	function reloadProjectAndContractAdmin() {
		var pid = lastProjectId || projectIdFromQuery();
		if (!pid) return;
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(pid);
		fetch(url, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var item = data.item;
				if (!item) throw new Error("Missing item in response");
				lastProjectItem = item;
				render(item);
				fillContractAdminFromProject(item);
				loadContractAdminCommitmentSummary(pid);
				refreshPrimeSovSummary(pid);
				wireProcurementTabProjectScope(item, pid);
			})
			.catch(function (err) {
				if (typeof console !== "undefined" && console.warn) {
					console.warn("Contract admin reload failed:", err.message || err);
				}
			});
	}

	function wireContractAdminToolsOnce() {
		if (wireContractAdminToolsOnce._done) return;
		wireContractAdminToolsOnce._done = true;
		wirePrimeSovModalOnce();
		var jobBtn = document.getElementById("usis-ca-jump-job");
		if (jobBtn) {
			jobBtn.addEventListener("click", showJobInfoTab);
		}
		var jobComplianceBtn = document.getElementById("usis-ca-jump-job-compliance");
		if (jobComplianceBtn) {
			jobComplianceBtn.addEventListener("click", showJobInfoTab);
		}
		var reloadBtn = document.getElementById("usis-ca-reload-project");
		if (reloadBtn) {
			reloadBtn.addEventListener("click", reloadProjectAndContractAdmin);
		}
		var addContractBtn = document.getElementById("usis-ca-contract-add");
		if (addContractBtn) {
			addContractBtn.addEventListener("click", function () {
				fillContractForm({
					title: lastContractItems.length ? "" : "Prime contract",
					is_primary: lastContractItems.length === 0,
				});
				var modal = contractModal();
				if (modal) modal.show();
			});
		}
		var saveContractBtn = document.getElementById("usis-ca-c-save");
		if (saveContractBtn) {
			saveContractBtn.addEventListener("click", saveProjectContract);
		}
		var copySageBtn = document.getElementById("usis-ca-copy-sage");
		if (copySageBtn) {
			copySageBtn.addEventListener("click", function () {
				if (!lastSageProjectIdStr) return;
				copyTextToClipboard(lastSageProjectIdStr).catch(function () {});
			});
		}
		var procBtn = document.getElementById("usis-ca-open-procurement");
		if (procBtn) {
			procBtn.addEventListener("click", function () {
				var tabBtn = document.getElementById("proj-tab-procurement");
				if (tabBtn && window.bootstrap && window.bootstrap.Tab) {
					window.bootstrap.Tab.getOrCreateInstance(tabBtn).show();
				}
			});
		}
		var refBtn = document.getElementById("usis-ca-proc-refresh");
		if (refBtn) {
			refBtn.addEventListener("click", function () {
				if (lastProjectId) loadContractAdminCommitmentSummary(lastProjectId);
			});
		}
	}

	function firstNumber() {
		for (var i = 0; i < arguments.length; i++) {
			var n = Number(arguments[i]);
			if (!isNaN(n) && isFinite(n)) return n;
		}
		return null;
	}

	function formatIsoDateTime(iso) {
		if (!iso) return null;
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return String(iso);
			try {
				return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
			} catch (e2) {
				return d.toLocaleString();
			}
		} catch (e) {
			return String(iso);
		}
	}

	function formatJobDate(iso) {
		if (!iso) return null;
		var raw = String(iso).trim();
		if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
			try {
				var d = new Date(raw + "T12:00:00");
				if (!isNaN(d.getTime())) return d.toLocaleDateString();
			} catch (e) { /* fall through */ }
			return raw;
		}
		return formatIsoDateTime(iso);
	}

	function formatMoneyCur(n, currency) {
		if (n == null || n === "") return null;
		var cur = (currency || "USD").toString().trim() || "USD";
		try {
			return new Intl.NumberFormat(undefined, { style: "currency", currency: cur }).format(Number(n));
		} catch (e) {
			return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + cur;
		}
	}

	function formatPercent(p) {
		if (p == null || p === "") return null;
		var x = Number(p);
		if (isNaN(x)) return null;
		if (x >= 0 && x <= 1) x = x * 100;
		return x.toFixed(1).replace(/\.0$/, "") + "%";
	}

	function formatLocation(loc) {
		if (!loc || typeof loc !== "object") return null;
		var keys = [
			"formatted",
			"formattedAddress",
			"complete",
			"address",
			"address1",
			"streetName",
			"street",
			"line1",
			"city",
			"state",
			"region",
			"postalCode",
			"zip",
			"country",
		];
		var parts = [];
		var seen = {};
		for (var i = 0; i < keys.length; i++) {
			var v = loc[keys[i]];
			if (v == null || String(v).trim() === "") continue;
			var text = String(v).trim();
			if (seen[text.toLowerCase()]) continue;
			seen[text.toLowerCase()] = 1;
			parts.push(text);
		}
		return parts.length ? parts.join(", ") : null;
	}

	function projectLocation(item) {
		if (!item) return null;
		var has =
			item.address_line1 ||
			item.address_line2 ||
			item.city ||
			item.state ||
			item.postal_code ||
			item.country;
		if (!has) return null;
		return {
			address: [item.address_line1, item.address_line2].filter(Boolean).join(", "),
			city: item.city,
			state: item.state,
			postalCode: item.postal_code,
			country: item.country && item.country !== "US" ? item.country : null,
		};
	}

	function locationQuery(item) {
		var lat = firstNumber(item && item.latitude, item && item.lat);
		var lng = firstNumber(item && item.longitude, item && item.lng, item && item.lon);
		if (lat != null && lng != null) return lat + "," + lng;
		var loc = item && item.location;
		if (loc && typeof loc === "object") {
			var coords = loc.coords && typeof loc.coords === "object" ? loc.coords : loc;
			lat = firstNumber(coords.lat, coords.latitude, loc.lat, loc.latitude);
			lng = firstNumber(coords.lng, coords.lon, coords.longitude, loc.lng, loc.lon, loc.longitude);
			if (lat != null && lng != null) return lat + "," + lng;
		}
		var formatted = formatLocation(loc) || formatLocation(projectLocation(item));
		if (formatted) return formatted;
		var bits = [item && item.city, item && item.state].filter(Boolean);
		return bits.length ? bits.join(", ") : "";
	}

	function dueClass(iso) {
		if (!iso) return "text-muted";
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return "text-muted";
			if (d.getTime() - Date.now() <= 7 * 86400000) return "text-danger";
		} catch (e) { /* keep muted */ }
		return "";
	}

	function yn(v) {
		if (v === true) return "Yes";
		if (v === false) return "No";
		return "—";
	}

	function humanizeToken(s) {
		var raw = String(s || "").trim();
		if (!raw) return "";
		return raw.replace(/_/g, " ").replace(/\b\w/g, function (ch) {
			return ch.toUpperCase();
		});
	}

	function appendFieldRow(tbody, label, htmlValue) {
		if (!tbody) return;
		var row = document.createElement("tr");
		row.innerHTML =
			'<th class="text-muted fw-normal ps-3 py-2" scope="row" style="width:42%">' +
			esc(label) +
			'</th><td class="py-2 pe-3">' +
			htmlValue +
			"</td>";
		tbody.appendChild(row);
	}

	function appendDateRow(tbody, label, iso) {
		appendFieldRow(tbody, label, iso ? fmtDash(formatJobDate(iso)) : '<span class="text-muted">—</span>');
	}

	function renderMembers(container, members) {
		if (!container) return;
		container.innerHTML = "";
		if (!members) {
			container.innerHTML = '<p class="text-muted mb-0 small">No team list in import.</p>';
			return;
		}
		if (Array.isArray(members) && members.length) {
			var ul = document.createElement("ul");
			ul.className = "list-unstyled mb-0";
			members.forEach(function (m) {
				if (!m || typeof m !== "object") return;
				var li = document.createElement("li");
				li.className = "mb-2 pb-2 border-bottom";
				var name =
					m.name ||
					[m.firstName, m.lastName].filter(Boolean).join(" ") ||
					m.displayName ||
					m.email ||
					"Member";
				var role = m.role || m.title || m.tradeName || "";
				var co = (m.company && m.company.name) || m.companyName || "";
				li.innerHTML =
					'<div class="fw-medium">' +
					esc(name) +
					"</div>" +
					(role ? '<div class="text-muted">' + esc(role) + "</div>" : "") +
					(co ? '<div class="text-muted">' + esc(co) + "</div>" : "");
				ul.appendChild(li);
			});
			container.appendChild(ul);
			return;
		}
		container.innerHTML = '<p class="text-muted mb-0 small">No team list in import.</p>';
	}

	function pick(project, lead, key) {
		if (project && project[key] != null && project[key] !== "") return project[key];
		if (lead && lead[key] != null && lead[key] !== "") return lead[key];
		return project ? project[key] : null;
	}

	function fetchLinkedLead(item) {
		var lid = item && item.primary_lead_detail_id;
		if (!lid) return Promise.resolve(null);
		return fetch(apiBase() + "/api/v1/lead-estimates/" + encodeURIComponent(lid), {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				if (!res.ok) return null;
				return res.json();
			})
			.then(function (data) {
				return (data && data.item) || null;
			})
			.catch(function () {
				return null;
			});
	}

	function setJobPaneLoading(show) {
		var pane = document.getElementById("proj-pane-job");
		if (!pane) return;
		var n = pane.querySelector("[data-usis-loading]");
		if (n) n.classList.toggle("d-none", !show);
	}

	function setJobPaneError(msg) {
		var pane = document.getElementById("proj-pane-job");
		if (!pane) return;
		var n = pane.querySelector("[data-usis-error]");
		if (!n) return;
		if (msg) {
			n.textContent = msg;
			n.classList.remove("d-none");
		} else {
			n.textContent = "";
			n.classList.add("d-none");
		}
	}

	function loadInvoiceMethods(cb) {
		fetch(apiBase() + "/api/v1/invoice-delivery-methods", {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					if (cb) cb(res.body && res.body.error ? res.body.error : "Could not load invoice methods.");
					return;
				}
				invoiceMethods = res.body.items || [];
				if (cb) cb(null);
			})
			.catch(function () {
				if (cb) cb("Network error loading invoice methods.");
			});
	}

	function fillInvoiceMethodSelect(selectedCode) {
		var sel = document.getElementById("usis-proj-edit-invoice-method");
		if (!sel) return;
		var html = '<option value="">— Select —</option>';
		invoiceMethods.forEach(function (m) {
			var code = m.code || "";
			var label = m.label || code;
			var selAttr = code === selectedCode ? " selected" : "";
			html += '<option value="' + esc(code) + '"' + selAttr + ">" + esc(label) + "</option>";
		});
		html += '<option value="' + INVOICE_ADD_NEW + '">+ Add new method…</option>';
		sel.innerHTML = html;
	}

	function toggleInvoiceEmailField() {
		var sel = document.getElementById("usis-proj-edit-invoice-method");
		var wrap = document.getElementById("usis-proj-edit-email-wrap");
		if (!sel || !wrap) return;
		var show = sel.value === "email";
		wrap.classList.toggle("d-none", !show);
	}

	function fillShipOfficeSelect(selectedId) {
		var sel = document.getElementById("usis-proj-edit-ship-office");
		if (!sel) return;
		var html = '<option value="">— Select office —</option>';
		lastOffices.forEach(function (o) {
			var id = o.id || "";
			var label = o.label || o.name || "Office";
			if (o.address) label += " — " + o.address;
			html +=
				'<option value="' +
				esc(id) +
				'"' +
				(id === selectedId ? " selected" : "") +
				">" +
				esc(label) +
				"</option>";
		});
		sel.innerHTML = html;
		if (!lastOffices.length) {
			sel.innerHTML = '<option value="">No offices yet — add them in Company settings</option>';
		}
	}

	function toggleShipOfficeField() {
		var kind = document.getElementById("usis-proj-edit-ship-kind");
		var wrap = document.getElementById("usis-proj-edit-ship-office-wrap");
		if (!wrap) return;
		wrap.classList.toggle("d-none", !kind || kind.value !== "office");
	}

	function loadOffices(cb) {
		fetch(apiBase() + "/api/v1/office-locations", {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				lastOffices = res.ok && res.body && res.body.items ? res.body.items : [];
				if (cb) cb(null);
			})
			.catch(function () {
				lastOffices = [];
				if (cb) cb("Could not load offices.");
			});
	}

	function setEditErr(msg) {
		var el = document.getElementById("usis-proj-edit-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function openEditModal() {
		if (!lastProjectItem) return;
		var item = lastProjectItem;
		setEditErr("");
		document.getElementById("usis-proj-edit-name").value = item.name || "";
		document.getElementById("usis-proj-edit-number").value = item.number || "";
		document.getElementById("usis-proj-edit-status").value = item.status || "active";
		document.getElementById("usis-proj-edit-type").value = item.project_type || "commercial";
		document.getElementById("usis-proj-edit-sage").value = item.sage_project_id || "";
		document.getElementById("usis-proj-edit-textura").value = item.textura_project_id || "";
		document.getElementById("usis-proj-edit-addr1").value = item.address_line1 || "";
		var addr2 = document.getElementById("usis-proj-edit-addr2");
		if (addr2) addr2.value = item.address_line2 || "";
		document.getElementById("usis-proj-edit-city").value = item.city || "";
		document.getElementById("usis-proj-edit-state").value = item.state || "";
		document.getElementById("usis-proj-edit-zip").value = item.postal_code || "";
		document.getElementById("usis-proj-edit-contract-value").value =
			item.contract_value != null ? String(item.contract_value) : "";
		document.getElementById("usis-proj-edit-contract-date").value = isoToInputDate(item.contract_date);
		document.getElementById("usis-proj-edit-start").value = isoToInputDate(item.start_date);
		var install = document.getElementById("usis-proj-edit-install");
		if (install) install.value = isoToInputDate(item.expected_install_date);
		var shipKind = document.getElementById("usis-proj-edit-ship-kind");
		if (shipKind) shipKind.value = item.ship_to_kind === "office" ? "office" : "jobsite";
		loadOffices(function () {
			fillShipOfficeSelect(item.ship_to_office_id || "");
			toggleShipOfficeField();
		});
		document.getElementById("usis-proj-edit-substantial").value = isoToInputDate(item.substantial_completion_date);
		document.getElementById("usis-proj-edit-closeout").value = isoToInputDate(item.closeout_date);
		document.getElementById("usis-proj-edit-retention").value =
			item.retention_percentage != null ? String(item.retention_percentage) : "";
		document.getElementById("usis-proj-edit-invoice-due").value = isoToInputDate(item.invoice_due_date);
		document.getElementById("usis-proj-edit-invoice-emails").value = item.invoice_recipient_emails || "";
		document.getElementById("usis-proj-edit-description").value = item.description || "";
		document.getElementById("usis-proj-edit-notes").value = item.notes || "";
		document.getElementById("usis-proj-edit-prevailing").checked = !!item.prevailing_wage;
		document.getElementById("usis-proj-edit-dbe").checked = !!item.dbe_required;
		loadInvoiceMethods(function (err) {
			if (err) {
				setEditErr(err);
			}
			fillInvoiceMethodSelect(item.invoice_method || "");
			toggleInvoiceEmailField();
			var modalEl = document.getElementById("usis-proj-edit-modal");
			if (modalEl && window.bootstrap) {
				window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
			}
		});
	}

	function onInvoiceMethodChange() {
		var sel = document.getElementById("usis-proj-edit-invoice-method");
		if (!sel || sel.value !== INVOICE_ADD_NEW) {
			toggleInvoiceEmailField();
			return;
		}
		var label = window.prompt("Name for the new invoice delivery method:");
		if (!label || !String(label).trim()) {
			sel.value = lastProjectItem && lastProjectItem.invoice_method ? lastProjectItem.invoice_method : "";
			toggleInvoiceEmailField();
			return;
		}
		fetch(apiBase() + "/api/v1/invoice-delivery-methods", {
			method: "POST",
			credentials: "include",
			headers: Object.assign(
				{ Accept: "application/json", "Content-Type": "application/json" },
				actorHeaders()
			),
			body: JSON.stringify({ label: String(label).trim() }),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					setEditErr((res.body && res.body.error) || "Could not save new method.");
					sel.value = "";
					toggleInvoiceEmailField();
					return;
				}
				invoiceMethods.push(res.body.item);
				fillInvoiceMethodSelect(res.body.item.code);
				toggleInvoiceEmailField();
				setEditErr("");
			})
			.catch(function () {
				setEditErr("Network error saving new method.");
				sel.value = "";
				toggleInvoiceEmailField();
			});
	}

	function saveProjectEdit() {
		if (!lastProjectId) return;
		setEditErr("");
		var method = document.getElementById("usis-proj-edit-invoice-method").value;
		var payload = {
			name: document.getElementById("usis-proj-edit-name").value.trim(),
			number: document.getElementById("usis-proj-edit-number").value.trim() || null,
			status: document.getElementById("usis-proj-edit-status").value,
			project_type: document.getElementById("usis-proj-edit-type").value,
			sage_project_id: document.getElementById("usis-proj-edit-sage").value.trim() || null,
			textura_project_id: document.getElementById("usis-proj-edit-textura").value.trim() || null,
			address_line1: document.getElementById("usis-proj-edit-addr1").value.trim() || null,
			address_line2: document.getElementById("usis-proj-edit-addr2")
				? document.getElementById("usis-proj-edit-addr2").value.trim() || null
				: null,
			city: document.getElementById("usis-proj-edit-city").value.trim() || null,
			state: document.getElementById("usis-proj-edit-state").value.trim() || null,
			postal_code: document.getElementById("usis-proj-edit-zip").value.trim() || null,
			contract_value: document.getElementById("usis-proj-edit-contract-value").value.trim() || null,
			contract_date: document.getElementById("usis-proj-edit-contract-date").value || null,
			start_date: document.getElementById("usis-proj-edit-start").value || null,
			expected_install_date: (document.getElementById("usis-proj-edit-install") || {}).value || null,
			ship_to_kind: (document.getElementById("usis-proj-edit-ship-kind") || {}).value || "jobsite",
			ship_to_office_id:
				((document.getElementById("usis-proj-edit-ship-kind") || {}).value === "office"
					? (document.getElementById("usis-proj-edit-ship-office") || {}).value
					: "") || null,
			substantial_completion_date: document.getElementById("usis-proj-edit-substantial").value || null,
			closeout_date: document.getElementById("usis-proj-edit-closeout").value || null,
			retention_percentage: document.getElementById("usis-proj-edit-retention").value.trim() || null,
			prevailing_wage: document.getElementById("usis-proj-edit-prevailing").checked,
			dbe_required: document.getElementById("usis-proj-edit-dbe").checked,
			description: document.getElementById("usis-proj-edit-description").value.trim() || null,
			notes: document.getElementById("usis-proj-edit-notes").value.trim() || null,
			invoice_method: method || null,
			invoice_due_date: document.getElementById("usis-proj-edit-invoice-due").value || null,
			invoice_recipient_emails:
				method === "email"
					? document.getElementById("usis-proj-edit-invoice-emails").value.trim()
					: null,
		};
		if (!payload.name) {
			setEditErr("Project name is required.");
			return;
		}
		fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(lastProjectId), {
			method: "PATCH",
			credentials: "include",
			headers: Object.assign(
				{ Accept: "application/json", "Content-Type": "application/json" },
				actorHeaders()
			),
			body: JSON.stringify(payload),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					setEditErr((res.body && res.body.error) || "Save failed.");
					return;
				}
				var item = res.body.item;
				lastProjectItem = item;
				render(item);
				fillContractAdminFromProject(item);
				wireProcurementTabProjectScope(item, lastProjectId);
				var modalEl = document.getElementById("usis-proj-edit-modal");
				if (modalEl && window.bootstrap) {
					var inst = window.bootstrap.Modal.getInstance(modalEl);
					if (inst) inst.hide();
				}
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success("Project information saved.");
				}
			})
			.catch(function () {
				setEditErr("Network error saving project.");
			});
	}

	function wireProjectEditOnce() {
		if (wireProjectEditOnce._done) return;
		wireProjectEditOnce._done = true;
		var editBtn = document.getElementById("usis-proj-edit-btn");
		if (editBtn) editBtn.addEventListener("click", openEditModal);
		var saveBtn = document.getElementById("usis-proj-edit-save");
		if (saveBtn) saveBtn.addEventListener("click", saveProjectEdit);
		var methodSel = document.getElementById("usis-proj-edit-invoice-method");
		if (methodSel) methodSel.addEventListener("change", onInvoiceMethodChange);
		var shipKind = document.getElementById("usis-proj-edit-ship-kind");
		if (shipKind) shipKind.addEventListener("change", toggleShipOfficeField);
	}

	function renderJobMap(merged) {
		var card = document.getElementById("usis-proj-job-map-card");
		var frame = document.getElementById("usis-proj-job-map");
		var open = document.getElementById("usis-proj-job-map-open");
		if (!card || !frame) return;
		var q = locationQuery(merged);
		if (!q) {
			card.classList.add("d-none");
			frame.removeAttribute("src");
			if (open) {
				open.removeAttribute("href");
				open.classList.add("d-none");
			}
			return;
		}
		var encoded = encodeURIComponent(q);
		frame.src = "https://maps.google.com/maps?q=" + encoded + "&z=16&output=embed";
		if (open) {
			open.href = "https://www.google.com/maps/search/?api=1&query=" + encoded;
			open.classList.remove("d-none");
		}
		card.classList.remove("d-none");
	}

	function render(item, lead) {
		lastProjectItem = item;
		if (lead !== undefined) lastLeadItem = lead;
		else lead = lastLeadItem;
		lead = lead || {};

		var jobName = item.name || lead.name || "Untitled project";
		var jobNumber = item.number || lead.number;
		var title = document.getElementById("usis-proj-job-title");
		if (title) title.textContent = jobNumber ? jobNumber + " | " + jobName : jobName;

		var sub = document.getElementById("usis-proj-job-subtitle");
		if (sub) {
			var bits = [];
			if (lead.trade_name) bits.push(lead.trade_name);
			else if (item.project_type) bits.push(humanizeToken(item.project_type));
			var cityState = [pick(item, lead, "city"), pick(item, lead, "state")].filter(Boolean).join(", ");
			if (cityState) bits.push(cityState);
			sub.textContent = bits.join(" · ") || "Project details";
		}

		var dueBadge = document.getElementById("usis-proj-job-badge-due");
		if (dueBadge) {
			if (lead.due_at) {
				dueBadge.className = "small fw-medium " + dueClass(lead.due_at);
				var dueStr = formatJobDate(lead.due_at);
				dueBadge.textContent = dueStr ? "Due " + dueStr : "";
			} else {
				dueBadge.className = "small text-muted";
				dueBadge.textContent = "";
			}
		}

		var st = document.getElementById("usis-proj-job-status");
		if (st) {
			var statusBits = [];
			if (item.status) statusBits.push(humanizeToken(item.status));
			if (item.project_type) statusBits.push(humanizeToken(item.project_type));
			st.textContent = statusBits.join(" · ");
			st.className = "small text-muted";
		}

		var loc = projectLocation(item) || lead.location;
		var merged = {
			latitude: item.latitude,
			longitude: item.longitude,
			city: pick(item, lead, "city"),
			state: pick(item, lead, "state"),
			location: loc,
		};
		renderJobMap(merged);

		var cur = lead.default_currency || "USD";
		var pub = document.getElementById("usis-proj-job-public-tbody");
		if (pub) {
			pub.innerHTML = "";
			appendFieldRow(pub, "Project #", fmtDash(jobNumber));
			appendFieldRow(pub, "Project name", fmtDash(jobName));
			appendDateRow(pub, "Bid due", lead.due_at);
			var locStr = formatLocation(loc);
			if (locStr) {
				appendFieldRow(pub, "Location", '<div class="small" style="white-space:pre-wrap;">' + esc(locStr) + "</div>");
			} else if (merged.city || merged.state) {
				appendFieldRow(pub, "Location", fmtDash([merged.city, merged.state].filter(Boolean).join(", ")));
			} else {
				appendFieldRow(pub, "Location", '<span class="text-muted">No location on file.</span>');
			}
			var ship = item.job_shipping || {};
			appendFieldRow(
				pub,
				"Ship to",
				fmtDash(ship.shipping_label || (item.ship_to_kind === "office" ? "Office" : "Jobsite"))
			);
			appendFieldRow(
				pub,
				"Shipping address",
				ship.shipping_address
					? '<div class="small" style="white-space:pre-wrap;">' + esc(ship.shipping_address) + "</div>"
					: '<span class="text-muted">No shipping address on file.</span>'
			);
			appendDateRow(pub, "Job walk", lead.job_walk_at);
			appendDateRow(pub, "RFIs due", lead.rfis_due_at);
			appendDateRow(pub, "Expected start", item.start_date || lead.expected_start_at);
			appendDateRow(pub, "Expected install date", item.expected_install_date || ship.expected_install_date_explicit);
			appendDateRow(pub, "Expected finish", item.substantial_completion_date || lead.expected_finish_at);
			appendFieldRow(
				pub,
				"Project size",
				fmtDash(formatMoneyCur(lead.project_size != null ? lead.project_size : item.contract_value, cur))
			);
			appendFieldRow(pub, "Architect", fmtDash(lead.architect || item.architect_company_name));
			appendFieldRow(pub, "Engineer", fmtDash(lead.engineer));
			appendFieldRow(pub, "Property owner", fmtDash(lead.property_owner || item.owner_company_name));
			appendFieldRow(pub, "Tenant", fmtDash(lead.property_tenant));
			appendDateRow(pub, "Invite received", lead.invited_at);
			appendDateRow(pub, "Contract start", item.contract_date || lead.contract_start_at || lead.contract_date);
			appendDateRow(pub, "Closeout", item.closeout_date);
			appendDateRow(pub, "Created (BC)", lead.bc_created_at);
			appendDateRow(pub, "Last updated (BC)", lead.bc_updated_at);
		}

		var desc = document.getElementById("usis-proj-job-description");
		if (desc) {
			var narrative = lead.project_information || item.description || item.notes;
			if (narrative && String(narrative).trim()) {
				desc.innerHTML = '<div class="small" style="white-space:pre-wrap;">' + esc(narrative) + "</div>";
			} else {
				desc.innerHTML =
					'<p class="text-muted small mb-0">No project description was provided in Building Connected for this opportunity.</p>';
			}
		}

		var trade = document.getElementById("usis-proj-job-trade");
		if (trade) {
			if (lead.trade_specific_instructions && String(lead.trade_specific_instructions).trim()) {
				trade.innerHTML =
					'<div style="white-space:pre-wrap;">' + esc(lead.trade_specific_instructions) + "</div>";
			} else {
				trade.innerHTML = '<p class="text-muted small mb-0">No trade-specific instructions.</p>';
			}
		}

		var adv = document.getElementById("usis-proj-job-advanced");
		if (adv) {
			var abits = [];
			abits.push("<div><strong>NDA required:</strong> " + yn(lead.is_nda_required) + "</div>");
			abits.push("<div><strong>Sealed bidding:</strong> " + yn(lead.is_sealed_bidding) + "</div>");
			abits.push("<div><strong>Discoverable / public project:</strong> " + yn(lead.project_is_public) + "</div>");
			abits.push("<div><strong>Archived:</strong> " + yn(lead.is_archived != null ? lead.is_archived : item.status === "archived") + "</div>");
			if (lead.is_parent != null) {
				abits.push("<div><strong>Parent invite (BC):</strong> " + yn(lead.is_parent) + "</div>");
			}
			adv.innerHTML = abits.join("");
		}

		var priv = document.getElementById("usis-proj-job-private-tbody");
		if (priv) {
			priv.innerHTML = "";
			appendFieldRow(priv, "Request type / budgeting", fmtDash(lead.request_type || item.project_type));
			appendFieldRow(priv, "Client (company)", fmtDash(lead.company_name || lead.gc_company_name || item.gc_company_name));
			appendFieldRow(priv, "Primary contact", fmtDash(lead.client_contact));
			appendFieldRow(priv, "Fee %", fmtDash(formatPercent(lead.fee_percentage)));
			appendFieldRow(priv, "Profit margin", fmtDash(formatPercent(lead.profit_margin)));
			appendFieldRow(priv, "Market sector", fmtDash(lead.market_sector));
			appendFieldRow(priv, "Owning office (id)", fmtDash(lead.owning_office_id));
			appendFieldRow(priv, "Workflow bucket", fmtDash(lead.workflow_bucket));
			appendFieldRow(priv, "ROM", fmtDash(formatMoneyCur(lead.rom, cur)));
			appendFieldRow(
				priv,
				"Project value / final",
				fmtDash(
					formatMoneyCur(
						lead.final_value != null
							? lead.final_value
							: item.contract_value != null
								? item.contract_value
								: lead.contract_value,
						cur
					)
				)
			);
			appendFieldRow(priv, "CRM stage", fmtDash(lead.crm_stage));
			appendFieldRow(priv, "Win probability", fmtDash(formatPercent(lead.win_probability)));
			appendFieldRow(priv, "Estimating hours", fmtDash(lead.estimating_hours));
			appendFieldRow(priv, "Contract duration (days)", fmtDash(lead.contract_duration));
			appendFieldRow(priv, "Avg. crew size", fmtDash(lead.average_crew_size));
			if (lead.takeoff_line_count != null) {
				appendFieldRow(priv, "Takeoff lines", '<span class="fw-medium">' + esc(String(lead.takeoff_line_count)) + "</span>");
			}
			appendFieldRow(priv, "Priority", fmtDash(lead.priority));
			appendDateRow(priv, "Follow-up", lead.follow_up_at);
			appendFieldRow(
				priv,
				"Retention %",
				item.retention_percentage != null ? esc(String(item.retention_percentage)) : '<span class="text-muted">—</span>'
			);
			appendFieldRow(priv, "Prevailing wage", esc(fmtBool(!!item.prevailing_wage)));
			appendFieldRow(priv, "DBE required", esc(fmtBool(!!item.dbe_required)));
			appendFieldRow(priv, "Sage project id", fmtDash(item.sage_project_id));
			appendFieldRow(priv, "Textura project id", fmtDash(item.textura_project_id));
			appendFieldRow(priv, "Invoice method", fmtDash(item.invoice_method_label || item.invoice_method));
			appendDateRow(priv, "Invoice due date", item.invoice_due_date);
			appendFieldRow(
				priv,
				"Invoice emails",
				item.invoice_method === "email"
					? fmtDash(item.invoice_recipient_emails)
					: '<span class="text-muted">—</span>'
			);
			if (item.notes && String(item.notes).trim() && item.notes !== (lead.project_information || item.description)) {
				appendFieldRow(
					priv,
					"Notes",
					'<div class="small" style="white-space:pre-wrap;">' + esc(item.notes) + "</div>"
				);
			}
		}

		renderMembers(document.getElementById("usis-proj-job-members"), lead.members);

		var foot = document.getElementById("usis-proj-job-footer");
		if (foot) {
			var extras = [];
			extras.push("Project id <code>" + esc(item.id || "—") + "</code>");
			if (lead.external_id || lead.id) {
				extras.push(
					" · Building Connected ref <code>" +
						esc(lead.external_id || "—") +
						"</code> · Internal id <code>" +
						esc(lead.id || "—") +
						"</code>"
				);
			}
			if (item.primary_lead_detail_id) {
				extras.push(
					' · <a class="link-primary" href="construction/lead-detail.html?id=' +
						encodeURIComponent(item.primary_lead_detail_id) +
						'">Open lead</a>'
				);
				extras.push(
					' · <a class="link-secondary" href="construction/estimate-detail.html?id=' +
						encodeURIComponent(item.primary_lead_detail_id) +
						'">Open estimate</a>'
				);
			} else {
				extras.push(' · <span class="text-muted">No linked lead on file for this project.</span>');
			}
			foot.innerHTML = extras.join("");
		}

		var root = document.getElementById("usis-project-job-root");
		if (root) root.classList.remove("d-none");
	}

	function wireProjectRfpLinks(projectId) {
		if (!projectId) return;
		var q = "?project_id=" + encodeURIComponent(projectId);
		var base = "../usis-rfp-list.html" + q;
		var c = document.getElementById("usis-proc-rfp-full-list");
		if (c) c.setAttribute("href", base);
	}

	function wireContractAdminHubLink(projectId) {
		var el = document.getElementById("usis-proj-contract-admin-hub");
		if (!el) return;
		if (!projectId) {
			el.classList.add("d-none");
			return;
		}
		el.setAttribute("href", "../usis-procurement.html?project_id=" + encodeURIComponent(projectId));
		el.classList.remove("d-none");
	}

	/** Procurement tab: show this job in the horizontal toolbar (tooltip + optional # suffix). */
	function wireProcurementTabProjectScope(item, projectId) {
		var btn = document.getElementById("proj-tab-procurement");
		if (!btn || !item || !projectId) return;
		var name = (item.name && String(item.name).trim()) || "This project";
		var num = item.number != null && String(item.number).trim() ? String(item.number).trim() : "";
		var labelBits = ["Procurement for this job: " + name];
		if (num) labelBits.push("job #" + num);
		labelBits.push("project id " + projectId);
		var full = labelBits.join(" — ");
		btn.setAttribute("title", full);
		btn.setAttribute("aria-label", full);
		btn.textContent = "Procurement";
	}

	function init() {
		var pid = projectIdFromQuery();
		wireContractAdminHubLink(null);
		setJobPaneError("");
		if (!pid) {
			setJobPaneLoading(false);
			setJobPaneError("No project id in the URL — open this page from the Projects table.");
			return;
		}
		setJobPaneLoading(true);
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(pid);
		fetch(url, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var item = data.item;
				if (!item) throw new Error("Missing item in response");
				lastProjectId = pid;
				lastProjectItem = item;
				if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
					window.USISProjectContext.setProjectId(pid);
				}
				wireContractAdminToolsOnce();
				wireProjectEditOnce();
				fillContractAdminFromProject(item);
				loadContractAdminCommitmentSummary(pid);
				refreshPrimeSovSummary(pid);
				wireProjectRfpLinks(pid);
				wireContractAdminHubLink(pid);
				wireProcurementTabProjectScope(item, pid);
				return fetchLinkedLead(item).then(function (lead) {
					lastLeadItem = lead;
					render(item, lead);
					setJobPaneLoading(false);
				});
			})
			.catch(function (err) {
				setJobPaneLoading(false);
				wireContractAdminHubLink(null);
				setJobPaneError(err.message || String(err));
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			wireContractAdminToolsOnce();
			wireProjectEditOnce();
			init();
		});
	} else {
		wireContractAdminToolsOnce();
		wireProjectEditOnce();
		init();
	}
})();
