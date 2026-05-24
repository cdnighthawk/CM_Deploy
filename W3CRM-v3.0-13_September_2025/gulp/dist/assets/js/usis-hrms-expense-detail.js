(function () {
	"use strict";
	var X = window.USISHrmsExpense;
	if (!X) return;

	var state = { reportId: "", report: null, categories: [], projects: [] };

	function reportIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && String(id).trim() ? String(id).trim() : "";
	}

	function showErr(msg) {
		var el = document.getElementById("usis-hrms-expd-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else el.classList.add("d-none");
	}

	function editable() {
		var s = (state.report && state.report.status) || "";
		return s === "draft" || s === "rejected";
	}

	function loadMeta() {
		return Promise.all([
			X.apiFetch("/api/v1/hrms/expense-categories"),
			X.apiFetch("/api/v1/hrms/expense-projects"),
		]).then(function (res) {
			state.categories = (res[0].items || []);
			state.projects = (res[1].items || []);
			var catSel = document.getElementById("usis-hrms-expd-category");
			if (catSel) {
				catSel.innerHTML = state.categories
					.map(function (c) {
						return '<option value="' + X.esc(c.code) + '">' + X.esc(c.label) + "</option>";
					})
					.join("");
			}
			var projSel = document.getElementById("usis-hrms-expd-project");
			if (projSel) {
				projSel.innerHTML =
					'<option value="">Select project…</option>' +
					state.projects
						.map(function (p) {
							var label = (p.number ? p.number + " — " : "") + (p.name || "");
							return '<option value="' + X.esc(p.id) + '">' + X.esc(label) + "</option>";
						})
						.join("");
			}
		});
	}

	function renderReport(r) {
		state.report = r;
		document.getElementById("usis-hrms-expd-title").textContent = r.title || "Expense report";
		document.getElementById("usis-hrms-expd-status-badge").innerHTML = X.statusBadge(r.status);
		document.getElementById("usis-hrms-expd-total").textContent = X.fmtMoney(r.total_amount, r.currency);
		var reject = document.getElementById("usis-hrms-expd-reject");
		if (reject) {
			if (r.status === "rejected" && r.rejection_reason) {
				reject.textContent = "Rejected: " + r.rejection_reason;
				reject.classList.remove("d-none");
			} else reject.classList.add("d-none");
		}
		var addCard = document.getElementById("usis-hrms-expd-add-card");
		if (addCard) addCard.classList.toggle("d-none", !editable());
		var hint = document.getElementById("usis-hrms-expd-hint");
		if (hint) {
			if (editable()) hint.textContent = "Each line requires a project and receipt before you submit.";
			else if (r.status === "submitted") hint.textContent = "Submitted — awaiting manager approval.";
			else if (r.status === "approved") hint.textContent = "Approved — finance will export and reimburse.";
			else if (r.status === "reimbursed") hint.textContent = "Reimbursed.";
			else hint.textContent = "";
		}
		renderLines(r.lines || []);
		renderActions(r);
	}

	function renderLines(lines) {
		var tb = document.getElementById("usis-hrms-expd-lines");
		if (!tb) return;
		if (!lines.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted small py-3">No lines yet.</td></tr>';
			return;
		}
		tb.innerHTML = lines
			.map(function (ln) {
				var proj = ln.project_number ? ln.project_number + " — " : "";
				proj += ln.project_name || ln.project_id || "—";
				var receiptCell = "—";
				if (ln.receipt_url) {
					var url = ln.receipt_url.indexOf("http") === 0 ? ln.receipt_url : X.apiBase() + ln.receipt_url;
					receiptCell = '<a href="' + X.esc(url) + '" target="_blank" rel="noopener">View</a>';
				}
				var uploadBtn = "";
				if (editable()) {
					uploadBtn =
						'<label class="btn btn-sm btn-outline-secondary py-0 mb-0 ms-1">' +
						"Upload" +
						'<input type="file" class="d-none usis-hrms-expd-receipt-input" data-line-id="' +
						X.esc(ln.id) +
						'" accept="image/*,.pdf">' +
						"</label>";
				}
				var delBtn = editable()
					? '<button type="button" class="btn btn-sm btn-outline-danger py-0 usis-hrms-expd-del-line" data-line-id="' +
					  X.esc(ln.id) +
					  '">Delete</button>'
					: "";
				return (
					"<tr><td>" +
					X.esc(ln.spent_at) +
					"</td><td>" +
					X.esc(proj) +
					"</td><td>" +
					X.esc(ln.category) +
					"</td><td>" +
					X.esc(ln.merchant || "—") +
					'</td><td class="text-end">' +
					X.fmtMoney(ln.amount, ln.currency) +
					"</td><td>" +
					receiptCell +
					uploadBtn +
					'</td><td class="text-end">' +
					delBtn +
					"</td></tr>"
				);
			})
			.join("");
		wireLineButtons();
	}

	function renderActions(r) {
		var root = document.getElementById("usis-hrms-expd-actions");
		if (!root) return;
		var html = "";
		if (editable()) {
			html +=
				'<button type="button" class="btn btn-primary btn-sm" id="usis-hrms-expd-submit">Submit for approval</button>' +
				'<button type="button" class="btn btn-outline-danger btn-sm" id="usis-hrms-expd-delete">Delete report</button>';
		}
		root.innerHTML = html;
		var submit = document.getElementById("usis-hrms-expd-submit");
		if (submit) {
			submit.addEventListener("click", function () {
				X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(state.reportId) + "/submit", {
					method: "POST",
				})
					.then(function (data) {
						renderReport(data.item);
						if (window.USISNotify) window.USISNotify.success("Submitted for approval.");
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		}
		var del = document.getElementById("usis-hrms-expd-delete");
		if (del) {
			del.addEventListener("click", function () {
				if (!window.confirm("Delete this expense report?")) return;
				X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(state.reportId), { method: "DELETE" })
					.then(function () {
						window.location.href = "usis-hrms-expenses.html";
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		}
	}

	function wireLineButtons() {
		document.querySelectorAll(".usis-hrms-expd-del-line").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var lineId = btn.getAttribute("data-line-id");
				X.apiFetch(
					"/api/v1/hrms/expense-reports/" +
						encodeURIComponent(state.reportId) +
						"/lines/" +
						encodeURIComponent(lineId),
					{ method: "DELETE" }
				)
					.then(function () {
						loadReport();
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		});
		document.querySelectorAll(".usis-hrms-expd-receipt-input").forEach(function (input) {
			input.addEventListener("change", function () {
				var file = input.files && input.files[0];
				if (!file) return;
				var lineId = input.getAttribute("data-line-id");
				var fd = new FormData();
				fd.append("file", file);
				fetch(
					X.apiBase() +
						"/api/v1/hrms/expense-reports/" +
						encodeURIComponent(state.reportId) +
						"/lines/" +
						encodeURIComponent(lineId) +
						"/receipt",
					{
						method: "POST",
						credentials: "include",
						headers: X.actorHeaders(),
						body: fd,
					}
				)
					.then(function (r) {
						return r.json().then(function (body) {
							if (!r.ok) throw new Error((body && body.error) || "Upload failed");
							return body;
						});
					})
					.then(function () {
						loadReport();
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		});
	}

	function addLine() {
		var spent = (document.getElementById("usis-hrms-expd-spent") || {}).value;
		var amount = (document.getElementById("usis-hrms-expd-amount") || {}).value;
		var category = (document.getElementById("usis-hrms-expd-category") || {}).value;
		var projectId = (document.getElementById("usis-hrms-expd-project") || {}).value;
		var merchant = (document.getElementById("usis-hrms-expd-merchant") || {}).value;
		var desc = (document.getElementById("usis-hrms-expd-desc") || {}).value;
		if (!projectId) {
			showErr("Select a project for this expense.");
			return;
		}
		showErr("");
		X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(state.reportId) + "/lines", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				spent_at: spent,
				amount: amount,
				category: category,
				project_id: projectId,
				merchant: merchant,
				description: desc,
			}),
		})
			.then(function () {
				loadReport();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function loadReport() {
		return X.apiFetch("/api/v1/hrms/expense-reports/" + encodeURIComponent(state.reportId)).then(function (data) {
			renderReport(data.item);
		});
	}

	function wire() {
		state.reportId = reportIdFromQuery();
		if (!state.reportId) {
			showErr("Missing report id (?id=).");
			return;
		}
		var addBtn = document.getElementById("usis-hrms-expd-add-line");
		if (addBtn) addBtn.addEventListener("click", addLine);
		loadMeta()
			.then(loadReport)
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
