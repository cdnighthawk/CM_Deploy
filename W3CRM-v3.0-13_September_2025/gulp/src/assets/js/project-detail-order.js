/**
 * Project detail — Buyout → Order board (order-by dates + supplier confirm).
 */
(function () {
	"use strict";

	var projectId = null;
	var bucket = "all";

	function projectIdFromQuery() {
		if (window.USISProjectContext && typeof window.USISProjectContext.projectIdFromQuery === "function") {
			return window.USISProjectContext.projectIdFromQuery();
		}
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim() || null;
	}
	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}
	function toastErr(msg) {
		if (window.USISNotify && window.USISNotify.error) window.USISNotify.error(msg);
	}
	function iso(val) {
		return val ? String(val).slice(0, 10) : "—";
	}
	function confirmClass(status) {
		if (status === "confirmed") return "badge text-bg-success";
		if (status === "overdue") return "badge text-bg-danger";
		if (status === "sent") return "badge text-bg-warning";
		return "badge text-bg-light";
	}
	function loadBoard() {
		if (!projectId) return;
		var loading = document.getElementById("usis-order-loading");
		var err = document.getElementById("usis-order-error");
		var tb = document.getElementById("usis-order-tbody");
		if (loading) loading.classList.remove("d-none");
		if (err) {
			err.textContent = "";
			err.classList.add("d-none");
		}
		window.USIS_API.fetchJson(
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/order-board?bucket=" + encodeURIComponent(bucket)
		)
			.then(function (data) {
				if (loading) loading.classList.add("d-none");
				if (!tb) return;
				tb.innerHTML = "";
				var items = data.items || [];
				if (!items.length) {
					tb.innerHTML = '<tr><td colspan="8" class="text-muted">No purchase orders in this filter.</td></tr>';
					return;
				}
				items.forEach(function (row) {
					var tr = document.createElement("tr");
					if (row.buy_late) tr.classList.add("table-warning");
					tr.innerHTML =
						"<td>" +
						esc(row.po_number || "—") +
						"</td><td>" +
						esc(row.vendor_name || "") +
						"</td><td>" +
						esc(row.schedule_title || "—") +
						"</td><td>" +
						esc(iso(row.needed_on_site_date)) +
						"</td><td>" +
						esc(row.lead_time_days != null ? String(row.lead_time_days) : "—") +
						"</td><td>" +
						esc(iso(row.order_by_date)) +
						"</td><td><span class=\"" +
						confirmClass(row.supplier_confirm_status) +
						'">' +
						esc(row.supplier_confirm_status || "none") +
						"</span></td>" +
						'<td class="text-end"><button type="button" class="btn btn-link btn-sm p-0 usis-order-open" data-id="' +
						esc(row.commitment_id) +
						'">Open</button></td>';
					tb.appendChild(tr);
				});
				tb.querySelectorAll(".usis-order-open").forEach(function (btn) {
					btn.addEventListener("click", function () {
						var cid = btn.getAttribute("data-id");
						if (window.usisOpenCommitmentEdit) window.usisOpenCommitmentEdit(cid);
					});
				});
			})
			.catch(function (e) {
				if (loading) loading.classList.add("d-none");
				if (err) {
					err.textContent = e.message || String(e);
					err.classList.remove("d-none");
				} else {
					toastErr(e.message || String(e));
				}
			});
	}
	function setBucket(next) {
		bucket = next || "all";
		document.querySelectorAll(".usis-order-filter").forEach(function (btn) {
			var on = btn.getAttribute("data-usis-order-bucket") === bucket;
			btn.classList.toggle("btn-primary", on);
			btn.classList.toggle("btn-outline-secondary", !on);
			btn.setAttribute("aria-pressed", on ? "true" : "false");
		});
		loadBoard();
	}
	function wire() {
		projectId = projectIdFromQuery();
		var refresh = document.getElementById("usis-order-refresh");
		if (refresh) refresh.addEventListener("click", loadBoard);
		document.querySelectorAll(".usis-order-filter").forEach(function (btn) {
			btn.addEventListener("click", function () {
				setBucket(btn.getAttribute("data-usis-order-bucket"));
			});
		});
		var orderTab = document.getElementById("proj-tab-order");
		if (orderTab) {
			orderTab.addEventListener("shown.bs.tab", loadBoard);
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
