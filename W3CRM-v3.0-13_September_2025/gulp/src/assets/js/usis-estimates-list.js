/**
 * Lead detail — Estimates list + create / copy modal.
 * GET/POST /api/v1/leads/<lead_id>/estimates
 */
(function () {
	"use strict";

	var Api = typeof window.USISEstimateApi !== "undefined" ? window.USISEstimateApi : null;
	var leadId = null;
	var estimates = [];
	var copyFromId = "";

	function leadIdFromUrl() {
		return new URLSearchParams(window.location.search).get("id");
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function money(n) {
		if (n == null || n === "" || isNaN(Number(n))) return "—";
		return (
			"$" +
			Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
		);
	}

	function statusBadge(status) {
		var s = String(status || "draft").toLowerCase();
		var cls = "bg-secondary";
		if (s === "submitted") cls = "bg-primary";
		else if (s === "awarded") cls = "bg-success";
		else if (s === "superseded") cls = "bg-warning text-dark";
		else if (s === "archived") cls = "bg-dark";
		else if (s === "draft") cls = "bg-light text-dark border";
		return '<span class="badge ' + cls + ' text-capitalize">' + esc(s) + "</span>";
	}

	function drawingSetName(row) {
		if (row.drawing_set && row.drawing_set.name) return row.drawing_set.name;
		return "";
	}

	function showListErr(msg) {
		var el = document.getElementById("usis-lead-estimates-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function showModalErr(msg) {
		var el = document.getElementById("usis-est-create-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function renderTable() {
		var tb = document.getElementById("usis-lead-estimates-tbody");
		if (!tb) return;
		if (!estimates.length) {
			tb.innerHTML =
				'<tr><td colspan="7" class="text-center text-muted py-4">No estimates yet. Create one to start takeoff and pricing.</td></tr>';
			return;
		}
		tb.innerHTML = estimates
			.map(function (row) {
				var href = Api.estimateDetailHref(row.id);
				var locked = row.estimate_locked_at
					? '<span title="Locked">&#128274;</span>'
					: "";
				return (
					"<tr>" +
					'<td class="fw-medium"><a class="link-primary text-decoration-none" href="' +
					esc(href) +
					'">' +
					esc(row.name || "—") +
					"</a></td>" +
					"<td>" +
					esc(row.gc_name || "—") +
					"</td>" +
					"<td>" +
					esc(drawingSetName(row) || "—") +
					"</td>" +
					"<td>" +
					statusBadge(row.status) +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					esc(money(row.total)) +
					"</td>" +
					'<td class="text-center">' +
					locked +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					'<a class="btn btn-sm btn-outline-primary me-1" href="' +
					esc(href) +
					'">Open</a>' +
					'<button type="button" class="btn btn-sm btn-outline-secondary usis-est-copy-btn" data-estimate-id="' +
					esc(row.id) +
					'">Copy</button>' +
					"</td></tr>"
				);
			})
			.join("");
	}

	function fillCopyDropdown(selectedId) {
		var sel = document.getElementById("usis-est-create-copy-from");
		if (!sel) return;
		sel.innerHTML = estimates
			.map(function (row) {
				var selAttr = String(row.id) === String(selectedId) ? " selected" : "";
				return (
					'<option value="' +
					esc(row.id) +
					'"' +
					selAttr +
					">" +
					esc(row.name || row.id) +
					"</option>"
				);
			})
			.join("");
		if (!estimates.length) {
			sel.innerHTML = '<option value="">No existing estimates</option>';
		}
	}

	function fillDrawingSets(items, selectedId) {
		var sel = document.getElementById("usis-est-create-drawing-set");
		if (!sel) return;
		var opts = '<option value="">— None —</option>';
		(items || []).forEach(function (row) {
			var selAttr = selectedId && String(row.id) === String(selectedId) ? " selected" : "";
			opts +=
				'<option value="' +
				esc(row.id) +
				'"' +
				selAttr +
				">" +
				esc(row.name || row.id) +
				"</option>";
		});
		sel.innerHTML = opts;
	}

	function setCopyEnabled(on) {
		var wrap = document.getElementById("usis-est-create-copy-wrap");
		var chk = document.getElementById("usis-est-create-copy");
		var sel = document.getElementById("usis-est-create-copy-from");
		if (chk) chk.checked = !!on;
		if (wrap) wrap.classList.toggle("d-none", !on);
		if (sel) sel.disabled = !on || !estimates.length;
	}

	function fillLeadPicker(items, selectedId) {
		var wrap = document.getElementById("usis-est-create-lead-wrap");
		var sel = document.getElementById("usis-est-create-lead");
		if (!wrap || !sel) return;
		var show = !leadId;
		wrap.classList.toggle("d-none", !show);
		if (!show) return;
		var opts = '<option value="">Select a lead…</option>';
		(items || []).forEach(function (row) {
			var id = row.id || row.external_id;
			if (!id) return;
			var label = (row.name || "Lead") + (row.number ? " · #" + row.number : "");
			var selAttr = selectedId && String(id) === String(selectedId) ? " selected" : "";
			opts += '<option value="' + esc(String(id)) + '"' + selAttr + ">" + esc(label) + "</option>";
		});
		sel.innerHTML = opts;
	}

	function resolveCreateLeadId() {
		if (leadId) return leadId;
		var sel = document.getElementById("usis-est-create-lead");
		return sel ? String(sel.value || "").trim() : "";
	}

	function openModal(opts) {
		opts = opts || {};
		if (Object.prototype.hasOwnProperty.call(opts, "leadId")) leadId = opts.leadId || null;
		if (Array.isArray(opts.estimates)) estimates = opts.estimates;
		copyFromId = opts.copyFromId || "";
		showModalErr("");
		var title = document.getElementById("usis-est-create-title");
		if (title) title.textContent = copyFromId ? "Copy estimate" : "New estimate";
		fillLeadPicker(opts.leadOptions || window.__USIS_ESTIMATE_LEADS || [], leadId);
		var nameEl = document.getElementById("usis-est-create-name");
		var gcEl = document.getElementById("usis-est-create-gc");
		var feeEl = document.getElementById("usis-est-create-fee");
		var src = null;
		if (copyFromId) {
			for (var i = 0; i < estimates.length; i++) {
				if (String(estimates[i].id) === String(copyFromId)) {
					src = estimates[i];
					break;
				}
			}
		}
		if (nameEl) {
			nameEl.value = src ? src.name + " copy" : "Original Estimate";
			nameEl.focus();
		}
		if (gcEl) gcEl.value = src && src.gc_name ? src.gc_name : "";
		if (feeEl) feeEl.value = src ? Api.feeToPercent(src.fee_percentage) : "";
		fillCopyDropdown(copyFromId);
		setCopyEnabled(!!copyFromId);
		var lid = resolveCreateLeadId();
		if (Api && lid) {
			Api.listForLead(lid)
				.then(function (data) {
					if (!estimates.length) estimates = data.items || [];
					fillCopyDropdown(copyFromId);
					if (!copyFromId) setCopyEnabled(false);
				})
				.catch(function () {});
			Api.listDrawingSets(lid)
				.then(function (data) {
					fillDrawingSets(data.items || [], src && src.drawing_set_id);
				})
				.catch(function () {
					fillDrawingSets([], src && src.drawing_set_id);
				});
		} else {
			fillDrawingSets([], src && src.drawing_set_id);
		}
		var modalEl = document.getElementById("usis-est-create-modal");
		if (modalEl && window.bootstrap) {
			window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
		}
	}

	function loadList() {
		if (!Api || !leadId) return;
		showListErr("");
		var tb = document.getElementById("usis-lead-estimates-tbody");
		if (tb) tb.innerHTML = '<tr><td colspan="7" class="text-muted">Loading estimates…</td></tr>';
		Api.listForLead(leadId)
			.then(function (data) {
				estimates = data.items || [];
				renderTable();
			})
			.catch(function (err) {
				estimates = [];
				renderTable();
				showListErr(err.message || String(err));
			});
	}

	function submitCreate() {
		if (!Api) return;
		var createLeadId = resolveCreateLeadId();
		if (!createLeadId) {
			showModalErr("Choose a lead for this estimate.");
			return;
		}
		var nameEl = document.getElementById("usis-est-create-name");
		var gcEl = document.getElementById("usis-est-create-gc");
		var feeEl = document.getElementById("usis-est-create-fee");
		var dsEl = document.getElementById("usis-est-create-drawing-set");
		var copyChk = document.getElementById("usis-est-create-copy");
		var copySel = document.getElementById("usis-est-create-copy-from");
		var name = nameEl ? String(nameEl.value || "").trim() : "";
		if (!name) {
			showModalErr("Name is required.");
			return;
		}
		var body = { name: name };
		var gc = gcEl ? String(gcEl.value || "").trim() : "";
		if (gc) body.gc_name = gc;
		var fee = feeEl ? Api.percentToFee(feeEl.value) : null;
		var copying = copyChk && copyChk.checked;
		if (fee != null && !copying) body.fee_percentage = fee;
		if (fee != null && copying) {
			var srcRow = null;
			var srcId = copySel ? String(copySel.value || "").trim() : copyFromId;
			for (var i = 0; i < estimates.length; i++) {
				if (String(estimates[i].id) === String(srcId)) {
					srcRow = estimates[i];
					break;
				}
			}
			var srcPct = srcRow ? String(Api.feeToPercent(srcRow.fee_percentage)) : "";
			if (String(feeEl.value || "").trim() !== srcPct) body.fee_percentage = fee;
		}
		var ds = dsEl ? String(dsEl.value || "").trim() : "";
		if (ds) body.drawing_set_id = ds;
		if (copying) {
			var copyId = copySel ? String(copySel.value || "").trim() : copyFromId;
			if (!copyId) {
				showModalErr("Choose an estimate to copy from.");
				return;
			}
			body.copy_from_estimate_id = copyId;
		}
		var btn = document.getElementById("usis-est-create-submit");
		if (btn) btn.disabled = true;
		showModalErr("");
		Api.createForLead(createLeadId, body)
			.then(function (data) {
				var item = data.item || {};
				if (!item.id) throw new Error("Create succeeded but no estimate id was returned.");
				window.location.href = Api.estimateDetailHref(item.id);
			})
			.catch(function (err) {
				showModalErr(err.message || String(err));
				if (btn) btn.disabled = false;
			});
	}

	function init() {
		if (!Api) return;
		var root = document.getElementById("usis-lead-estimates-root");
		if (root) {
			leadId = leadIdFromUrl();
			if (!leadId) showListErr("Open this page from the Leads table to manage estimates.");
		}
		var newBtn = document.getElementById("usis-lead-est-new");
		if (newBtn) newBtn.addEventListener("click", function () {
			openModal({});
		});
		var revBtn = document.getElementById("usis-lead-est-revision");
		if (revBtn) {
			revBtn.addEventListener("click", function () {
				var src = estimates[0] ? estimates[0].id : "";
				if (!src) {
					openModal({});
					return;
				}
				openModal({ copyFromId: src });
			});
		}
		var tb = document.getElementById("usis-lead-estimates-tbody");
		if (tb) {
			tb.addEventListener("click", function (e) {
				var btn = e.target.closest(".usis-est-copy-btn");
				if (!btn) return;
				openModal({ copyFromId: btn.getAttribute("data-estimate-id") });
			});
		}
		var copyChk = document.getElementById("usis-est-create-copy");
		if (copyChk) {
			copyChk.addEventListener("change", function () {
				setCopyEnabled(copyChk.checked);
			});
		}
		var submit = document.getElementById("usis-est-create-submit");
		if (submit) submit.addEventListener("click", submitCreate);
		var leadSel = document.getElementById("usis-est-create-lead");
		if (leadSel) {
			leadSel.addEventListener("change", function () {
				leadId = String(leadSel.value || "").trim() || null;
				if (leadId && Api) {
					Api.listForLead(leadId)
						.then(function (data) {
							estimates = data.items || [];
							fillCopyDropdown(copyFromId);
						})
						.catch(function () {
							estimates = [];
							fillCopyDropdown("");
						});
					Api.listDrawingSets(leadId)
						.then(function (data) {
							fillDrawingSets(data.items || [], null);
						})
						.catch(function () {
							fillDrawingSets([], null);
						});
				}
			});
		}
		if (root && leadId) loadList();
	}

	window.USISEstimateCreate = {
		open: function (id, opts) {
			opts = opts || {};
			opts.leadId = id || null;
			openModal(opts);
		},
	};

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
