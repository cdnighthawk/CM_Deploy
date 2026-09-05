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

	function refreshPendingCount() {
		X.apiFetch("/api/v1/ap/invoices/approvals")
			.then(function (data) {
				var n = (data.items || []).length;
				var el = document.getElementById("usis-ap-pending-count");
				if (el) el.textContent = String(n);
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
							var detailHref = "usis-invoice-detail.html?id=" + encodeURIComponent(row.id);
							var vendorCell =
								'<a href="' + detailHref + '">' + X.esc(vendor) + "</a>";
							if (row.subject && row.subject !== vendor) {
								vendorCell += '<div class="small text-muted">' + X.esc(row.subject) + "</div>";
							}
							if (row.reminder_count) {
								vendorCell +=
									'<div class="small text-info">Also received ' +
									X.esc(String(row.reminder_count)) +
									" more time" +
									(row.reminder_count === 1 ? "" : "s") +
									"</div>";
							}
							var extras = [];
							if (row.can_approve) {
								extras.push({
									label: "Approve",
									className: "usis-ap-approve",
									data: { "invoice-id": row.id },
								});
							}
							var actions =
								window.USISUi && window.USISUi.rowMenu
									? window.USISUi.rowMenu({
											id: row.id,
											editLabel: "Open",
											editHref: detailHref,
											createTarget: "#usis-ap-new",
											deleteClass: "usis-ap-del",
											extras: extras,
										})
									: '<a class="btn btn-sm btn-outline-primary py-0" href="' +
										detailHref +
										'">Open</a>';
							return (
								'<tr data-id="' +
								X.esc(row.id) +
								'"><td>' +
								X.statusBadge(row.status) +
								"</td><td>" +
								vendorCell +
								"</td><td>" +
								X.esc(row.invoice_number || "—") +
								"</td><td>" +
								X.esc(job) +
								'</td><td class="text-end">' +
								X.fmtMoney(row.amount, row.currency) +
								"</td><td>" +
								X.esc((row.received_at || row.created_at || "").slice(0, 10) || "—") +
								'</td><td class="text-end">' +
								actions +
								"</td></tr>"
							);
						})
						.join("");
				}
				setStatus(items.length + " invoice(s).");
				refreshPendingCount();
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
				if (item.busy) {
					setStatus("Mailbox sync is already running. New invoices will show up shortly.");
					loadList();
					return;
				}
				var extra = item.truncated ? " More mail remains; auto-sync will continue." : "";
				var errN = (item.errors && item.errors.length) || 0;
				var updated = item.updated || 0;
				var dups = item.duplicates || 0;
				setStatus(
					"Synced " +
						(item.created || 0) +
						" new invoice(s)" +
						(updated ? "; updated " + updated + " forwarded invoice(s)" : "") +
						(dups ? "; matched " + dups + " reminder(s) to invoices already on file" : "") +
						"; skipped " +
						(item.skipped || 0) +
						"." +
						extra,
					errN > 0 && !(item.created || 0) && !updated && !dups
				);
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

	function bindRowActions() {
		var tb = document.getElementById("usis-ap-body");
		if (!tb || tb.getAttribute("data-ap-actions")) return;
		tb.setAttribute("data-ap-actions", "1");
		tb.addEventListener(
			"click",
			function (ev) {
				var del = ev.target.closest(".usis-ap-del");
				if (del && tb.contains(del)) {
					ev.preventDefault();
					ev.stopPropagation();
					var delId =
						del.getAttribute("data-id") ||
						(del.closest("tr") && del.closest("tr").getAttribute("data-id"));
					if (!delId || !window.confirm("Delete this invoice?")) return;
					X.apiFetch("/api/v1/ap/invoices/" + encodeURIComponent(delId), { method: "DELETE" })
						.then(function () {
							loadList();
						})
						.catch(function (err) {
							setStatus(err.message || String(err), true);
						});
					return;
				}
				var appr = ev.target.closest(".usis-ap-approve");
				if (appr && tb.contains(appr)) {
					ev.preventDefault();
					ev.stopPropagation();
					var apprId = appr.getAttribute("data-invoice-id");
					if (!apprId) return;
					appr.disabled = true;
					X.apiFetch("/api/v1/ap/invoices/" + encodeURIComponent(apprId) + "/approve", {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: "{}",
					})
						.then(function () {
							loadList();
						})
						.catch(function (err) {
							appr.disabled = false;
							setStatus(err.message || String(err), true);
						});
				}
			},
			true
		);
	}

	function wire() {
		var syncBtn = document.getElementById("usis-ap-sync");
		var newBtn = document.getElementById("usis-ap-new");
		var filter = document.getElementById("usis-ap-filter");
		if (syncBtn) syncBtn.addEventListener("click", syncMailbox);
		if (newBtn) newBtn.addEventListener("click", createManual);
		if (filter) filter.addEventListener("change", loadList);
		bindRowActions();
		loadMailbox();
		loadList();
		setInterval(function () {
			loadMailbox();
			loadList();
		}, 5 * 60 * 1000);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
