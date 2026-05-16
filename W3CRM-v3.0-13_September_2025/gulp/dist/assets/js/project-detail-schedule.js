/**
 * Active project — installation windows + FullCalendar (GET/POST/PATCH/DELETE schedule-items).
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		items: [],
		calendar: null,
		scheduleFetched: false,
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
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
			4173: 1,
			5173: 1,
			5174: 1,
			5500: 1,
			5501: 1,
			8080: 1,
			4200: 1,
			4321: 1,
			9630: 1,
			1234: 1,
		};
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

	function projectIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
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

	function setSchedLoading(on) {
		var els = document.querySelectorAll("[data-usis-sched-loading]");
		for (var i = 0; i < els.length; i++) {
			els[i].classList.toggle("d-none", !on);
		}
	}

	function setSchedError(msg) {
		var els = document.querySelectorAll("[data-usis-sched-error]");
		for (var i = 0; i < els.length; i++) {
			if (msg) {
				els[i].textContent = msg;
				els[i].classList.remove("d-none");
			} else {
				els[i].classList.add("d-none");
			}
		}
	}

	function toFcExclusiveEnd(isoInclusive) {
		if (!isoInclusive || isoInclusive.length < 10) return isoInclusive;
		var y = parseInt(isoInclusive.slice(0, 4), 10);
		var m = parseInt(isoInclusive.slice(5, 7), 10) - 1;
		var d = parseInt(isoInclusive.slice(8, 10), 10);
		var dt = new Date(y, m, d);
		dt.setDate(dt.getDate() + 1);
		var yy = dt.getFullYear();
		var mm = String(dt.getMonth() + 1).padStart(2, "0");
		var dd = String(dt.getDate()).padStart(2, "0");
		return yy + "-" + mm + "-" + dd;
	}

	function buildFcEvents(items) {
		return (items || []).map(function (it) {
			var t = it.title;
			if (it.crew_label) {
				t += " · " + it.crew_label;
			}
			return {
				id: it.id,
				title: t,
				start: it.start_date,
				end: toFcExclusiveEnd(it.end_date),
				allDay: true,
				classNames: ["text-white"],
				backgroundColor: "#0d6efd",
				borderColor: "#0d6efd",
			};
		});
	}

	function syncCalendarEvents() {
		if (!state.calendar) return;
		state.calendar.removeAllEvents();
		buildFcEvents(state.items).forEach(function (ev) {
			state.calendar.addEvent(ev);
		});
		if (state.items.length) {
			state.calendar.gotoDate(state.items[0].start_date);
		}
		state.calendar.updateSize();
	}

	function ensureCalendar() {
		var el = document.getElementById("usis-proj-schedule-calendar");
		if (!el || typeof FullCalendar === "undefined") {
			return;
		}
		if (state.calendar) {
			syncCalendarEvents();
			state.calendar.updateSize();
			return;
		}
		var initial = state.items.length ? state.items[0].start_date : undefined;
		state.calendar = new FullCalendar.Calendar(el, {
			headerToolbar: {
				left: "prev,next today",
				center: "title",
				right: "dayGridMonth,timeGridWeek,listMonth",
			},
			initialView: "dayGridMonth",
			initialDate: initial || undefined,
			height: "auto",
			navLinks: true,
			editable: false,
			selectable: false,
			events: buildFcEvents(state.items),
		});
		state.calendar.render();
	}

	function renderTable() {
		var tb = document.getElementById("usis-sched-tbody");
		if (!tb) return;
		if (!state.items.length) {
			tb.innerHTML =
				'<tr><td colspan="5" class="text-muted small">No installation windows yet. Use <strong>+ Add window</strong> to add date ranges by area.</td></tr>';
			return;
		}
		var rows = [];
		for (var i = 0; i < state.items.length; i++) {
			var it = state.items[i];
			rows.push(
				"<tr>" +
					"<td>" +
					esc(it.title) +
					"</td>" +
					"<td>" +
					esc(it.start_date) +
					"</td>" +
					"<td>" +
					esc(it.end_date) +
					"</td>" +
					"<td>" +
					esc(it.crew_label || "—") +
					"</td>" +
					'<td class="text-nowrap">' +
					'<button type="button" class="btn btn-outline-secondary btn-sm py-0 usis-sched-edit" data-id="' +
					escAttr(it.id) +
					'">Edit</button> ' +
					'<button type="button" class="btn btn-outline-danger btn-sm py-0 usis-sched-del" data-id="' +
					escAttr(it.id) +
					'">Delete</button>' +
					"</td>" +
					"</tr>"
			);
		}
		tb.innerHTML = rows.join("");
	}

	function notifyScheduleChanged() {
		try {
			window.dispatchEvent(new CustomEvent("usis-project-schedule-changed"));
		} catch (e) {}
	}

	function loadSchedule() {
		if (!state.projectId) return;
		setSchedError("");
		setSchedLoading(true);
		var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(state.projectId) + "/schedule-items";
		fetch(url, { headers: Object.assign({ Accept: "application/json" }, actorHeaders()) })
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				setSchedLoading(false);
				if (!res.ok) {
					setSchedError((res.body && res.body.error) || "Failed to load schedule (" + res.status + ").");
					return;
				}
				state.items = Array.isArray(res.body.items) ? res.body.items : [];
				renderTable();
				syncCalendarEvents();
				notifyScheduleChanged();
			})
			.catch(function () {
				setSchedLoading(false);
				setSchedError("Network error loading schedule.");
			});
	}

	function modalErr(msg) {
		var el = document.getElementById("usis-sched-modal-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function scheduleModal() {
		var node = document.getElementById("usis-modal-schedule-item");
		if (!node || typeof bootstrap === "undefined") return null;
		return bootstrap.Modal.getOrCreateInstance(node);
	}

	function openModalCreate() {
		modalErr("");
		var tEl = document.getElementById("usis-modal-schedule-item-title");
		if (tEl) tEl.textContent = "Add installation window";
		var hid = document.getElementById("usis-sched-modal-item-id");
		if (hid) hid.value = "";
		var title = document.getElementById("usis-sched-modal-title");
		if (title) title.value = "";
		var s = document.getElementById("usis-sched-modal-start");
		var e = document.getElementById("usis-sched-modal-end");
		if (s) s.value = "";
		if (e) e.value = "";
		var c = document.getElementById("usis-sched-modal-crew");
		if (c) c.value = "";
		var m = scheduleModal();
		if (m) m.show();
	}

	function openModalEdit(it) {
		modalErr("");
		var tEl = document.getElementById("usis-modal-schedule-item-title");
		if (tEl) tEl.textContent = "Edit installation window";
		var hid = document.getElementById("usis-sched-modal-item-id");
		if (hid) hid.value = it.id;
		var title = document.getElementById("usis-sched-modal-title");
		if (title) title.value = it.title || "";
		var s = document.getElementById("usis-sched-modal-start");
		var e = document.getElementById("usis-sched-modal-end");
		if (s) s.value = (it.start_date || "").slice(0, 10);
		if (e) e.value = (it.end_date || "").slice(0, 10);
		var c = document.getElementById("usis-sched-modal-crew");
		if (c) c.value = it.crew_label || "";
		var m = scheduleModal();
		if (m) m.show();
	}

	function saveModal() {
		modalErr("");
		var id = (document.getElementById("usis-sched-modal-item-id") || {}).value || "";
		var title = (document.getElementById("usis-sched-modal-title") || {}).value || "";
		var start = (document.getElementById("usis-sched-modal-start") || {}).value || "";
		var end = (document.getElementById("usis-sched-modal-end") || {}).value || "";
		var crew = (document.getElementById("usis-sched-modal-crew") || {}).value || "";
		if (!String(title).trim()) {
			modalErr("Area / scope is required.");
			return;
		}
		if (!start || !end) {
			modalErr("Start and end dates are required.");
			return;
		}
		var payload = {
			title: String(title).trim(),
			start_date: start,
			end_date: end,
			crew_label: String(crew).trim() || null,
		};
		var method = id ? "PATCH" : "POST";
		var url =
			apiBase() +
			"/api/v1/projects/" +
			encodeURIComponent(state.projectId) +
			"/schedule-items" +
			(id ? "/" + encodeURIComponent(id) : "");
		fetch(url, {
			method: method,
			headers: Object.assign(
				{ Accept: "application/json", "Content-Type": "application/json" },
				actorHeaders()
			),
			body: JSON.stringify(payload),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					modalErr((res.body && res.body.error) || "Save failed.");
					return;
				}
				var m = scheduleModal();
				if (m) m.hide();
				loadSchedule();
			})
			.catch(function () {
				modalErr("Network error.");
			});
	}

	function deleteItem(itemId) {
		if (!window.confirm("Delete this installation window?")) return;
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
					setSchedError((res.body && res.body.error) || "Delete failed.");
					return;
				}
				loadSchedule();
			})
			.catch(function () {
				setSchedError("Network error on delete.");
			});
	}

	function itemById(id) {
		for (var i = 0; i < state.items.length; i++) {
			if (state.items[i].id === id) return state.items[i];
		}
		return null;
	}

	function wire() {
		state.projectId = projectIdFromQuery();
		if (!state.projectId) return;

		var tabSched = document.getElementById("proj-tab-schedule");
		if (tabSched) {
			tabSched.addEventListener("shown.bs.tab", function () {
				if (!state.scheduleFetched) {
					state.scheduleFetched = true;
					loadSchedule();
				}
			});
		}

		var calTab = document.getElementById("proj-sched-sub-tab-cal");
		if (calTab) {
			calTab.addEventListener("shown.bs.tab", function () {
				ensureCalendar();
			});
		}

		var addBtn = document.getElementById("usis-sched-btn-add");
		if (addBtn) addBtn.addEventListener("click", openModalCreate);

		var saveBtn = document.getElementById("usis-sched-modal-save");
		if (saveBtn) saveBtn.addEventListener("click", saveModal);

		var tb = document.getElementById("usis-sched-tbody");
		if (tb) {
			tb.addEventListener("click", function (ev) {
				var ed = ev.target && ev.target.closest && ev.target.closest(".usis-sched-edit");
				var del = ev.target && ev.target.closest && ev.target.closest(".usis-sched-del");
				if (ed) {
					var id1 = ed.getAttribute("data-id");
					var it1 = itemById(id1);
					if (it1) openModalEdit(it1);
				} else if (del) {
					var id2 = del.getAttribute("data-id");
					if (id2) deleteItem(id2);
				}
			});
		}
	}

	/** Lets the Tasks tab reuse the same installation-window modal (title / dates / crew). */
	window.USISProjectScheduleUi = {
		openCreateModal: openModalCreate,
		openEditItem: function (it) {
			if (it) openModalEdit(it);
		},
		reload: loadSchedule,
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
