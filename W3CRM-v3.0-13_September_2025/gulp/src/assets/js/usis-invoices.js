(function () {
	"use strict";
	var X = window.USISInvoices;
	if (!X) return;

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-ap-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function currentFilter() {
		var sel = document.getElementById("usis-ap-filter");
		return sel && sel.value ? sel.value : "";
	}

	function loadMailbox() {
		X.apiFetch("/api/v1/ap/mailbox")
			.then(function (data) {
				var item = data.item || {};
				var el = document.getElementById("usis-ap-mailbox");
				if (!el) return;
				el.textContent = item.mailbox
					? item.mailbox + (item.graph_configured ? " — mailbox connected" : " — mailbox not connected yet; log invoices manually or connect Microsoft Graph")
					: "";
			})
			.catch(function () {});
	}

	function loadList() {
		setStatus("Loading…");
		var status = currentFilter();
		var q = status ? "?status=" + encodeURIComponent(status) : "";
		X.apiFetch("/api/v1/ap/invoices" + q)
			.then(function (data) {
				var items = data.items || [];
				var tb = document.getElementById("usis-ap-body");
				if (!tb) return;
				if (!items.length) {
					tb.innerHTML =
						'<tr><td colspan="7" class="text-muted small py-3">No invoices in this view. Sync the mailbox or log one manually.</td></tr>';
				} else {
					tb.innerHTML = items
						.map(function (row) {
							var vendor = row.vendor_name || row.from_name || row.from_email || "—";
							var job = row.project_number || row.project_name || "Unassigned";
							return (
								"<tr><td>" +
								X.statusBadge(row.status) +
								"</td><td>" +
								X.esc(vendor) +
								"</td><td>" +
								X.esc(row.invoice_number || "—") +
								"</td><td>" +
								X.esc(job) +
								'</td><td class="text-end">' +
								X.fmtMoney(row.amount, row.currency) +
								"</td><td>" +
								X.esc((row.received_at || row.created_at || "").slice(0, 10) || "—") +
								'</td><td class="text-end"><a class="btn btn-sm btn-outline-primary py-0" href="usis-invoice-detail.html?id=' +
								encodeURIComponent(row.id) +
								'">Open</a></td></tr>'
							);
						})
						.join("");
				}
				setStatus(items.length + " invoice(s).");
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	function syncMailbox() {
		setStatus("Reading invoices@ mailbox…");
		X.apiFetch("/api/v1/ap/mailbox/sync", { method: "POST" })
			.then(function (data) {
				var item = data.item || {};
				setStatus("Synced " + (item.created || 0) + " new invoice(s); skipped " + (item.skipped || 0) + ".");
				loadList();
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	function createManual() {
		X.apiFetch("/api/v1/ap/invoices", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ source: "manual" }),
		})
			.then(function (data) {
				var id = data.item && data.item.id;
				if (id) window.location.href = "usis-invoice-detail.html?id=" + encodeURIComponent(id);
				else loadList();
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	function wire() {
		var syncBtn = document.getElementById("usis-ap-sync");
		var newBtn = document.getElementById("usis-ap-new");
		var filter = document.getElementById("usis-ap-filter");
		if (syncBtn) syncBtn.addEventListener("click", syncMailbox);
		if (newBtn) newBtn.addEventListener("click", createManual);
		if (filter) filter.addEventListener("change", loadList);
		loadMailbox();
		loadList();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
