(function () {
	"use strict";
	var X = window.USISHrmsExpense;
	if (!X) return;

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-hrms-expa-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function renderLines(lines) {
		if (!lines || !lines.length) return '<p class="small text-muted mb-0">No lines.</p>';
		return (
			'<ul class="list-unstyled small mb-0">' +
			lines
				.map(function (ln) {
					return (
						"<li>" +
						X.esc(ln.spent_at) +
						" · " +
						X.fmtMoney(ln.amount, ln.currency) +
						" · " +
						X.esc(ln.category) +
						" · " +
						X.esc(ln.project_name || "") +
						(ln.receipt_url
							? ' · <a href="' +
							  X.esc(X.apiBase() + ln.receipt_url) +
							  '" target="_blank" rel="noopener">Receipt</a>'
							: "") +
						"</li>"
					);
				})
				.join("") +
			"</ul>"
		);
	}

	function loadQueue() {
		setStatus("Loading…");
		X.apiFetch("/api/v1/hrms/expense-reports/approvals")
			.then(function (data) {
				var items = data.items || [];
				var root = document.getElementById("usis-hrms-expa-list");
				if (!root) return;
				if (!items.length) {
					root.innerHTML = '<div class="alert alert-light border">No reports awaiting approval.</div>';
				} else {
					root.innerHTML = items
						.map(function (r) {
							return (
								'<div class="card border-0 shadow-sm mb-3" data-report-id="' +
								X.esc(r.id) +
								'"><div class="card-body"><div class="d-flex flex-wrap justify-content-between gap-2 mb-2">' +
								"<div><h6 class=\"mb-1\">" +
								X.esc(r.title) +
								"</h6><p class="small text-muted mb-0">" +
								X.esc(r.employee_name || r.employee_email || "") +
								" · " +
								X.fmtMoney(r.total_amount, r.currency) +
								"</p></div>" +
								'<div class="d-flex gap-2">' +
								'<button type="button" class="btn btn-sm btn-success usis-hrms-expa-approve">Approve</button>' +
								'<button type="button" class="btn btn-sm btn-outline-danger usis-hrms-expa-reject">Reject</button>' +
								"</div></div>" +
								renderLines(r.lines) +
								"</div></div>"
							);
						})
						.join("");
					wireButtons();
				}
				setStatus(items.length + " pending.");
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	function wireButtons() {
		document.querySelectorAll(".usis-hrms-expa-approve").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var card = btn.closest("[data-report-id]");
				var id = card && card.getAttribute("data-report-id");
				if (!id) return;
				X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(id) + "/approve", { method: "POST" })
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Approved.");
						loadQueue();
					})
					.catch(function (e) {
						setStatus(e.message || String(e), true);
					});
			});
		});
		document.querySelectorAll(".usis-hrms-expa-reject").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var card = btn.closest("[data-report-id]");
				var id = card && card.getAttribute("data-report-id");
				if (!id) return;
				var reason = window.prompt("Rejection reason (required):");
				if (!reason || !String(reason).trim()) return;
				X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(id) + "/reject", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ rejection_reason: String(reason).trim() }),
				})
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Rejected.");
						loadQueue();
					})
					.catch(function (e) {
						setStatus(e.message || String(e), true);
					});
			});
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", loadQueue);
	else loadQueue();
})();
