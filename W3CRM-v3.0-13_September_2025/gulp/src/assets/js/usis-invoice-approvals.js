(function () {
	"use strict";
	var X = window.USISInvoices;
	if (!X) return;

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-apa-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function showErr(msg) {
		var el = document.getElementById("usis-apa-err");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function postAction(id, path, body) {
		return X.apiFetch("/api/v1/ap/invoices/" + encodeURIComponent(id) + path, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body || {}),
		});
	}

	function wireButtons() {
		document.querySelectorAll(".usis-apa-approve").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var card = btn.closest("[data-invoice-id]");
				var id = card && card.getAttribute("data-invoice-id");
				if (!id) return;
				btn.disabled = true;
				postAction(id, "/approve")
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Invoice approved for payment.");
						loadList();
					})
					.catch(function (err) {
						btn.disabled = false;
						showErr(err.message || String(err));
					});
			});
		});
		document.querySelectorAll(".usis-apa-reject").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var card = btn.closest("[data-invoice-id]");
				var id = card && card.getAttribute("data-invoice-id");
				if (!id) return;
				var reason = window.prompt("Reason for rejection:");
				if (!reason || !reason.trim()) return;
				btn.disabled = true;
				postAction(id, "/reject", { reason: reason.trim() })
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Invoice rejected.");
						loadList();
					})
					.catch(function (err) {
						btn.disabled = false;
						showErr(err.message || String(err));
					});
			});
		});
	}

	function loadList() {
		setStatus("Loading…");
		showErr("");
		X.apiFetch("/api/v1/ap/invoices/approvals")
			.then(function (data) {
				var items = data.items || [];
				var wrap = document.getElementById("usis-apa-list");
				if (!wrap) return;
				if (!items.length) {
					wrap.innerHTML =
						'<div class="alert alert-light border">' +
						"<p class=\"mb-2\">No invoices are waiting for payment approval.</p>" +
						"<p class=\"small text-muted mb-2\">To send one here: open the invoice, assign a job and amount, then click <strong>Submit for approval</strong>.</p>" +
						'<a class="btn btn-sm btn-primary" href="usis-invoices.html">Open invoices</a>' +
						"</div>";
				} else {
					wrap.innerHTML = items
						.map(function (row) {
							var actions = row.can_approve
								? '<button type="button" class="btn btn-sm btn-success usis-apa-approve">Approve</button>' +
								  '<button type="button" class="btn btn-sm btn-outline-danger usis-apa-reject">Reject</button>'
								: "";
							return (
								'<div class="card border-0 shadow-sm mb-3" data-invoice-id="' +
								X.esc(row.id) +
								'"><div class="card-body"><div class="d-flex flex-wrap justify-content-between align-items-start gap-2">' +
								'<div><div class="fw-semibold"><a href="usis-invoice-detail.html?id=' +
								encodeURIComponent(row.id) +
								'">' +
								X.esc(row.vendor_name || row.from_name || row.subject || "Invoice") +
								"</a></div><div class=\"small text-muted\">" +
								X.esc(row.project_number || row.project_name || "No job") +
								" · " +
								X.esc(row.invoice_number || "No invoice #") +
								" · " +
								X.fmtMoney(row.amount, row.currency) +
								(row.due_date ? " · due " + X.esc(row.due_date) : "") +
								"</div></div>" +
								'<div class="d-flex flex-wrap gap-2">' +
								actions +
								'<a class="btn btn-sm btn-outline-primary" href="usis-invoice-detail.html?id=' +
								encodeURIComponent(row.id) +
								'">Open</a></div></div></div></div>'
							);
						})
						.join("");
					wireButtons();
				}
				setStatus(items.length ? items.length + " waiting for approval." : "Approval queue is empty.");
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", loadList);
	else loadList();
})();
