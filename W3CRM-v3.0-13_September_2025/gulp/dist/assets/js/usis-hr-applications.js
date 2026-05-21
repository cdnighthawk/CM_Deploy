(function () {
	"use strict";

	var searchTimer = null;

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		if (host === "localhost" || host === "127.0.0.1") return (proto + "//" + host + ":5000").replace(/\/$/, "");
		return "";
	}

	function esc(s) {
		if (s == null) return "";
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	function fmtDate(iso) {
		if (!iso) return "—";
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(iso);
			return esc(d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }));
		} catch (e) {
			return esc(iso);
		}
	}

	function statusBadge(status) {
		var s = status || "in_progress";
		var cls = "bg-secondary";
		if (s === "submitted") cls = "bg-primary";
		if (s === "under_review") cls = "bg-info text-dark";
		if (s === "hired") cls = "bg-success";
		if (s === "rejected") cls = "bg-danger";
		return '<span class="badge ' + cls + '">' + esc(s.replace(/_/g, " ")) + "</span>";
	}

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-hr-apps-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function loadList() {
		var q = (document.getElementById("usis-hr-apps-search") || {}).value || "";
		var status = (document.getElementById("usis-hr-apps-status-filter") || {}).value || "";
		var params = new URLSearchParams();
		if (q.trim()) params.set("q", q.trim());
		if (status) params.set("hire_status", status);
		params.set("limit", "100");
		setStatus("Loading…");
		fetch(apiBase() + "/api/v1/hr/applications?" + params.toString(), {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				return r.json().then(function (data) {
					return { ok: r.ok, data: data };
				});
			})
			.then(function (res) {
				if (!res.ok) throw new Error((res.data && res.data.error) || "HTTP error");
				var items = res.data.items || [];
				var tb = document.getElementById("usis-hr-apps-body");
				if (!tb) return;
				if (!items.length) {
					tb.innerHTML = '<tr><td colspan="7" class="text-muted small py-3">No applications match these filters.</td></tr>';
				} else {
					tb.innerHTML = items
						.map(function (row) {
							return (
								"<tr>" +
								"<td>" +
								esc(row.name) +
								"</td><td>" +
								esc(row.email) +
								"</td><td>" +
								esc(row.position || "—") +
								"</td><td>" +
								fmtDate(row.submitted_for_review_at) +
								"</td><td>" +
								statusBadge(row.hire_status) +
								'</td><td class="text-end">' +
								esc(row.progress_percent != null ? row.progress_percent + "%" : "—") +
								'</td><td class="text-end"><a class="btn btn-sm btn-outline-primary py-0" href="usis-hr-application-detail.html?id=' +
								encodeURIComponent(row.user_id) +
								'">Review</a></td></tr>'
							);
						})
						.join("");
				}
				setStatus("Showing " + items.length + " of " + (res.data.total || items.length) + " application(s).");
			})
			.catch(function (err) {
				setStatus("Could not load applications: " + (err.message || err), true);
				var tb = document.getElementById("usis-hr-apps-body");
				if (tb) tb.innerHTML = '<tr><td colspan="7" class="text-danger small py-3">Load failed.</td></tr>';
			});
	}

	function wire() {
		var refresh = document.getElementById("usis-hr-apps-refresh");
		if (refresh) refresh.addEventListener("click", loadList);
		var filter = document.getElementById("usis-hr-apps-status-filter");
		if (filter) filter.addEventListener("change", loadList);
		var search = document.getElementById("usis-hr-apps-search");
		if (search) {
			search.addEventListener("input", function () {
				if (searchTimer) clearTimeout(searchTimer);
				searchTimer = setTimeout(loadList, 350);
			});
		}
		loadList();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
