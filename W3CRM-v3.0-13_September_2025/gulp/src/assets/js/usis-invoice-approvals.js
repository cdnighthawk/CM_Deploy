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

	function loadList() {
		setStatus("Loading…");
		X.apiFetch("/api/v1/ap/invoices/approvals")
			.then(function (data) {
				var items = data.items || [];
				var wrap = document.getElementById("usis-apa-list");
				if (!wrap) return;
				if (!items.length) {
					wrap.innerHTML = '<p class="text-muted small">No invoices waiting for payment approval.</p>';
				} else {
					wrap.innerHTML = items
						.map(function (row) {
							return (
								'<div class="card border-0 shadow-sm mb-2"><div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-2">' +
								"<div><div class=\"fw-semibold\">" +
								X.esc(row.vendor_name || row.from_name || row.subject || "Invoice") +
								"</div><div class=\"small text-muted\">" +
								X.esc(row.project_number || row.project_name || "No job") +
								" · " +
								X.esc(row.invoice_number || "No invoice #") +
								" · " +
								X.fmtMoney(row.amount, row.currency) +
								"</div></div>" +
								'<a class="btn btn-sm btn-primary" href="usis-invoice-detail.html?id=' +
								encodeURIComponent(row.id) +
								'">Review</a></div></div>'
							);
						})
						.join("");
				}
				setStatus(items.length + " pending.");
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", loadList);
	else loadList();
})();
