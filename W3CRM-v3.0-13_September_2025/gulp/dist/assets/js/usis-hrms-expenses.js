(function () {
	"use strict";
	var X = window.USISHrmsExpense;
	if (!X) return;

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-hrms-exp-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function loadList() {
		setStatus("Loading…");
		X.apiFetch("/api/v1/hrms/expense-reports")
			.then(function (data) {
				var items = data.items || [];
				var tb = document.getElementById("usis-hrms-exp-body");
				if (!tb) return;
				if (!items.length) {
					tb.innerHTML = '<tr><td colspan="5" class="text-muted small py-3">No expense reports yet. Click New report to start.</td></tr>';
				} else {
					tb.innerHTML = items
						.map(function (row) {
							return (
								"<tr><td>" +
								X.esc(row.title) +
								"</td><td>" +
								X.statusBadge(row.status) +
								'</td><td class="text-end">' +
								X.fmtMoney(row.total_amount, row.currency) +
								"</td><td>" +
								X.esc(row.submitted_at ? row.submitted_at.slice(0, 10) : "—") +
								'</td><td class="text-end"><a class="btn btn-sm btn-outline-primary py-0" href="usis-hrms-expense-detail.html?id=' +
								encodeURIComponent(row.id) +
								'">Open</a></td></tr>'
							);
						})
						.join("");
				}
				setStatus(items.length + " report(s).");
			})
			.catch(function (err) {
				setStatus(err.message || String(err), true);
			});
	}

	function createReport() {
		var title = window.prompt("Report title (e.g. March 2026 field expenses):");
		if (!title || !String(title).trim()) return;
		X.apiFetch("/api/v1/hrms/expense-reports", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ title: String(title).trim() }),
		}).then(function (data) {
			var id = data.item && data.item.id;
			if (id) window.location.href = "usis-hrms-expense-detail.html?id=" + encodeURIComponent(id);
			else loadList();
		}).catch(function (err) {
			setStatus(err.message || String(err), true);
		});
	}

	function wire() {
		var btn = document.getElementById("usis-hrms-exp-new");
		if (btn) btn.addEventListener("click", createReport);
		loadList();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
