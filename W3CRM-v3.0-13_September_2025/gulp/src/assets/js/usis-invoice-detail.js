(function () {
	"use strict";
	var X = window.USISInvoices;
	if (!X) return;

	function invoiceId() {
		var q = new URLSearchParams(window.location.search);
		return (q.get("id") || "").trim();
	}

	function showErr(msg) {
		var el = document.getElementById("usis-apd-err");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function val(id) {
		var el = document.getElementById(id);
		return el ? String(el.value || "").trim() : "";
	}

	function setVal(id, value) {
		var el = document.getElementById(id);
		if (el) el.value = value == null ? "" : String(value);
	}

	function payload() {
		return {
			vendor_company_id: val("usis-apd-vendor") || null,
			project_id: val("usis-apd-project") || null,
			commitment_id: val("usis-apd-commitment") || null,
			invoice_number: val("usis-apd-number") || null,
			invoice_date: val("usis-apd-date") || null,
			due_date: val("usis-apd-due") || null,
			amount: val("usis-apd-amount") || null,
			po_number: val("usis-apd-po") || null,
			notes: val("usis-apd-notes") || null,
			from_email: val("usis-apd-from-email") || null,
			from_name: val("usis-apd-from-name") || null,
			subject: val("usis-apd-subject") || null,
		};
	}

	function setHint(item) {
		var el = document.getElementById("usis-apd-hint");
		if (!el) return;
		if (item.status === "received") el.textContent = "Assign this invoice to a job, then submit it for payment approval.";
		else if (item.status === "routed") el.textContent = "Routed to a job. Review the amount and submit for payment approval.";
		else if (item.status === "pending_approval") el.textContent = "Waiting for payment approval.";
		else if (item.status === "approved") el.textContent = "Approved for payment. Accounting can mark it paid.";
		else if (item.status === "rejected") el.textContent = "Rejected — update the invoice and resubmit.";
		else if (item.status === "paid") el.textContent = "Paid" + (item.payment_ref ? " · " + item.payment_ref : "") + ".";
		else el.textContent = "";
	}

	function renderFiles(item) {
		var wrap = document.getElementById("usis-apd-files");
		if (!wrap) return;
		var files = item.files || [];
		if (!files.length) {
			wrap.innerHTML = '<p class="text-muted small mb-0">No attachments yet.</p>';
			return;
		}
		wrap.innerHTML = files
			.map(function (f) {
				return (
					'<a class="d-block small mb-1" target="_blank" rel="noopener" href="' +
					X.apiBase() +
					f.url +
					'">' +
					X.esc(f.original_filename || "Attachment") +
					"</a>"
				);
			})
			.join("");
	}

	function renderEvents(item) {
		var wrap = document.getElementById("usis-apd-events");
		if (!wrap) return;
		var events = item.events || [];
		if (!events.length) {
			wrap.innerHTML = '<p class="text-muted small mb-0">No activity yet.</p>';
			return;
		}
		wrap.innerHTML = events
			.map(function (ev) {
				return (
					'<div class="small mb-2"><strong>' +
					X.esc((ev.action || "").replace(/_/g, " ")) +
					"</strong> · " +
					X.esc((ev.created_at || "").replace("T", " ").slice(0, 16)) +
					"</div>"
				);
			})
			.join("");
	}

	function setActions(item) {
		var editable = item.status === "received" || item.status === "routed" || item.status === "rejected";
		["usis-apd-save", "usis-apd-file", "usis-apd-upload"].forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.disabled = !editable;
		});
		var submit = document.getElementById("usis-apd-submit");
		var approve = document.getElementById("usis-apd-approve");
		var reject = document.getElementById("usis-apd-reject");
		var paid = document.getElementById("usis-apd-paid");
		var voidBtn = document.getElementById("usis-apd-void");
		if (submit) submit.classList.toggle("d-none", !(item.status === "received" || item.status === "routed" || item.status === "rejected"));
		if (approve) approve.classList.toggle("d-none", item.status !== "pending_approval");
		if (reject) reject.classList.toggle("d-none", item.status !== "pending_approval");
		if (paid) paid.classList.toggle("d-none", item.status !== "approved");
		if (voidBtn) voidBtn.classList.toggle("d-none", item.status === "paid" || item.status === "void");
	}

	function applyItem(item) {
		document.getElementById("usis-apd-title").textContent = item.subject || item.invoice_number || "Vendor invoice";
		document.getElementById("usis-apd-status-badge").innerHTML = X.statusBadge(item.status);
		document.getElementById("usis-apd-total").textContent = X.fmtMoney(item.amount, item.currency);
		setVal("usis-apd-number", item.invoice_number);
		setVal("usis-apd-date", item.invoice_date);
		setVal("usis-apd-due", item.due_date);
		setVal("usis-apd-amount", item.amount);
		setVal("usis-apd-po", item.po_number);
		setVal("usis-apd-notes", item.notes);
		setVal("usis-apd-from-email", item.from_email);
		setVal("usis-apd-from-name", item.from_name);
		setVal("usis-apd-subject", item.subject);
		var preview = document.getElementById("usis-apd-preview");
		if (preview) preview.textContent = item.body_preview || "—";
		setHint(item);
		setActions(item);
		renderFiles(item);
		renderEvents(item);
		var rejectNote = document.getElementById("usis-apd-reject-note");
		if (rejectNote) {
			if (item.rejection_reason) {
				rejectNote.textContent = "Rejected: " + item.rejection_reason;
				rejectNote.classList.remove("d-none");
			} else {
				rejectNote.classList.add("d-none");
			}
		}
	}

	function loadLookups(item) {
		return Promise.all([
			X.apiFetch("/api/v1/ap/lookups/vendors"),
			X.apiFetch("/api/v1/ap/lookups/projects"),
			X.apiFetch(
				"/api/v1/ap/lookups/commitments" +
					(item.project_id ? "?project_id=" + encodeURIComponent(item.project_id) : "") +
					(item.vendor_company_id
						? (item.project_id ? "&" : "?") + "vendor_company_id=" + encodeURIComponent(item.vendor_company_id)
						: "")
			),
		]).then(function (parts) {
			X.fillSelect(document.getElementById("usis-apd-vendor"), parts[0].items || [], item.vendor_company_id, "Select vendor");
			X.fillSelect(document.getElementById("usis-apd-project"), parts[1].items || [], item.project_id, "Assign to job");
			X.fillSelect(document.getElementById("usis-apd-commitment"), parts[2].items || [], item.commitment_id, "Optional PO / subcontract");
		});
	}

	function load() {
		var id = invoiceId();
		if (!id) {
			showErr("Missing invoice id.");
			return Promise.resolve();
		}
		showErr("");
		return X.apiFetch("/api/v1/ap/invoices/" + encodeURIComponent(id))
			.then(function (data) {
				var item = data.item || {};
				applyItem(item);
				return loadLookups(item);
			})
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function save() {
		var id = invoiceId();
		X.apiFetch("/api/v1/ap/invoices/" + encodeURIComponent(id), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload()),
		})
			.then(load)
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function post(path, body) {
		var id = invoiceId();
		return X.apiFetch("/api/v1/ap/invoices/" + encodeURIComponent(id) + path, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body || {}),
		}).then(load);
	}

	function upload() {
		var id = invoiceId();
		var input = document.getElementById("usis-apd-file");
		if (!input || !input.files || !input.files[0]) {
			showErr("Choose a file first.");
			return;
		}
		var fd = new FormData();
		fd.append("file", input.files[0]);
		var headers = X.actorHeaders();
		fetch(X.apiBase() + "/api/v1/ap/invoices/" + encodeURIComponent(id) + "/files", {
			method: "POST",
			credentials: "include",
			headers: headers,
			body: fd,
		})
			.then(function (r) {
				return r.json().then(function (body) {
					if (!r.ok) throw new Error((body && body.error) || "Upload failed");
					return body;
				});
			})
			.then(load)
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function wire() {
		var saveBtn = document.getElementById("usis-apd-save");
		var submitBtn = document.getElementById("usis-apd-submit");
		var approveBtn = document.getElementById("usis-apd-approve");
		var rejectBtn = document.getElementById("usis-apd-reject");
		var paidBtn = document.getElementById("usis-apd-paid");
		var voidBtn = document.getElementById("usis-apd-void");
		var uploadBtn = document.getElementById("usis-apd-upload");
		if (saveBtn) saveBtn.addEventListener("click", save);
		if (submitBtn) submitBtn.addEventListener("click", function () { post("/submit").catch(function (err) { showErr(err.message || String(err)); }); });
		if (approveBtn) approveBtn.addEventListener("click", function () { post("/approve").catch(function (err) { showErr(err.message || String(err)); }); });
		if (rejectBtn)
			rejectBtn.addEventListener("click", function () {
				var reason = window.prompt("Reason for rejection:");
				if (!reason || !reason.trim()) return;
				post("/reject", { reason: reason.trim() }).catch(function (err) { showErr(err.message || String(err)); });
			});
		if (paidBtn)
			paidBtn.addEventListener("click", function () {
				var ref = window.prompt("Payment reference (check / ACH number), optional:") || "";
				post("/mark-paid", { payment_ref: ref.trim() }).catch(function (err) { showErr(err.message || String(err)); });
			});
		if (voidBtn)
			voidBtn.addEventListener("click", function () {
				if (!window.confirm("Void this invoice?")) return;
				post("/void", {}).catch(function (err) { showErr(err.message || String(err)); });
			});
		if (uploadBtn) uploadBtn.addEventListener("click", upload);
		load();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
