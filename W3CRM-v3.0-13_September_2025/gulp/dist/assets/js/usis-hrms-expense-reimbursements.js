(function () {
	"use strict";
	var X = window.USISHrmsExpense;
	if (!X) return;

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-hrms-expr-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function loadQueue() {
		setStatus("Loading…");
		X.apiFetch("/api/v1/hrms/expense-reports/reimbursements")
			.then(function (data) {
				var items = data.items || [];
				var tb = document.getElementById("usis-hrms-expr-body");
				if (!tb) return;
				if (!items.length) {
					tb.innerHTML = '<tr><td colspan="6" class="text-muted small py-3">No approved expenses awaiting reimbursement.</td></tr>';
				} else {
					tb.innerHTML = items
						.map(function (r) {
							return (
								"<tr><td>" +
								X.esc(r.employee_name || r.employee_email) +
								"</td><td>" +
								X.esc(r.title) +
								'</td><td class="text-end">' +
								X.fmtMoney(r.total_amount, r.currency) +
								"</td><td>" +
								X.esc(r.decided_at ? r.decided_at.slice(0, 10) : "—") +
								"</td><td>" +
								X.esc(r.exported_at ? r.exported_at.slice(0, 10) : "—") +
								'</td><td class="text-end"><button type="button" class="btn btn-sm btn-success py-0 usis-hrms-expr-paid" data-id="' +
								X.esc(r.id) +
								'">Mark reimbursed</button></td></tr>'
							);
						})
						.join("");
					document.querySelectorAll(".usis-hrms-expr-paid").forEach(function (btn) {
						btn.addEventListener("click", function () {
							var id = btn.getAttribute("data-id");
							if (!id || !window.confirm("Mark this report as reimbursed?")) return;
							X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(id) + "/mark-reimbursed", {
								method: "POST",
							})
								.then(function () {
									if (window.USISNotify) window.USISNotify.success("Marked reimbursed.");
									loadQueue();
								})
								.catch(function (e) {
									setStatus(e.message || String(e), true);
								});
						});
					});
				}
				setStatus(items.length + " awaiting reimbursement.");
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	function wireExport() {
		var link = document.getElementById("usis-hrms-expr-export");
		if (!link) return;
		link.addEventListener("click", function (ev) {
			ev.preventDefault();
			var url = X.apiBase() + "/api/v1/hrms/expense-reports/export.csv";
			fetch(url, { credentials: "include", headers: X.actorHeaders() })
				.then(function (r) {
					if (!r.ok) throw new Error("Export failed (" + r.status + ")");
					return r.blob();
				})
				.then(function (blob) {
					var a = document.createElement("a");
					a.href = URL.createObjectURL(blob);
					a.download = "expense-reimbursements.csv";
					a.click();
					URL.revokeObjectURL(a.href);
					loadQueue();
				})
				.catch(function (e) {
					setStatus(e.message || String(e), true);
				});
		});
	}

	function wire() {
		wireExport();
		loadQueue();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
