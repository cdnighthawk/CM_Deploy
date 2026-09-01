/**
 * RFP detail — body (takeoff / manual / narrative), drawings, quotes@ send.
 */
(function () {
	"use strict";

	var UNITS = ["SF", "LF", "SY", "EA", "LS", "HR", "GAL", "SQ"];
	var state = {
		id: null,
		rfp: null,
		bidders: [],
		takeoff: null,
		drawCandidates: [],
		searchTimer: null,
		vendorSearchSeq: 0,
		frozen: false,
		costCodes: [],
	};

	function $(id) {
		return document.getElementById(id);
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

	function apiUrl(path) {
		if (window.USIS_API && typeof window.USIS_API.buildUrl === "function" && path.indexOf("/api/") === 0) {
			return window.USIS_API.buildUrl(path);
		}
		return path;
	}

	function actorHeaders() {
		if (window.USIS_API && typeof window.USIS_API.actorHeaders === "function") {
			return window.USIS_API.actorHeaders();
		}
		return {};
	}

	function flash(msg, kind) {
		var el = $("usis-rfp-flash");
		if (!el) return;
		el.className = "alert py-2 px-3 mb-3 " + (kind === "error" ? "alert-danger" : kind === "warn" ? "alert-warning" : "alert-success");
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function fmtWhen(iso) {
		if (!iso) return "—";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return esc(iso);
		return d.toLocaleString();
	}

	function sourceLabel(src) {
		if (src === "email") return "Email";
		if (src === "portal") return "Portal";
		if (src === "upload") return "PDF";
		return "Invited";
	}

	function lineSource() {
		var el = document.querySelector("input[name='usis-rfp-source']:checked");
		return el ? el.value : "manual";
	}

	function setFrozen(frozen) {
		state.frozen = !!frozen;
		document.querySelectorAll("#usis-rfp-title-input, #usis-rfp-due-input, #usis-rfp-scope, #usis-rfp-inclusions, #usis-rfp-exclusions, #usis-rfp-clarifications, #usis-rfp-src-takeoff, #usis-rfp-src-manual, #usis-rfp-src-narrative, #usis-rfp-add-line, #usis-rfp-attach, #usis-rfp-refresh-takeoff").forEach(function (el) {
			if (el) el.disabled = state.frozen;
		});
	}

	function applySourceUi() {
		var src = lineSource();
		var takeoff = $("usis-rfp-takeoff-panel");
		var lines = $("usis-rfp-lines-panel");
		var internal = $("usis-rfp-internal-lines");
		if (takeoff) takeoff.classList.toggle("d-none", src !== "takeoff");
		if (lines) lines.classList.toggle("d-none", src === "narrative");
		if (internal) internal.classList.toggle("d-none", src !== "narrative");
	}

	function renderHeader(item) {
		var title = $("usis-rfp-title-input");
		if (title && document.activeElement !== title) title.value = item.title || "";
		var status = $("usis-rfp-status");
		if (status) {
			status.innerHTML = window.USISUi ? window.USISUi.statusChip(item.status || "Draft") : esc(item.status || "Draft");
		}
		var due = $("usis-rfp-due-input");
		if (due && document.activeElement !== due) due.value = item.due_at ? String(item.due_at).slice(0, 10) : "";
		var mailbox = $("usis-rfp-mailbox");
		if (mailbox) mailbox.textContent = item.from_header || item.quotes_mailbox || "quotes@gousis.com";
		var tag = $("usis-rfp-mail-tag");
		if (tag) tag.textContent = item.mail_tag ? "[RFP " + item.mail_tag + "]" : "";
		var cmp = $("usis-rfp-compare-link");
		if (cmp) cmp.href = "usis-rfp-compare.html?id=" + encodeURIComponent(item.id);
		var src = item.line_source || "manual";
		var radio = document.querySelector("input[name='usis-rfp-source'][value='" + src + "']");
		if (radio) radio.checked = true;
		["scope", "inclusions", "exclusions", "clarifications"].forEach(function (k) {
			var el = $("usis-rfp-" + (k === "scope" ? "scope" : k));
			if (el && document.activeElement !== el) el.value = item[k === "scope" ? "scope_of_work" : k] || "";
		});
		var cc = $("usis-rfp-cc-estimator");
		if (cc) cc.checked = !!item.cc_estimator;
		setFrozen(!!item.frozen);
		applySourceUi();
	}

	function loadCostCodes() {
		return fetchJson("/api/v1/cost-codes?active=1")
			.then(function (data) {
				state.costCodes = (data && data.items) || [];
			})
			.catch(function () {
				state.costCodes = [];
			});
	}

	function costCodeByCode(code) {
		var key = String(code || "").trim();
		if (!key) return null;
		for (var i = 0; i < (state.costCodes || []).length; i++) {
			if (String(state.costCodes[i].code || "") === key) return state.costCodes[i];
		}
		return null;
	}

	function csiOptionsHtml(selected) {
		var key = String(selected || "").trim();
		var html = "<option value=''>Select CSI…</option>";
		var seen = {};
		(state.costCodes || []).forEach(function (it) {
			if (!it || !it.code) return;
			seen[it.code] = true;
			var label = it.code + (it.description ? " — " + it.description : "");
			html +=
				"<option value='" +
				esc(it.code) +
				"'" +
				(key === it.code ? " selected" : "") +
				">" +
				esc(label) +
				"</option>";
		});
		if (key && !seen[key]) {
			html += "<option value='" + esc(key) + "' selected>" + esc(key) + "</option>";
		}
		return html;
	}

	function csiFieldHtml(ln) {
		var selected = ln.csi_division || "";
		if (!(state.costCodes || []).length) {
			return (
				"<td><input class='form-control form-control-sm' data-f='csi_division' value='" +
				esc(selected) +
				"'></td>"
			);
		}
		return (
			"<td><select class='form-select form-select-sm' data-f='csi_division'>" +
			csiOptionsHtml(selected) +
			"</select></td>"
		);
	}

	function applyCostCodeDefaults(tr, code) {
		var master = costCodeByCode(code);
		if (!master || !tr) return;
		var desc = tr.querySelector("[data-f='description']");
		if (desc && (!String(desc.value || "").trim() || String(desc.value).trim() === "New item")) {
			desc.value = master.description || desc.value;
		}
		var unit = tr.querySelector("[data-f='unit']");
		if (unit && master.units) {
			var current = String(unit.value || "").trim();
			if (!current || current === "EA") {
				if (UNITS.indexOf(master.units) === -1) UNITS.push(master.units);
				if (!Array.prototype.some.call(unit.options, function (opt) { return opt.value === master.units; })) {
					var extra = document.createElement("option");
					extra.value = master.units;
					extra.textContent = master.units;
					unit.appendChild(extra);
				}
				unit.value = master.units;
			}
		}
	}

	function renderLines(item) {
		var tb = $("usis-rfp-lines-body");
		if (!tb) return;
		var lines = item.line_items || [];
		if (!lines.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted">No line items yet.</td></tr>';
			return;
		}
		tb.innerHTML = lines
			.map(function (ln) {
				var unitOpts = UNITS.map(function (u) {
					return "<option" + (ln.unit === u ? " selected" : "") + ">" + u + "</option>";
				}).join("");
				if (ln.unit && UNITS.indexOf(ln.unit) === -1) {
					unitOpts += "<option selected>" + esc(ln.unit) + "</option>";
				}
				var badge = ln.source_kind === "takeoff" ? "Takeoff" : "Manual";
				return (
					"<tr data-line='" +
					esc(ln.id) +
					"'>" +
					csiFieldHtml(ln) +
					"<td><input class='form-control form-control-sm' data-f='description' value='" +
					esc(ln.description) +
					"'></td>" +
					"<td><input class='form-control form-control-sm' data-f='quantity' type='number' step='any' value='" +
					esc(ln.quantity == null ? "" : ln.quantity) +
					"'></td>" +
					"<td><select class='form-select form-select-sm' data-f='unit'>" +
					unitOpts +
					"</select></td>" +
					"<td><input class='form-control form-control-sm' data-f='notes' value='" +
					esc(ln.notes) +
					"'></td>" +
					"<td>" +
					(window.USISUi ? window.USISUi.statusChip(badge) : esc(badge)) +
					"</td>" +
					"<td><button type='button' class='btn btn-link btn-sm p-0' data-del='" +
					esc(ln.id) +
					"'>Delete</button></td></tr>"
				);
			})
			.join("");
		tb.querySelectorAll("[data-del]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				if (state.frozen) return;
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/line-items/" + encodeURIComponent(btn.getAttribute("data-del")), {
					method: "DELETE",
				}).then(load);
			});
		});
		tb.querySelectorAll("input,select").forEach(function (inp) {
			inp.disabled = state.frozen;
			inp.addEventListener("change", function () {
				if (state.frozen) return;
				var tr = inp.closest("tr");
				var lid = tr.getAttribute("data-line");
				if (inp.getAttribute("data-f") === "csi_division") applyCostCodeDefaults(tr, inp.value);
				var body = {};
				tr.querySelectorAll("[data-f]").forEach(function (f) {
					body[f.getAttribute("data-f")] = f.value;
				});
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/line-items/" + encodeURIComponent(lid), {
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(body),
				}).catch(function (err) {
					flash(err.message || String(err), "error");
				});
			});
		});
	}

	function isPdfFile(file) {
		if (!file) return false;
		var name = (file.name || "").toLowerCase();
		return name.slice(-4) === ".pdf" || (file.type || "") === "application/pdf";
	}

	function fillQuoteVendorSelect(item) {
		var sel = $("usis-rfp-quote-vendor");
		if (!sel) return;
		var quotes = (item && item.quotes) || [];
		var opts = [];
		quotes.forEach(function (q) {
			opts.push({ value: "q:" + q.id, label: q.vendor_label || "Vendor" });
		});
		(state.bidders || []).forEach(function (b) {
			if (!b.company_id) return;
			var already = quotes.some(function (q) {
				return q.vendor_company_id === b.company_id;
			});
			if (!already) opts.push({ value: "c:" + b.company_id, label: (b.label || "Vendor") + " (new)" });
		});
		var prev = sel.value;
		sel.innerHTML =
			'<option value="">' +
			(opts.length ? "Select a vendor" : "Add a vendor first") +
			"</option>" +
			opts
				.map(function (o) {
					return "<option value='" + esc(o.value) + "'>" + esc(o.label) + "</option>";
				})
				.join("");
		if (opts.length === 1) sel.value = opts[0].value;
		else if (
			prev &&
			[].some.call(sel.options, function (o) {
				return o.value === prev;
			})
		) {
			sel.value = prev;
		}
		var closed = item && (item.status === "Awarded" || item.status === "Closed");
		sel.disabled = !!closed;
		var input = $("usis-rfp-quote-pdf");
		if (input) input.disabled = !!closed;
		var drop = $("usis-rfp-quote-drop");
		if (drop) drop.style.opacity = closed ? "0.55" : "";
	}

	function resolveQuoteTarget() {
		var sel = $("usis-rfp-quote-vendor");
		var val = sel ? sel.value : "";
		if (val.indexOf("q:") === 0) return { quoteId: val.slice(2), companyId: null };
		if (val.indexOf("c:") === 0) return { quoteId: null, companyId: val.slice(2) };
		return { quoteId: null, companyId: null };
	}

	function uploadQuotePdf(file, quoteId, companyId) {
		var fd = new FormData();
		fd.append("file", file);
		var url;
		if (quoteId) {
			url = "/api/v1/rfps/" + encodeURIComponent(state.id) + "/quotes/" + encodeURIComponent(quoteId) + "/attachments";
		} else {
			url = "/api/v1/rfps/" + encodeURIComponent(state.id) + "/quote-pdf";
			if (companyId) fd.append("company_id", companyId);
		}
		return fetch(apiUrl(url), {
			method: "POST",
			credentials: "include",
			headers: actorHeaders(),
			body: fd,
		}).then(function (res) {
			return res.json().then(function (j) {
				if (!res.ok) throw new Error(j.error || res.statusText || String(res.status));
				return j;
			});
		});
	}

	function handleQuotePdfFile(file) {
		if (!isPdfFile(file)) {
			flash("Only PDF quotes are accepted", "error");
			return;
		}
		var target = resolveQuoteTarget();
		if (!target.quoteId && !target.companyId) {
			flash("Select a vendor for this PDF", "error");
			return;
		}
		var nameEl = $("usis-rfp-quote-pdf-name");
		if (nameEl) nameEl.textContent = "Uploading " + file.name + "…";
		uploadQuotePdf(file, target.quoteId, target.companyId)
			.then(function () {
				flash("Quote PDF saved", "ok");
				if (nameEl) nameEl.textContent = "or click to browse · PDF only, max 25 MB";
				return load();
			})
			.catch(function (err) {
				flash(err.message || String(err), "error");
				if (nameEl) nameEl.textContent = "or click to browse · PDF only, max 25 MB";
			});
	}

	function bindQuoteDrop() {
		var drop = $("usis-rfp-quote-drop");
		var input = $("usis-rfp-quote-pdf");
		if (!drop || !input || drop.getAttribute("data-bound") === "1") return;
		drop.setAttribute("data-bound", "1");
		drop.addEventListener("dragover", function (ev) {
			ev.preventDefault();
			drop.classList.add("is-drag");
			drop.style.borderColor = "#1F4E5F";
			drop.style.background = "#eef5f7";
		});
		drop.addEventListener("dragleave", function () {
			drop.classList.remove("is-drag");
			drop.style.borderColor = "#E3E8EE";
			drop.style.background = "#fafbfc";
		});
		drop.addEventListener("drop", function (ev) {
			ev.preventDefault();
			drop.classList.remove("is-drag");
			drop.style.borderColor = "#E3E8EE";
			drop.style.background = "#fafbfc";
			var file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
			if (file) handleQuotePdfFile(file);
		});
		input.addEventListener("change", function () {
			var file = input.files && input.files[0];
			if (file) handleQuotePdfFile(file);
			input.value = "";
		});
	}

	function renderQuotes(item) {
		fillQuoteVendorSelect(item);
		var tb = $("usis-rfp-quotes-body");
		if (!tb) return;
		var quotes = item.quotes || [];
		if (!quotes.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted">No invitations or quotes yet. Drop a vendor PDF above after selecting a vendor.</td></tr>';
			return;
		}
		tb.innerHTML = quotes
			.map(function (q) {
				var atts = (q.attachments || [])
					.map(function (a) {
						var label = esc(a.name || "quote.pdf");
						if (a.file_url) {
							return "<a href='" + esc(apiUrl(a.file_url)) + "' target='_blank' rel='noopener'>" + label + "</a>";
						}
						return label;
					})
					.join(", ");
				var lump = q.lump_sum_amount != null ? " · LS $" + q.lump_sum_amount : "";
				return (
					"<tr>" +
					"<td>" +
					esc(q.vendor_label) +
					"</td>" +
					"<td>" +
					esc(q.invited_email || q.from_email || "") +
					"</td>" +
					"<td>" +
					esc(sourceLabel(q.source)) +
					"</td>" +
					"<td>" +
					fmtWhen(q.sent_at) +
					"</td>" +
					"<td>" +
					fmtWhen(q.received_at) +
					"</td>" +
					"<td><div class='small'>" +
					esc(q.notes || "") +
					lump +
					"</div>" +
					(atts ? "<div class='small mt-1'>" + atts + "</div>" : "") +
					"</td>" +
					"<td class='text-nowrap'>" +
					"<button type='button' class='btn btn-sm btn-outline-secondary me-1' data-attach='" +
					esc(q.id) +
					"'>PDF</button>" +
					(q.received_at
						? "<button type='button' class='btn btn-sm btn-outline-primary' data-award='" +
						  esc(q.id) +
						  "'>Award</button>"
						: "") +
					"</td></tr>"
				);
			})
			.join("");
		tb.querySelectorAll("[data-attach]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var sel = $("usis-rfp-quote-vendor");
				if (sel) sel.value = "q:" + btn.getAttribute("data-attach");
				var input = $("usis-rfp-quote-pdf");
				if (input && !input.disabled) input.click();
			});
		});
		tb.querySelectorAll("[data-award]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				if (!window.confirm("Award this vendor?")) return;
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/award", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ quote_id: btn.getAttribute("data-award") }),
				})
					.then(load)
					.catch(function (err) {
						flash(err.message || String(err), "error");
					});
			});
		});
	}

	function renderBidders() {
		if (state.rfp) fillQuoteVendorSelect(state.rfp);
		var wrap = $("usis-rfp-bidder-chips");
		if (!wrap) return;
		if (!state.bidders.length) {
			wrap.innerHTML = '<span class="text-muted small">Select vendors with an email on the company record.</span>';
			return;
		}
		wrap.innerHTML = state.bidders
			.map(function (b, i) {
				var missing = b.missing_email;
				return (
					'<div class="form-check small mb-1">' +
					'<input class="form-check-input" type="checkbox" data-sel="' +
					i +
					'" ' +
					(b.selected !== false && !missing ? "checked" : "") +
					" " +
					(missing ? "disabled" : "") +
					">" +
					"<label class='form-check-label'>" +
					esc(b.label) +
					(b.email ? " &lt;" + esc(b.email) + "&gt;" : " <span class='text-danger'>no email</span>") +
					(missing
						? " <a href='" +
						  esc(b.company_edit_url || "usis-companies.html?id=" + b.company_id) +
						  "'>Add email on the vendor record</a>"
						: "") +
					' <button type="button" class="btn btn-link btn-sm p-0" data-remove="' +
					i +
					'">×</button></label></div>'
				);
			})
			.join("");
		wrap.querySelectorAll("[data-remove]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				state.bidders.splice(Number(btn.getAttribute("data-remove")), 1);
				renderBidders();
			});
		});
	}

	function addBidder(row) {
		var email = (row.email || "").trim().toLowerCase();
		var exists = state.bidders.some(function (b) {
			return b.company_id && row.company_id && b.company_id === row.company_id && b.email === email;
		});
		if (exists) return;
		state.bidders.push({
			company_id: row.company_id,
			contact_id: row.contact_id || null,
			email: email,
			label: row.label,
			missing_email: !email,
			company_edit_url: row.company_edit_url,
			selected: !!email,
		});
		renderBidders();
	}

	function selectedBidders() {
		return state.bidders.filter(function (b, i) {
			var box = document.querySelector("[data-sel='" + i + "']");
			return b.email && (!box || box.checked);
		});
	}

	function renderTakeoff() {
		var data = state.takeoff || {};
		var empty = $("usis-rfp-takeoff-empty");
		var sel = $("usis-rfp-estimate");
		if (empty) empty.classList.toggle("d-none", !!data.has_estimates);
		if (sel) {
			sel.innerHTML = (data.estimates || [])
				.map(function (e) {
					return (
						"<option value='" +
						esc(e.id) +
						"'" +
						(e.id === data.estimate_id ? " selected" : "") +
						">" +
						esc(e.name) +
						" · " +
						esc(e.status) +
						" · " +
						esc(e.line_count) +
						" lines</option>"
					);
				})
				.join("");
		}
		var filter = (($("usis-rfp-trade-filter") || {}).value || "").toLowerCase();
		var tb = $("usis-rfp-takeoff-body");
		if (!tb) return;
		var lines = (data.lines || []).filter(function (ln) {
			if (!filter) return true;
			var blob = [ln.csi_division, ln.trade, ln.description, ln.notes].join(" ").toLowerCase();
			return blob.indexOf(filter) >= 0;
		});
		tb.innerHTML = lines
			.map(function (ln) {
				return (
					"<tr><td><input type='checkbox' data-tl='" +
					esc(ln.id) +
					"'" +
					(ln.remaining ? " data-remaining='1'" : "") +
					"></td><td>" +
					esc(ln.csi_division) +
					"</td><td>" +
					esc(ln.trade) +
					"</td><td>" +
					esc(ln.description) +
					"</td><td>" +
					esc(ln.quantity) +
					"</td><td>" +
					esc(ln.unit) +
					"</td><td>" +
					esc(ln.room_area) +
					"</td><td>" +
					esc(ln.notes) +
					"</td></tr>"
				);
			})
			.join("");
	}

	function loadTakeoff(estimateId) {
		var q = estimateId ? "?estimate_id=" + encodeURIComponent(estimateId) : "";
		return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/takeoff-candidates" + q).then(function (d) {
			state.takeoff = d.item || d;
			renderTakeoff();
		});
	}

	function renderDrawings() {
		var tb = $("usis-rfp-draw-body");
		if (!tb) return;
		var items = state.drawCandidates || [];
		if (!items.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted">No sheets on this job yet.</td></tr>';
			return;
		}
		tb.innerHTML = items
			.map(function (d, i) {
				var cadNote = d.is_cad && !d.has_pdf ? " <span class='text-muted'>PDF rendition required</span>" : "";
				var size = d.bytes ? (d.bytes > 1048576 ? (d.bytes / 1048576).toFixed(1) + " MB" : Math.round(d.bytes / 1024) + " KB") : "—";
				var updated = d.updated_at ? String(d.updated_at).slice(0, 10) : "—";
				return (
					"<tr data-i='" +
					i +
					"'><td><input type='checkbox' data-draw='" +
					i +
					"'" +
					(d.prechecked ? " checked" : "") +
					"></td><td>" +
					esc(d.sheet_number) +
					"</td><td>" +
					esc(d.sheet_title) +
					cadNote +
					"</td><td>" +
					esc(d.discipline) +
					"</td><td>" +
					esc(d.revision) +
					"</td><td>" +
					esc(size) +
					"</td><td>" +
					esc(updated) +
					"</td></tr>"
				);
			})
			.join("");
	}

	function loadDrawings() {
		return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/drawing-candidates").then(function (d) {
			state.drawCandidates = (d.item && d.item.items) || [];
			renderDrawings();
		});
	}

	function collectDrawings() {
		var out = [];
		(state.drawCandidates || []).forEach(function (d, i) {
			var box = document.querySelector("[data-draw='" + i + "']");
			if (!box || !box.checked) return;
			out.push({
				drawing_id: d.drawing_id,
				document_id: d.document_id,
				delivery: "link",
			});
		});
		return out;
	}

	function saveDrawings() {
		return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/drawings", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ drawings: collectDrawings() }),
		});
	}

	function saveDraft() {
		if (state.frozen) {
			flash("This RFP is frozen after Send. Clone to a new RFP to edit.", "warn");
			return Promise.resolve();
		}
		var body = {
			title: ($("usis-rfp-title-input") || {}).value,
			due_at: ($("usis-rfp-due-input") || {}).value || null,
			scope_of_work: ($("usis-rfp-scope") || {}).value,
			inclusions: ($("usis-rfp-inclusions") || {}).value,
			exclusions: ($("usis-rfp-exclusions") || {}).value,
			clarifications: ($("usis-rfp-clarifications") || {}).value,
			line_source: lineSource(),
			confirm: true,
			cc_estimator: !!(($("usis-rfp-cc-estimator") || {}).checked),
		};
		return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		})
			.then(function () {
				return saveDrawings();
			})
			.then(function () {
				flash("Draft saved.", "success");
				return load();
			})
			.catch(function (err) {
				flash(err.message || String(err), "error");
			});
	}

	function load() {
		flash("");
		return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id)).then(function (d) {
			state.rfp = d.item || d;
			renderHeader(state.rfp);
			renderLines(state.rfp);
			renderQuotes(state.rfp);
			if (lineSource() === "takeoff") loadTakeoff(state.rfp.source_estimate_id);
			loadDrawings();
			return state.rfp;
		});
	}

	function hideVendorResults() {
		var box = $("usis-rfp-vendor-results");
		if (!box) return;
		box.innerHTML = "";
		box.classList.add("d-none");
	}

	function pickVendor(row) {
		if (!row) return;
		var contacts = (row.contacts || []).filter(function (ct) {
			return ct.email;
		});
		if (contacts.length) {
			contacts.forEach(function (ct) {
				addBidder({
					company_id: row.id,
					contact_id: ct.id,
					email: ct.email,
					label: (ct.name || row.name) + " · " + row.name,
					company_edit_url: row.company_edit_url,
				});
			});
		} else {
			addBidder({
				company_id: row.id,
				email: row.email || "",
				label: row.name,
				company_edit_url: row.company_edit_url,
			});
		}
		var search = $("usis-rfp-vendor-search");
		if (search) search.value = "";
		hideVendorResults();
	}

	window.usisRfpPickVendor = pickVendor;

	function fv(id) {
		var n = $(id);
		return n ? String(n.value || "").trim() : "";
	}

	function setVendorErr(msg) {
		var box = $("usis-rfp-vendor-err");
		if (!box) return;
		box.textContent = msg || "";
		box.classList.toggle("d-none", !msg);
	}

	function vendorModal() {
		var node = $("usis-rfp-vendor-modal");
		if (!node || !window.bootstrap || !window.bootstrap.Modal) return null;
		return window.bootstrap.Modal.getOrCreateInstance(node);
	}

	function resetVendorForm() {
		setVendorErr("");
		[
			"usis-nv-name",
			"usis-nv-email",
			"usis-nv-phone",
			"usis-nv-website",
			"usis-nv-tax",
			"usis-nv-addr1",
			"usis-nv-addr2",
			"usis-nv-city",
			"usis-nv-state",
			"usis-nv-zip",
			"usis-nv-notes",
			"usis-nv-ct-first",
			"usis-nv-ct-last",
			"usis-nv-ct-title",
			"usis-nv-ct-email",
			"usis-nv-ct-phone",
			"usis-nv-ins-type",
			"usis-nv-ins-carrier",
			"usis-nv-ins-exp",
			"usis-nv-lic-type",
			"usis-nv-lic-num",
			"usis-nv-lic-exp",
		].forEach(function (id) {
			var n = $(id);
			if (n) n.value = "";
		});
		var type = $("usis-nv-type");
		if (type) type.value = "vendor";
	}

	function openVendorModal() {
		resetVendorForm();
		var modal = vendorModal();
		if (modal) modal.show();
	}

	function parseApiError(err) {
		var raw = (err && (err.body || err.message)) || String(err || "Could not save vendor");
		try {
			var j = JSON.parse(raw);
			if (j && j.error) return j.error;
		} catch (e) {}
		return raw;
	}

	function saveNewVendor() {
		var name = fv("usis-nv-name");
		var companyEmail = fv("usis-nv-email");
		var contactEmail = fv("usis-nv-ct-email");
		if (!name) {
			setVendorErr("Company name is required.");
			return;
		}
		if (!companyEmail && !contactEmail) {
			setVendorErr("Add a company email or a primary contact email so we can send the quote request.");
			return;
		}
		var btn = $("usis-rfp-vendor-save");
		if (btn) btn.disabled = true;
		setVendorErr("");
		var payload = {
			name: name,
			company_type: fv("usis-nv-type") || "vendor",
			email: companyEmail || null,
			phone: fv("usis-nv-phone") || null,
			website: fv("usis-nv-website") || null,
			tax_id: fv("usis-nv-tax") || null,
			address_line1: fv("usis-nv-addr1") || null,
			address_line2: fv("usis-nv-addr2") || null,
			city: fv("usis-nv-city") || null,
			state: fv("usis-nv-state") || null,
			postal_code: fv("usis-nv-zip") || null,
			notes: fv("usis-nv-notes") || null,
		};
		fetchJson("/api/v1/companies", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		})
			.then(function (d) {
				var item = (d && d.item) || d || {};
				var cid = item.id;
				if (!cid) throw new Error("Company was created without an id.");
				var contactPayload = {
					first_name: fv("usis-nv-ct-first") || null,
					last_name: fv("usis-nv-ct-last") || null,
					title: fv("usis-nv-ct-title") || null,
					email: contactEmail || null,
					phone: fv("usis-nv-ct-phone") || null,
					is_primary: true,
				};
				var hasContact = contactPayload.first_name || contactPayload.last_name || contactPayload.email || contactPayload.phone || contactPayload.title;
				var next = Promise.resolve({ items: [] });
				if (hasContact) {
					next = fetchJson("/api/v1/companies/" + encodeURIComponent(cid) + "/contacts", {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify(contactPayload),
					});
				}
				return next.then(function (contactsRes) {
					var extras = [];
					if (fv("usis-nv-ins-type") || fv("usis-nv-ins-carrier")) {
						extras.push(
							fetchJson("/api/v1/companies/" + encodeURIComponent(cid) + "/insurance", {
								method: "POST",
								headers: { "Content-Type": "application/json" },
								body: JSON.stringify({
									policy_type: fv("usis-nv-ins-type") || null,
									carrier: fv("usis-nv-ins-carrier") || null,
									expires_on: fv("usis-nv-ins-exp") || null,
								}),
							})
						);
					}
					if (fv("usis-nv-lic-type") || fv("usis-nv-lic-num")) {
						extras.push(
							fetchJson("/api/v1/companies/" + encodeURIComponent(cid) + "/licenses", {
								method: "POST",
								headers: { "Content-Type": "application/json" },
								body: JSON.stringify({
									license_type: fv("usis-nv-lic-type") || null,
									license_number: fv("usis-nv-lic-num") || null,
									expires_on: fv("usis-nv-lic-exp") || null,
								}),
							})
						);
					}
					return Promise.all(extras).then(function () {
						return { item: item, contacts: (contactsRes && contactsRes.items) || [] };
					});
				});
			})
			.then(function (pack) {
				var item = pack.item;
				var contacts = pack.contacts || [];
				pickVendor({
					id: item.id,
					name: item.name,
					company_type: item.company_type,
					email: item.email || contactEmail || "",
					company_edit_url: "usis-companies.html?id=" + item.id,
					contacts: contacts,
				});
				var modal = vendorModal();
				if (modal) modal.hide();
				flash("Vendor added to the directory and this RFP.", "ok");
			})
			.catch(function (err) {
				setVendorErr(parseApiError(err));
			})
			.then(function () {
				if (btn) btn.disabled = false;
			});
	}

	function searchVendors(q) {
		var box = $("usis-rfp-vendor-results");
		if (!box) return;
		q = String(q || "").trim();
		if (!q) {
			hideVendorResults();
			return;
		}
		var req = (state.vendorSearchSeq += 1);
		fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/vendors?q=" + encodeURIComponent(q)).then(function (d) {
			if (req !== state.vendorSearchSeq) return;
			var typed = (($("usis-rfp-vendor-search") || {}).value || "").trim();
			if (!typed) {
				hideVendorResults();
				return;
			}
			var items = d.items || [];
			box.classList.remove("d-none");
			if (!items.length) {
				box.innerHTML = '<div class="list-group-item text-muted small">No companies match.</div>';
				return;
			}
			box.innerHTML = items
				.slice(0, 20)
				.map(function (c) {
					return (
						'<button type="button" class="list-group-item list-group-item-action py-2" data-company="' +
						esc(c.id) +
						'" role="option">' +
						esc(c.name) +
						' <span class="text-muted small">' +
						esc(c.company_type || "") +
						(c.missing_email ? " · missing email" : "") +
						"</span></button>"
					);
				})
				.join("");
			box.querySelectorAll("[data-company]").forEach(function (btn) {
				btn.addEventListener("mousedown", function (ev) {
					ev.preventDefault();
					var cid = btn.getAttribute("data-company");
					var row = items.find(function (c) {
						return c.id === cid;
					});
					pickVendor(row);
				});
			});
		});
	}

	function preview() {
		return saveDraft().then(function () {
			return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/email-preview").then(function (d) {
				var rec = $("usis-rfp-preview-recipients");
				if (rec) {
					var list = (d.recipients || []).concat(
						selectedBidders().map(function (b) {
							return { email: b.email, vendor_label: b.label, ready: !!b.email, error: b.missing_email ? "Add email on the vendor record." : null, company_edit_url: b.company_edit_url };
						})
					);
					if (!list.length) rec.innerHTML = '<p class="text-muted">No recipients yet.</p>';
					else
						rec.innerHTML = list
							.map(function (r) {
								return (
									"<div class='mb-1'>" +
									esc(r.vendor_label) +
									" — " +
									esc(r.email || "no email") +
									(r.token_last4 ? " · token …" + esc(r.token_last4) : "") +
									(r.ready ? "" : " <span class='text-danger'>" + esc(r.error || "blocked") + "</span>") +
									(r.company_edit_url && !r.ready ? " <a href='" + esc(r.company_edit_url) + "'>Open company</a>" : "") +
									"</div>"
								);
							})
							.join("");
				}
				var msg = $("usis-rfp-preview-msg");
				if (msg) {
					msg.textContent =
						"From: " +
						(d.from_header || d.from) +
						"\nReply-To: " +
						(d.reply_to || "") +
						"\nBCC: " +
						(d.bcc || "—") +
						"\nSubject: " +
						(d.subject || "") +
						"\n\n" +
						(d.text || "");
				}
				if ((d.errors || []).length) flash(d.errors.join(" "), "error");
				else if ((d.warnings || []).length) flash(d.warnings.join(" "), "warn");
				var body = $("usis-rfp-email-body");
				if (body) body.textContent = (d.subject ? d.subject + "\n\n" : "") + (d.text || d.html || "");
				return d;
			});
		});
	}

	function sendInvites(selectedOnly) {
		var bidders = selectedOnly ? selectedBidders() : state.bidders.filter(function (b) {
			return b.email;
		});
		if (!bidders.length) {
			flash("Add at least one vendor with an email address.", "error");
			return;
		}
		var blocked = state.bidders.filter(function (b) {
			return b.missing_email;
		});
		if (blocked.length && !selectedOnly) {
			flash("Some vendors have no email. Add it on the company record.", "error");
		}
		var btn = $("usis-rfp-send");
		if (btn) btn.disabled = true;
		saveDraft()
			.then(function () {
				return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/send", {
					method: "POST",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: JSON.stringify({
						bidders: bidders.map(function (b) {
							return {
								company_id: b.company_id,
								contact_id: b.contact_id,
								email: b.email,
								vendor_label: b.label,
							};
						}),
						cc_estimator: !!(($("usis-rfp-cc-estimator") || {}).checked),
					}),
				});
			})
			.then(function (d) {
				var sends = d.sends || [];
				var dry = sends.some(function (s) {
					return s.dry_run;
				});
				var failed = sends.filter(function (s) {
					return !s.ok;
				});
				state.rfp = d.item || state.rfp;
				renderHeader(state.rfp);
				renderQuotes(state.rfp);
				if (failed.length) {
					flash("Some invitations failed: " + failed.map(function (s) { return s.error; }).join("; "), "error");
				} else if (dry) {
					flash("Invitations recorded (email dry-run — Graph is not sending yet).", "success");
				} else {
					flash("Invitations sent from quotes@gousis.com.", "success");
				}
			})
			.catch(function (err) {
				flash(err.message || String(err), "error");
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	function syncMailbox() {
		var btn = $("usis-rfp-sync");
		if (btn) btn.disabled = true;
		fetchJson("/api/v1/rfps/mailbox/sync", { method: "POST", headers: { Accept: "application/json" } })
			.then(function (d) {
				var item = d.item || {};
				flash(
					"Synced " +
						(item.mailbox || "quotes@gousis.com") +
						": " +
						(item.updated || 0) +
						" updated, " +
						(item.created || 0) +
						" new, " +
						(item.unmatched || 0) +
						" unmatched.",
					"success"
				);
				return load();
			})
			.catch(function (err) {
				flash(err.message || String(err), "error");
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		state.id = new URLSearchParams(window.location.search).get("id");
		if (!state.id) {
			flash("Missing ?id= rfp uuid", "error");
			return;
		}
		bindQuoteDrop();
		loadCostCodes().then(function () {
			return load();
		}).catch(function (err) {
			flash(err.message || String(err), "error");
		});
		document.querySelectorAll("input[name='usis-rfp-source']").forEach(function (el) {
			el.addEventListener("change", function () {
				applySourceUi();
				if (el.value === "takeoff") loadTakeoff();
				saveDraft();
			});
		});
		var search = $("usis-rfp-vendor-search");
		if (search) {
			search.addEventListener("input", function () {
				clearTimeout(state.searchTimer);
				var q = search.value.trim();
				if (!q) {
					hideVendorResults();
					return;
				}
				state.searchTimer = setTimeout(function () {
					searchVendors(q);
				}, 250);
			});
			search.addEventListener("keydown", function (ev) {
				if (ev.key === "Escape") hideVendorResults();
			});
			document.addEventListener("mousedown", function (ev) {
				var wrap = $("usis-rfp-vendor-search-wrap");
				if (wrap && !wrap.contains(ev.target)) hideVendorResults();
			});
		}
		var addVendor = $("usis-rfp-add-vendor");
		if (addVendor) addVendor.addEventListener("click", openVendorModal);
		var saveVendor = $("usis-rfp-vendor-save");
		if (saveVendor) saveVendor.addEventListener("click", saveNewVendor);
		var send = $("usis-rfp-send");
		if (send) send.addEventListener("click", function () {
			sendInvites(false);
		});
		var sendSel = $("usis-rfp-send-selected");
		if (sendSel) sendSel.addEventListener("click", function () {
			sendInvites(true);
		});
		var sync = $("usis-rfp-sync");
		if (sync) sync.addEventListener("click", syncMailbox);
		[$("usis-rfp-save"), $("usis-rfp-save-2")].forEach(function (btn) {
			if (btn) btn.addEventListener("click", saveDraft);
		});
		var addLine = $("usis-rfp-add-line");
		if (addLine) {
			addLine.addEventListener("click", function () {
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/line-items", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ description: "New item", quantity: 1, unit: "EA" }),
				}).then(load);
			});
		}
		var est = $("usis-rfp-estimate");
		if (est) est.addEventListener("change", function () {
			loadTakeoff(est.value);
		});
		var filter = $("usis-rfp-trade-filter");
		if (filter) filter.addEventListener("input", renderTakeoff);
		var all = $("usis-rfp-takeoff-all");
		if (all) {
			all.addEventListener("change", function () {
				document.querySelectorAll("[data-tl]").forEach(function (cb) {
					cb.checked = all.checked;
				});
			});
		}
		var rem = $("usis-rfp-select-remaining");
		if (rem) {
			rem.addEventListener("click", function () {
				document.querySelectorAll("[data-tl]").forEach(function (cb) {
					cb.checked = cb.getAttribute("data-remaining") === "1";
				});
			});
		}
		var attach = $("usis-rfp-attach");
		if (attach) {
			attach.addEventListener("click", function () {
				var ids = [];
				document.querySelectorAll("[data-tl]:checked").forEach(function (cb) {
					ids.push(cb.getAttribute("data-tl"));
				});
				var eid = ($("usis-rfp-estimate") || {}).value;
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/attach-takeoff", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ estimate_id: eid, takeoff_line_ids: ids }),
				}).then(function (d) {
					var a = d.attach || {};
					var banner = $("usis-rfp-takeoff-banner");
					if (banner) {
						banner.classList.remove("d-none");
						banner.textContent =
							(a.attached || 0) +
							" lines attached from Estimate " +
							(a.estimate_name || "") +
							". Internal pricing is not sent to vendors.";
					}
					return load();
				});
			});
		}
		var refresh = $("usis-rfp-refresh-takeoff");
		if (refresh) {
			refresh.addEventListener("click", function () {
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/refresh-takeoff", { method: "POST" }).then(load);
			});
		}
		var arch = $("usis-rfp-draw-arch");
		if (arch) {
			arch.addEventListener("click", function () {
				(state.drawCandidates || []).forEach(function (d, i) {
					var disc = (d.discipline || "").toLowerCase();
					var title = (d.sheet_title || "").toLowerCase();
					var hit = /arch|finish|interior|a\d|a-/.test(disc + " " + title);
					var box = document.querySelector("[data-draw='" + i + "']");
					if (box && hit) box.checked = true;
				});
			});
		}
		var previewBtn = $("usis-rfp-email-preview");
		if (previewBtn) {
			previewBtn.addEventListener("click", function (ev) {
				ev.preventDefault();
				preview().then(function () {
					var modalEl = $("usis-rfp-email-modal");
					if (modalEl && window.bootstrap && window.bootstrap.Modal) {
						window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
					}
				});
			});
		}
		var clone = $("usis-rfp-clone");
		if (clone) {
			clone.addEventListener("click", function () {
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/clone", { method: "POST" }).then(function (d) {
					var nid = d.item && d.item.id;
					if (nid) window.location.href = "usis-rfp-detail.html?id=" + encodeURIComponent(nid);
				});
			});
		}
	});
})();
