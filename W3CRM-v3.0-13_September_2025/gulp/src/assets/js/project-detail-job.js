/**
 * Active project detail — Job info tab from GET /api/v1/projects/<uuid>.
 */
(function () {
	"use strict";

	var lastProjectId = null;
	var lastSageProjectIdStr = "";
	var lastPrimeContractValueNum = null;

	var DEV_SERVER_PORTS = {
		3000: 1,
		3001: 1,
		3002: 1,
		4173: 1,
		5173: 1,
		5174: 1,
		5500: 1,
		5501: 1,
		8080: 1,
		4200: 1,
		4321: 1,
		9630: 1,
		1234: 1,
	};

	function explicitWindowApiBase() {
		if (typeof window.USIS_API_BASE !== "string") return null;
		var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
		if (!s) return null;
		try {
			if (new URL(s).origin === window.location.origin) return null;
		} catch (e) {
			/* keep s */
		}
		return s;
	}

	function metaApiBase() {
		if (typeof document === "undefined" || !document.querySelector) return null;
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		if (DEV_SERVER_PORTS[port]) return proto + "//" + host + ":5000";
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
			return proto + "//" + host + ":5000";
		}
		var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
		if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
			return proto + "//" + host + ":5000";
		}
		if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
			return proto + "//" + host + ":5000";
		}
		return "";
	}

	function projectIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
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
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
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

	function tr(label, innerHtml) {
		return (
			"<tr><th class=\"text-muted small fw-normal\" style=\"width:42%\">" +
			esc(label) +
			"</th><td>" +
			innerHtml +
			"</td></tr>"
		);
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

	function render(item) {
		var title = document.getElementById("usis-proj-job-title");
		var sub = document.getElementById("usis-proj-job-subtitle");
		var st = document.getElementById("usis-proj-job-status");
		var ty = document.getElementById("usis-proj-job-type");
		var tbody = document.getElementById("usis-proj-job-tbody");
		var desc = document.getElementById("usis-proj-job-description");
		var notes = document.getElementById("usis-proj-job-notes");
		var leadWrap = document.getElementById("usis-proj-job-leadlink-wrap");
		var root = document.getElementById("usis-project-job-root");

		if (title) title.textContent = item.name || "—";
		if (sub) {
			var bits = [];
			if (item.number) bits.push("#" + item.number);
			if (item.city || item.state) bits.push([item.city, item.state].filter(Boolean).join(", "));
			sub.textContent = bits.join(" · ") || "";
		}
		if (st) {
			st.textContent = item.status || "—";
			st.className = "badge bg-light text-dark border";
		}
		if (ty) {
			ty.textContent = item.project_type ? String(item.project_type).replace(/_/g, " ") : "—";
			ty.className = "badge bg-light text-muted border text-capitalize";
		}

		var addr = [item.address_line1, item.address_line2].filter(Boolean).join(", ");
		var cityLine = [item.city, item.state, item.postal_code].filter(Boolean).join(" ");
		if (item.country && item.country !== "US") cityLine = (cityLine ? cityLine + ", " : "") + item.country;

		var rows = [
			tr("Project id", fmtDash(item.id)),
			tr("Number", fmtDash(item.number)),
			tr("Address", fmtDash(addr || null)),
			tr("City / ZIP", fmtDash(cityLine || null)),
			tr("Contract value", fmtMoney(item.contract_value)),
			tr("Contract date", fmtDate(item.contract_date)),
			tr("Start date", fmtDate(item.start_date)),
			tr("Substantial completion", fmtDate(item.substantial_completion_date)),
			tr("Closeout", fmtDate(item.closeout_date)),
			tr("Retention %", item.retention_percentage != null ? esc(String(item.retention_percentage)) : "—"),
			tr("Prevailing wage", esc(fmtBool(!!item.prevailing_wage))),
			tr("DBE required", esc(fmtBool(!!item.dbe_required))),
			tr("GC", fmtDash(item.gc_company_name)),
			tr("Owner", fmtDash(item.owner_company_name)),
			tr("Architect", fmtDash(item.architect_company_name)),
			tr("Sage project id", fmtDash(item.sage_project_id)),
			tr("Updated", fmtDate(item.updated_at)),
			tr("Created", fmtDate(item.created_at)),
		];
		if (tbody) tbody.innerHTML = rows.join("");

		if (desc) {
			desc.innerHTML = item.description
				? "<div class=\"text-body\">" + esc(item.description).replace(/\n/g, "<br>") + "</div>"
				: '<span class="text-muted">—</span>';
		}
		if (notes) {
			notes.innerHTML = item.notes
				? "<div class=\"text-body\">" + esc(item.notes).replace(/\n/g, "<br>") + "</div>"
				: '<span class="text-muted">—</span>';
		}
		if (leadWrap) {
			if (item.primary_lead_detail_id) {
				var href = "construction/lead-detail.html?id=" + encodeURIComponent(item.primary_lead_detail_id);
				leadWrap.innerHTML =
					'<a class="link-primary" href="' +
					href +
					'">Open linked lead / opportunity</a> <span class="text-muted">(Building Connected)</span>';
			} else {
				leadWrap.innerHTML = '<span class="text-muted">No linked lead on file for this project.</span>';
			}
		}
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
		btn.textContent = num ? "Procurement · #" + num : "Procurement";
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
				setJobPaneLoading(false);
				var item = data.item;
				if (!item) throw new Error("Missing item in response");
				lastProjectId = pid;
				wireContractAdminToolsOnce();
				render(item);
				fillContractAdminFromProject(item);
				loadContractAdminCommitmentSummary(pid);
				refreshPrimeSovSummary(pid);
				wireProjectRfpLinks(pid);
				wireContractAdminHubLink(pid);
				wireProcurementTabProjectScope(item, pid);
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
			init();
		});
	} else {
		wireContractAdminToolsOnce();
		init();
	}
})();
