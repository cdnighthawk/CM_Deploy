/**
 * USIS categorized calendar — procurement, project schedule, RFIs, submittals, RFPs, milestones.
 */
(function () {
	"use strict";

	var state = {
		calendar: null,
		projects: [],
	};

	var PRESET_CATEGORIES = {
		all: [
			"procurement_order",
			"procurement_delivery",
			"schedule",
			"rfi",
			"submittal",
			"rfp",
			"project_milestone",
		],
		procurement: ["procurement_order", "procurement_delivery", "rfp"],
		project: ["schedule", "rfi", "submittal", "project_milestone"],
	};

	var CATEGORY_COLORS = {
		procurement_order: { bg: "#ffc107", border: "#e0a800", text: "#212529" },
		procurement_delivery: { bg: "#198754", border: "#146c43", text: "#fff" },
		schedule: { bg: "#0d6efd", border: "#0a58ca", text: "#fff" },
		rfi: { bg: "#dc3545", border: "#b02a37", text: "#fff" },
		submittal: { bg: "#6c757d", border: "#565e64", text: "#fff" },
		rfp: { bg: "#6f42c1", border: "#59359a", text: "#fff" },
		project_milestone: { bg: "#20c997", border: "#1aa179", text: "#212529" },
	};

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		if (window.location.protocol === "file:") {
			return "http://127.0.0.1:5000";
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

	function qs(name) {
		return new URLSearchParams(window.location.search).get(name);
	}

	function setLoading(on) {
		var el = document.getElementById("usis-cal-loading");
		if (el) {
			el.classList.toggle("d-none", !on);
		}
	}

	function setError(msg) {
		var el = document.getElementById("usis-cal-error");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
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

	function selectedCategories() {
		var preset = (document.getElementById("usis-cal-preset") || {}).value || "all";
		if (preset !== "all" && PRESET_CATEGORIES[preset]) {
			return PRESET_CATEGORIES[preset].slice();
		}
		var boxes = document.querySelectorAll(".usis-cal-cat:checked");
		var out = [];
		for (var i = 0; i < boxes.length; i++) {
			if (boxes[i].value) out.push(boxes[i].value);
		}
		return out;
	}

	function applyPresetToCheckboxes() {
		var preset = (document.getElementById("usis-cal-preset") || {}).value || "all";
		var cats = PRESET_CATEGORIES[preset];
		var boxes = document.querySelectorAll(".usis-cal-cat");
		for (var i = 0; i < boxes.length; i++) {
			var b = boxes[i];
			if (preset === "all") {
				b.checked = true;
				b.disabled = false;
			} else if (cats) {
				b.checked = cats.indexOf(b.value) >= 0;
				b.disabled = false;
			}
		}
		var wrap = document.getElementById("usis-cal-categories-wrap");
		if (wrap) {
			wrap.classList.toggle("opacity-50", preset !== "all");
		}
	}

	function buildFcEvent(item) {
		var colors = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.schedule;
		var title = item.title;
		if (!qs("project_id") && item.project_name) {
			title = "[" + item.project_name + "] " + title;
		}
		var ev = {
			id: item.id,
			title: title,
			start: item.start,
			allDay: true,
			backgroundColor: colors.bg,
			borderColor: colors.border,
			textColor: colors.text,
			extendedProps: {
				category: item.category,
				category_label: item.category_label,
				project_id: item.project_id,
				project_name: item.project_name,
				url: item.url,
			},
		};
		if (item.start !== item.end) {
			ev.end = toFcExclusiveEnd(item.end);
		}
		return ev;
	}

	function fetchEvents(fetchInfo, successCallback, failureCallback) {
		setError("");
		setLoading(true);
		var cats = selectedCategories();
		if (!cats.length) {
			setLoading(false);
			successCallback([]);
			return;
		}
		var params = ["categories=" + encodeURIComponent(cats.join(","))];
		var pid = (document.getElementById("usis-cal-project") || {}).value || qs("project_id") || "";
		if (pid) {
			params.push("project_id=" + encodeURIComponent(pid));
		}
		if (fetchInfo && fetchInfo.start) {
			params.push("start=" + encodeURIComponent(fetchInfo.startStr.slice(0, 10)));
		}
		if (fetchInfo && fetchInfo.end) {
			params.push("end=" + encodeURIComponent(fetchInfo.endStr.slice(0, 10)));
		}
		var url = apiBase() + "/api/v1/calendar-events?" + params.join("&");
		fetch(url, { headers: Object.assign({ Accept: "application/json" }, actorHeaders()) })
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				setLoading(false);
				if (!res.ok) {
					var msg = (res.body && res.body.error) || "Failed to load calendar (" + res.status + ").";
					setError(msg);
					failureCallback(new Error(msg));
					return;
				}
				var items = Array.isArray(res.body.items) ? res.body.items : [];
				successCallback(items.map(buildFcEvent));
			})
			.catch(function () {
				setLoading(false);
				setError("Network error loading calendar.");
				failureCallback(new Error("network"));
			});
	}

	function ensureCalendar() {
		var el = document.getElementById("usis-calendar-main");
		if (!el || typeof FullCalendar === "undefined") {
			return;
		}
		if (state.calendar) {
			state.calendar.refetchEvents();
			return;
		}
		state.calendar = new FullCalendar.Calendar(el, {
			headerToolbar: {
				left: "prev,next today",
				center: "title",
				right: "dayGridMonth,timeGridWeek,listMonth",
			},
			initialView: "dayGridMonth",
			height: "auto",
			navLinks: true,
			editable: false,
			selectable: false,
			events: fetchEvents,
			eventClick: function (info) {
				var url = info.event.extendedProps && info.event.extendedProps.url;
				if (url) {
					info.jsEvent.preventDefault();
					window.location.href = url;
				}
			},
			eventDidMount: function (info) {
				var cat = info.event.extendedProps && info.event.extendedProps.category_label;
				var proj = info.event.extendedProps && info.event.extendedProps.project_name;
				var tip = info.event.title;
				if (cat) tip += " (" + cat + ")";
				if (proj) tip += " — " + proj;
				info.el.setAttribute("title", tip);
			},
		});
		state.calendar.render();
	}

	function loadProjects() {
		var sel = document.getElementById("usis-cal-project");
		if (!sel) return;
		var url = apiBase() + "/api/v1/projects";
		fetch(url, { headers: Object.assign({ Accept: "application/json" }, actorHeaders()) })
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				state.projects = Array.isArray(data.items) ? data.items : [];
				var html = '<option value="">All accessible projects</option>';
				for (var i = 0; i < state.projects.length; i++) {
					var p = state.projects[i];
					var label = p.name || p.id;
					if (p.number) {
						label = p.number + " — " + label;
					}
					html +=
						'<option value="' +
						String(p.id).replace(/"/g, "&quot;") +
						'">' +
						label +
						"</option>";
				}
				sel.innerHTML = html;
				var fromUrl = qs("project_id");
				if (fromUrl) {
					sel.value = fromUrl;
				}
				var preset = qs("preset");
				if (preset && document.getElementById("usis-cal-preset")) {
					document.getElementById("usis-cal-preset").value = preset;
					applyPresetToCheckboxes();
				}
				ensureCalendar();
			})
			.catch(function () {
				ensureCalendar();
			});
	}

	function bindUi() {
		var preset = document.getElementById("usis-cal-preset");
		if (preset) {
			preset.addEventListener("change", function () {
				applyPresetToCheckboxes();
			});
		}
		var apply = document.getElementById("usis-cal-apply");
		if (apply) {
			apply.addEventListener("click", function () {
				if (state.calendar) {
					state.calendar.refetchEvents();
				}
			});
		}
	}

	document.addEventListener("DOMContentLoaded", function () {
		bindUi();
		applyPresetToCheckboxes();
		loadProjects();
	});
})();
