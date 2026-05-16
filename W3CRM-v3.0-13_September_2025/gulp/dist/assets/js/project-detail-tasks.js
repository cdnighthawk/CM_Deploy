/**
 * Project detail — Tasks tab (W3CRM construction/task.html layout).
 * Uses the same ``/api/v1/projects/<id>/schedule-items`` rows as the Schedule tab.
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		items: [],
		fetched: false,
	};

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				if (s && new URL(s).origin === window.location.origin) {
					/* fall through */
				} else if (s) {
					return s;
				}
			} catch (e) {
				if (s) return s;
			}
		}
		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = { 3000: 1, 3001: 1, 3002: 1, 4173: 1, 5173: 1, 5174: 1, 5500: 1, 5501: 1, 8080: 1, 4200: 1, 4321: 1, 9630: 1, 1234: 1 };
		if (devPorts[port]) {
			return proto + "//" + host + ":5000";
		}
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") {
				return "";
			}
			return proto + "//" + host + ":5000";
		}
		var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
		if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
			return proto + "//" + host + ":5000";
		}
		if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
			return proto + "//" + host + ":5000";
		}
		return "";
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function projectIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = s;
		return d.innerHTML;
	}

	function escAttr(s) {
		if (s == null) return "";
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;");
	}

	function todayYmd() {
		var d = new Date();
		var y = d.getFullYear();
		var m = String(d.getMonth() + 1).padStart(2, "0");
		var day = String(d.getDate()).padStart(2, "0");
		return y + "-" + m + "-" + day;
	}

	function ymdSlice(iso) {
		if (!iso || typeof iso !== "string") return "";
		return iso.length >= 10 ? iso.slice(0, 10) : iso;
	}

	function inclusiveDayCount(startIso, endIso) {
		var a = ymdSlice(startIso);
		var b = ymdSlice(endIso);
		if (!a || !b) return null;
		var p1 = a.split("-");
		var p2 = b.split("-");
		var t1 = Date.UTC(parseInt(p1[0], 10), parseInt(p1[1], 10) - 1, parseInt(p1[2], 10));
		var t2 = Date.UTC(parseInt(p2[0], 10), parseInt(p2[1], 10) - 1, parseInt(p2[2], 10));
		if (isNaN(t1) || isNaN(t2)) return null;
		var diff = Math.round((t2 - t1) / 86400000) + 1;
		return diff > 0 ? diff : 1;
	}

	function statusBucket(it) {
		var t = todayYmd();
		var s = ymdSlice(it.start_date);
		var e = ymdSlice(it.end_date);
		if (e && e < t) return "completed";
		if (s && s > t) return "not_started";
		return "ongoing";
	}

	function statusLabel(bucket) {
		if (bucket === "completed") return "Completed";
		if (bucket === "not_started") return "Not started";
		return "Ongoing";
	}

	function statusBadgeClass(bucket) {
		if (bucket === "completed") return "bg-success";
		if (bucket === "not_started") return "bg-secondary";
		return "bg-primary";
	}

	function setTaskLoading(on) {
		document.querySelectorAll("[data-usis-task-loading]").forEach(function (el) {
			el.classList.toggle("d-none", !on);
		});
	}

	function setTaskError(msg) {
		document.querySelectorAll("[data-usis-task-error]").forEach(function (el) {
			if (msg) {
				el.textContent = msg;
				el.classList.remove("d-none");
			} else {
				el.classList.add("d-none");
			}
		});
	}

	function filteredItems() {
		var st = (document.getElementById("usis-task-filter-status") || {}).value || "all";
		var memRaw = (document.getElementById("usis-task-filter-member") || {}).value || "";
		var mem = memRaw.trim().toLowerCase();
		return state.items.filter(function (it) {
			if (st !== "all" && statusBucket(it) !== st) return false;
			if (mem) {
				var crew = (it.crew_label || "").toLowerCase();
				if (crew.indexOf(mem) === -1) return false;
			}
			return true;
		});
	}

	function renderTable() {
		var tb = document.getElementById("usis-task-tbody");
		if (!tb) return;
		var rows = filteredItems();
		if (!rows.length) {
			if (!state.items.length) {
				tb.innerHTML =
					'<tr><td colspan="10" class="text-muted small p-3">No tasks yet. Use <strong>+ Add task</strong> (same form as the Schedule tab) to create installation windows.</td></tr>';
			} else {
				tb.innerHTML =
					'<tr><td colspan="10" class="text-muted small p-3">No tasks match the filters. Clear filters or adjust status / assigned.</td></tr>';
			}
			return;
		}
		var html = [];
		for (var i = 0; i < rows.length; i++) {
			var it = rows[i];
			var bucket = statusBucket(it);
			var days = inclusiveDayCount(it.start_date, it.end_date);
			var dur = days != null ? days + (days === 1 ? " day" : " days") : "—";
			var prog =
				bucket === "completed"
					? '<span class="badge bg-success">100%</span>'
					: bucket === "not_started"
						? '<span class="badge bg-secondary">0%</span>'
						: '<span class="badge bg-primary">In progress</span>';
			html.push(
				"<tr>" +
					'<td class="text-center">' +
					(i + 1) +
					"</td>" +
					"<td>" +
					esc(it.title) +
					"</td>" +
					'<td class="text-center">' +
					esc(dur) +
					"</td>" +
					'<td class="text-center">' +
					esc(ymdSlice(it.start_date)) +
					"</td>" +
					'<td class="text-center">' +
					esc(ymdSlice(it.end_date)) +
					"</td>" +
					'<td class="text-center">' +
					prog +
					"</td>" +
					'<td class="text-center text-muted">—</td>' +
					'<td class="text-center">' +
					esc(it.crew_label || "—") +
					"</td>" +
					'<td class="text-center"><span class="badge ' +
					statusBadgeClass(bucket) +
					'">' +
					esc(statusLabel(bucket)) +
					"</span></td>" +
					'<td class="text-center">' +
					'<div class="dropdown custom-dropdown mb-0">' +
					'<button type="button" class="btn btn-sm btn-link p-0 text-body" data-bs-toggle="dropdown" aria-expanded="false">' +
					'<i class="fa-solid fa-ellipsis-vertical"></i>' +
					"</button>" +
					'<ul class="dropdown-menu dropdown-menu-end">' +
					'<li><button type="button" class="dropdown-item usis-task-row-edit" data-id="' +
					escAttr(it.id) +
					'">Edit</button></li>' +
					'<li><button type="button" class="dropdown-item text-danger usis-task-row-del" data-id="' +
					escAttr(it.id) +
					'">Delete</button></li>' +
					"</ul>" +
					"</div>" +
					"</td>" +
					"</tr>"
			);
		}
		tb.innerHTML = html.join("");
	}

	function loadTasks() {
		if (!state.projectId) return;
		setTaskError("");
		setTaskLoading(true);
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(state.projectId) + "/schedule-items";
		fetch(url, { headers: Object.assign({ Accept: "application/json" }, actorHeaders()) })
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				setTaskLoading(false);
				if (!res.ok) {
					setTaskError((res.body && res.body.error) || "Failed to load tasks (" + res.status + ").");
					return;
				}
				state.items = Array.isArray(res.body.items) ? res.body.items : [];
				state.fetched = true;
				renderTable();
			})
			.catch(function () {
				setTaskLoading(false);
				setTaskError("Network error loading tasks.");
			});
	}

	function itemById(id) {
		for (var i = 0; i < state.items.length; i++) {
			if (state.items[i].id === id) return state.items[i];
		}
		return null;
	}

	function openScheduleCreate() {
		var ui = window.USISProjectScheduleUi;
		if (ui && typeof ui.openCreateModal === "function") {
			ui.openCreateModal();
			var tEl = document.getElementById("usis-modal-schedule-item-title");
			if (tEl) tEl.textContent = "Add task / window";
		}
	}

	function openScheduleEdit(it) {
		var ui = window.USISProjectScheduleUi;
		if (ui && typeof ui.openEditItem === "function") {
			ui.openEditItem(it);
			var tEl = document.getElementById("usis-modal-schedule-item-title");
			if (tEl) tEl.textContent = "Edit task / window";
		}
	}

	function deleteItem(itemId) {
		if (!window.confirm("Delete this task (installation window)?")) return;
		var url =
			apiBase() +
			"/api/v1/projects/" +
			encodeURIComponent(state.projectId) +
			"/schedule-items/" +
			encodeURIComponent(itemId);
		fetch(url, {
			method: "DELETE",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					setTaskError((res.body && res.body.error) || "Delete failed.");
					return;
				}
				if (window.USISProjectScheduleUi && typeof window.USISProjectScheduleUi.reload === "function") {
					window.USISProjectScheduleUi.reload();
				} else {
					loadTasks();
				}
			})
			.catch(function () {
				setTaskError("Network error on delete.");
			});
	}

	function wire() {
		state.projectId = projectIdFromQuery();
		if (!state.projectId) return;

		var tab = document.getElementById("proj-tab-tasks");
		if (tab) {
			tab.addEventListener("shown.bs.tab", function () {
				if (!state.fetched) {
					loadTasks();
				} else {
					renderTable();
				}
			});
		}

		window.addEventListener("usis-project-schedule-changed", function () {
			if (!state.projectId) return;
			if (state.fetched) {
				loadTasks();
			}
		});

		var addBtn = document.getElementById("usis-task-btn-add");
		if (addBtn) {
			addBtn.addEventListener("click", openScheduleCreate);
		}

		var fs = document.getElementById("usis-task-filter-status");
		if (fs) fs.addEventListener("change", renderTable);
		var fm = document.getElementById("usis-task-filter-member");
		if (fm) fm.addEventListener("input", renderTable);

		var tb = document.getElementById("usis-task-tbody");
		if (tb) {
			tb.addEventListener("click", function (ev) {
				var ed = ev.target && ev.target.closest && ev.target.closest(".usis-task-row-edit");
				var del = ev.target && ev.target.closest && ev.target.closest(".usis-task-row-del");
				if (ed) {
					var id1 = ed.getAttribute("data-id");
					var it1 = itemById(id1);
					if (it1) openScheduleEdit(it1);
				} else if (del) {
					var id2 = del.getAttribute("data-id");
					if (id2) deleteItem(id2);
				}
			});
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
