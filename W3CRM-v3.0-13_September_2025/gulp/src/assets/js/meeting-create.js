/**
 * Project meeting create / edit page (office minutes record, not Teams / Schedule).
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		meetingId: "",
		users: [],
		companies: [],
		attendees: [],
		items: [],
		busy: false,
	};

	function $(id) {
		return document.getElementById(id);
	}

	function api() {
		return window.USIS_API;
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function queryParam(name) {
		try {
			return new URLSearchParams(window.location.search).get(name) || "";
		} catch (e) {
			return "";
		}
	}

	function projectId() {
		return (
			queryParam("project_id") ||
			queryParam("projectId") ||
			(window.USISProjectContext && window.USISProjectContext.getProjectId && window.USISProjectContext.getProjectId()) ||
			""
		).trim();
	}

	function meetingIdFromQuery() {
		return queryParam("id").trim();
	}

	function projectDetailHref(pid) {
		var id = pid || state.projectId;
		if (!id) return "construction/project-detail.html";
		return "construction/project-detail.html?id=" + encodeURIComponent(id) + "&tab=meetings";
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function setErr(msg) {
		var el = $("usis-meeting-error");
		if (!el) return;
		if (msg) {
			el.textContent = String(msg);
			el.classList.remove("d-none");
			el.scrollIntoView({ behavior: "smooth", block: "center" });
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function errMessage(err) {
		if (!err) return "Could not save.";
		var body = err.body;
		if (typeof body === "string") {
			try {
				body = JSON.parse(body);
			} catch (e) {}
		}
		if (body && typeof body === "object") return body.error || body.message || err.message || "Could not save.";
		return err.message || "Could not save.";
	}

	function personLabel(u) {
		if (!u) return "";
		return (u.name || [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email || "").trim();
	}

	function userById(id) {
		return state.users.find(function (x) {
			return String(x.id) === String(id);
		});
	}

	function todayIso() {
		var d = new Date();
		return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
	}

	function hhmm(raw) {
		var s = String(raw || "").trim();
		if (!s) return "";
		var m = s.match(/^(\d{1,2}):(\d{2})/);
		if (!m) return s.slice(0, 5);
		return String(m[1]).padStart(2, "0") + ":" + m[2];
	}

	function val(id) {
		var el = $(id);
		return el ? String(el.value || "").trim() : "";
	}

	function setVal(id, value) {
		var el = $(id);
		if (el) el.value = value == null ? "" : String(value);
	}

	function emptyGuest() {
		return { user_id: "", name: "", company: "", role: "", present: true, guest: true };
	}

	function emptyItem() {
		return { topic: "", owner_user_id: "", owner_name: "", due_date: "", done: false };
	}

	function ensureGuest() {
		if (
			!state.attendees.some(function (a) {
				return a.guest;
			})
		) {
			state.attendees.push(emptyGuest());
		}
	}

	function fillUserSelect(sel, emptyLabel, excludeIds) {
		if (!sel) return;
		excludeIds = excludeIds || [];
		var keep = sel.value;
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = emptyLabel || "Select a person";
		sel.appendChild(blank);
		state.users.forEach(function (u) {
			if (excludeIds.indexOf(String(u.id)) !== -1) return;
			var opt = document.createElement("option");
			opt.value = u.id;
			opt.textContent = personLabel(u);
			sel.appendChild(opt);
		});
		if (keep && Array.prototype.some.call(sel.options, function (o) { return o.value === keep; })) {
			sel.value = keep;
		} else {
			sel.value = "";
		}
	}

	function fillCompanySelect() {
		var sel = $("usis-meeting-add-company");
		if (!sel) return;
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = "Add from companies";
		sel.appendChild(blank);
		state.companies.forEach(function (c) {
			var opt = document.createElement("option");
			opt.value = c.id || c.company_id || c.name || "";
			opt.textContent = c.name || "";
			opt.setAttribute("data-name", c.name || "");
			opt.setAttribute("data-role", c.directory_role || c.company_type || "");
			if (opt.value) sel.appendChild(opt);
		});
	}

	function attendeeUsedUserIds() {
		return state.attendees
			.filter(function (a) {
				return a.user_id && !a.guest;
			})
			.map(function (a) {
				return String(a.user_id);
			});
	}

	function renderLookups() {
		fillUserSelect($("usis-meeting-facilitator"), "Select a person");
		fillUserSelect($("usis-meeting-add-person"), "Add from people", attendeeUsedUserIds());
		fillCompanySelect();
	}

	function renderAttendees() {
		var tbody = $("usis-meeting-attendees");
		if (!tbody) return;
		ensureGuest();
		tbody.innerHTML = state.attendees
			.map(function (a, i) {
				var guestNote = a.guest
					? '<div class="small text-muted mt-1" data-i18n="Guest (typed; not a Company)">Guest (typed; not a Company)</div>'
					: "";
				var remove = a.guest
					? ""
					: '<button type="button" class="btn btn-link btn-sm p-0" data-att-remove="' +
						i +
						'" data-i18n="Remove">Remove</button>';
				return (
					"<tr>" +
					'<td><input type="text" class="form-control" data-att-field="name" data-att-i="' +
					i +
					'" maxlength="200" value="' +
					esc(a.name) +
					'" placeholder="' +
					(a.guest ? "Guest name" : "Name") +
					'">' +
					guestNote +
					"</td>" +
					'<td><input type="text" class="form-control" data-att-field="company" data-att-i="' +
					i +
					'" maxlength="200" value="' +
					esc(a.company) +
					'" placeholder="Company"></td>' +
					'<td><input type="text" class="form-control" data-att-field="role" data-att-i="' +
					i +
					'" maxlength="120" value="' +
					esc(a.role) +
					'" placeholder="Role"></td>' +
					'<td class="text-center align-middle"><input type="checkbox" class="form-check-input" data-att-field="present" data-att-i="' +
					i +
					'"' +
					(a.present !== false ? " checked" : "") +
					"></td>" +
					'<td class="align-middle">' +
					remove +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
		fillUserSelect($("usis-meeting-add-person"), "Add from people", attendeeUsedUserIds());
	}

	function ownerOptionsHtml(selectedId) {
		var html = '<option value="">Owner</option>';
		state.users.forEach(function (u) {
			var id = String(u.id);
			html +=
				'<option value="' +
				esc(id) +
				'"' +
				(selectedId && String(selectedId) === id ? " selected" : "") +
				">" +
				esc(personLabel(u)) +
				"</option>";
		});
		return html;
	}

	function renderAgenda() {
		var tbody = $("usis-meeting-agenda");
		if (!tbody) return;
		if (!state.items.length) state.items.push(emptyItem());
		tbody.innerHTML = state.items
			.map(function (it, i) {
				return (
					"<tr>" +
					'<td class="align-middle text-muted">' +
					(i + 1) +
					"</td>" +
					'<td><input type="text" class="form-control" data-ag-field="topic" data-ag-i="' +
					i +
					'" maxlength="500" value="' +
					esc(it.topic) +
					'" placeholder="Topic"></td>' +
					'<td><select class="form-select" data-ag-field="owner_user_id" data-ag-i="' +
					i +
					'">' +
					ownerOptionsHtml(it.owner_user_id) +
					"</select></td>" +
					'<td><input type="date" class="form-control" data-ag-field="due_date" data-ag-i="' +
					i +
					'" value="' +
					esc(it.due_date) +
					'"></td>' +
					'<td class="text-center align-middle"><input type="checkbox" class="form-check-input" data-ag-field="done" data-ag-i="' +
					i +
					'"' +
					(it.done ? " checked" : "") +
					"></td>" +
					'<td class="align-middle"><button type="button" class="btn btn-link btn-sm p-0" data-ag-remove="' +
					i +
					'" data-i18n="Remove">Remove</button></td>' +
					"</tr>"
				);
			})
			.join("");
	}

	function syncAttendeeField(i, field, value) {
		var row = state.attendees[i];
		if (!row) return;
		if (field === "present") row.present = !!value;
		else row[field] = value;
	}

	function syncAgendaField(i, field, value) {
		var row = state.items[i];
		if (!row) return;
		if (field === "done") {
			row.done = !!value;
			return;
		}
		if (field === "owner_user_id") {
			row.owner_user_id = value || "";
			var u = userById(row.owner_user_id);
			row.owner_name = u ? personLabel(u) : "";
			return;
		}
		row[field] = value;
	}

	function collectAttendees() {
		return state.attendees
			.map(function (a) {
				var name = String(a.name || "").trim();
				var company = String(a.company || "").trim();
				if (!name && company) name = company;
				if (!name) return null;
				var row = {
					name: name,
					company: company,
					role: String(a.role || "").trim(),
					present: a.present !== false,
				};
				if (a.user_id) row.user_id = String(a.user_id);
				return row;
			})
			.filter(Boolean);
	}

	function collectItems() {
		return state.items
			.map(function (it, i) {
				var topic = String(it.topic || "").trim();
				if (!topic) return null;
				var row = {
					topic: topic,
					owner_user_id: it.owner_user_id || "",
					owner_name: it.owner_name || (userById(it.owner_user_id) ? personLabel(userById(it.owner_user_id)) : ""),
					due_date: it.due_date || "",
					done: !!it.done,
					sort_order: i + 1,
				};
				if (!row.owner_user_id) {
					row.owner_user_id = null;
				}
				if (!row.due_date) row.due_date = null;
				return row;
			})
			.filter(Boolean);
	}

	function collectPayload() {
		var meetingType = val("usis-meeting-type");
		var subject = val("usis-meeting-subject");
		var meetingDate = val("usis-meeting-date");
		var status = val("usis-meeting-status");
		if (!meetingType) return { error: "Type is required.", focus: "usis-meeting-type" };
		if (!subject) return { error: "Subject is required.", focus: "usis-meeting-subject" };
		if (!meetingDate) return { error: "Date is required.", focus: "usis-meeting-date" };
		if (!status) return { error: "Status is required.", focus: "usis-meeting-status" };
		var attendees = collectAttendees();
		if (!attendees.length) return { error: "Add at least one attendee.", focus: "usis-meeting-add-person" };
		var items = collectItems();
		if (!items.length) return { error: "Add at least one agenda item.", focus: "usis-meeting-agenda" };
		var body = {
			subject: subject,
			meeting_type: meetingType,
			meeting_date: meetingDate,
			status: status,
			start_time: hhmm(val("usis-meeting-start")),
			end_time: hhmm(val("usis-meeting-end")),
			location: val("usis-meeting-location"),
			facilitator_user_id: val("usis-meeting-facilitator") || null,
			notes: val("usis-meeting-notes"),
			minutes: val("usis-meeting-minutes"),
			attendees: attendees,
			items: items,
		};
		return { body: body };
	}

	function setBusy(on) {
		state.busy = !!on;
		["usis-meeting-save", "usis-meeting-save-new"].forEach(function (id) {
			var el = $(id);
			if (el) el.disabled = state.busy;
		});
	}

	function setTitles(isEdit, item) {
		var createLabel = "New Meeting";
		var editLabel = (item && (item.number || item.subject)) || "Meeting";
		var title = isEdit ? editLabel : createLabel;
		var crumb = $("usis-meeting-crumb-current");
		var page = $("usis-meeting-page-title");
		if (crumb) crumb.textContent = title;
		if (page) page.textContent = isEdit ? (item && item.subject ? String(item.subject) : "Meeting") : createLabel;
		var h1 = document.querySelector(".page-title h1");
		if (h1) h1.textContent = title;
		var active = document.querySelector(".page-title .breadcrumb-item.active span");
		if (active) active.textContent = title;
	}

	function applyItem(item) {
		item = item || {};
		setVal("usis-meeting-type", item.meeting_type || "");
		setVal("usis-meeting-subject", item.subject || "");
		setVal("usis-meeting-date", item.meeting_date ? String(item.meeting_date).slice(0, 10) : "");
		setVal("usis-meeting-status", item.status || "scheduled");
		setVal("usis-meeting-start", hhmm(item.start_time));
		setVal("usis-meeting-end", hhmm(item.end_time));
		setVal("usis-meeting-location", item.location || "");
		setVal("usis-meeting-facilitator", item.facilitator_user_id || "");
		setVal("usis-meeting-notes", item.notes || "");
		setVal("usis-meeting-minutes", item.minutes || "");
		var attendees = Array.isArray(item.attendees) ? item.attendees : [];
		state.attendees = attendees.map(function (a) {
			return {
				user_id: a.user_id || "",
				name: a.name || "",
				company: a.company || "",
				role: a.role || "",
				present: a.present !== false,
				guest: false,
			};
		});
		ensureGuest();
		var items = Array.isArray(item.items) ? item.items : [];
		state.items = items
			.slice()
			.sort(function (a, b) {
				return (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
			})
			.map(function (it) {
				return {
					topic: it.topic || "",
					owner_user_id: it.owner_user_id || "",
					owner_name: it.owner_name || "",
					due_date: it.due_date ? String(it.due_date).slice(0, 10) : "",
					done: !!it.done,
				};
			});
		if (!state.items.length) state.items.push(emptyItem());
		renderAttendees();
		renderAgenda();
		fillUserSelect($("usis-meeting-facilitator"), "Select a person");
		setVal("usis-meeting-facilitator", item.facilitator_user_id || "");
		setTitles(true, item);
	}

	function resetForm() {
		var form = $("usis-meeting-form");
		if (form) form.reset();
		state.meetingId = "";
		state.attendees = [emptyGuest()];
		state.items = [emptyItem()];
		setVal("usis-meeting-status", "scheduled");
		setVal("usis-meeting-date", todayIso());
		setVal("usis-meeting-type", "");
		setVal("usis-meeting-notes", "");
		setVal("usis-meeting-minutes", "");
		renderLookups();
		renderAttendees();
		renderAgenda();
		setTitles(false, null);
		try {
			var url = new URL(window.location.href);
			if (url.searchParams.has("id")) {
				url.searchParams.delete("id");
				window.history.replaceState({}, "", url.pathname + url.search + url.hash);
			}
		} catch (e) {}
	}

	function meetingsPath(id) {
		var base = "/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/meetings";
		if (id) return base + "/" + encodeURIComponent(id);
		return base;
	}

	function save(createNew) {
		if (state.busy) return;
		if (!state.projectId) {
			setErr("Open this form from a project Meetings tab.");
			return;
		}
		var collected = collectPayload();
		if (collected.error) {
			setErr(collected.error);
			var focus = $(collected.focus);
			if (focus) focus.focus();
			return;
		}
		setErr("");
		setBusy(true);
		var editing = !!state.meetingId;
		fetchJson(meetingsPath(state.meetingId), {
			method: editing ? "PATCH" : "POST",
			body: collected.body,
		})
			.then(function () {
				if (createNew) {
					resetForm();
					setBusy(false);
					var subject = $("usis-meeting-subject");
					if (subject) subject.focus();
					return;
				}
				window.location.href = projectDetailHref();
			})
			.catch(function (err) {
				setBusy(false);
				setErr(errMessage(err));
			});
	}

	function loadUsers() {
		return fetchJson("/api/v1/rfi-users", { params: { limit: 200 } }).then(function (data) {
			state.users = data.items || [];
		});
	}

	function loadCompanies() {
		if (!state.projectId) return Promise.resolve();
		return fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/directory/companies", {
			params: { all: 1 },
		})
			.then(function (data) {
				state.companies = data.items || [];
			})
			.catch(function () {
				state.companies = [];
			});
	}

	function loadMeeting() {
		if (!state.meetingId) {
			setVal("usis-meeting-status", "scheduled");
			setVal("usis-meeting-date", todayIso());
			state.attendees = [emptyGuest()];
			state.items = [emptyItem()];
			renderLookups();
			renderAttendees();
			renderAgenda();
			setTitles(false, null);
			return Promise.resolve();
		}
		return fetchJson(meetingsPath(state.meetingId)).then(function (data) {
			var item = (data && data.item) || data || {};
			renderLookups();
			applyItem(item);
		});
	}

	function wireTables() {
		var attBody = $("usis-meeting-attendees");
		if (attBody) {
			attBody.addEventListener("input", function (ev) {
				var el = ev.target.closest("[data-att-field]");
				if (!el) return;
				var i = parseInt(el.getAttribute("data-att-i"), 10);
				var field = el.getAttribute("data-att-field");
				if (field === "present") return;
				syncAttendeeField(i, field, el.value);
			});
			attBody.addEventListener("change", function (ev) {
				var el = ev.target.closest("[data-att-field]");
				if (!el) return;
				var i = parseInt(el.getAttribute("data-att-i"), 10);
				var field = el.getAttribute("data-att-field");
				if (field === "present") syncAttendeeField(i, field, el.checked);
			});
			attBody.addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-att-remove]");
				if (!btn) return;
				var i = parseInt(btn.getAttribute("data-att-remove"), 10);
				if (!isFinite(i) || !state.attendees[i] || state.attendees[i].guest) return;
				state.attendees.splice(i, 1);
				renderAttendees();
			});
		}
		var agBody = $("usis-meeting-agenda");
		if (agBody) {
			agBody.addEventListener("input", function (ev) {
				var el = ev.target.closest("[data-ag-field]");
				if (!el) return;
				var i = parseInt(el.getAttribute("data-ag-i"), 10);
				var field = el.getAttribute("data-ag-field");
				if (field === "done" || field === "owner_user_id") return;
				syncAgendaField(i, field, el.value);
			});
			agBody.addEventListener("change", function (ev) {
				var el = ev.target.closest("[data-ag-field]");
				if (!el) return;
				var i = parseInt(el.getAttribute("data-ag-i"), 10);
				var field = el.getAttribute("data-ag-field");
				if (field === "done") syncAgendaField(i, field, el.checked);
				else if (field === "owner_user_id") syncAgendaField(i, field, el.value);
				else syncAgendaField(i, field, el.value);
			});
			agBody.addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-ag-remove]");
				if (!btn) return;
				var i = parseInt(btn.getAttribute("data-ag-remove"), 10);
				if (!isFinite(i)) return;
				state.items.splice(i, 1);
				if (!state.items.length) state.items.push(emptyItem());
				renderAgenda();
			});
		}
		var addPerson = $("usis-meeting-add-person");
		if (addPerson) {
			addPerson.addEventListener("change", function () {
				var id = addPerson.value;
				if (!id) return;
				var u = userById(id);
				if (
					u &&
					!state.attendees.some(function (a) {
						return String(a.user_id) === String(id);
					})
				) {
					state.attendees.splice(state.attendees.length - (state.attendees.some(function (a) { return a.guest; }) ? 1 : 0), 0, {
						user_id: id,
						name: personLabel(u),
						company: "",
						role: "",
						present: true,
						guest: false,
					});
					renderAttendees();
				}
				addPerson.value = "";
			});
		}
		var addCo = $("usis-meeting-add-company");
		if (addCo) {
			addCo.addEventListener("change", function () {
				var opt = addCo.options[addCo.selectedIndex];
				if (!opt || !opt.value) return;
				var name = opt.getAttribute("data-name") || opt.textContent || "";
				var role = opt.getAttribute("data-role") || "";
				var insertAt = state.attendees.some(function (a) {
					return a.guest;
				})
					? state.attendees.length - 1
					: state.attendees.length;
				state.attendees.splice(insertAt, 0, {
					user_id: "",
					name: name,
					company: name,
					role: role,
					present: true,
					guest: false,
				});
				renderAttendees();
				addCo.value = "";
			});
		}
		var addAg = $("usis-meeting-add-agenda");
		if (addAg) {
			addAg.addEventListener("click", function () {
				state.items.push(emptyItem());
				renderAgenda();
			});
		}
	}

	function init() {
		state.projectId = projectId();
		state.meetingId = meetingIdFromQuery();
		var cancel = $("usis-meeting-cancel");
		var crumb = $("usis-meeting-crumb-list");
		if (cancel) cancel.setAttribute("href", projectDetailHref());
		if (crumb) crumb.setAttribute("href", projectDetailHref());
		if (!state.projectId) {
			setErr("Open this form from a project Meetings tab so a project id is in the URL.");
			return;
		}
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(state.projectId);
		}
		wireTables();
		var form = $("usis-meeting-form");
		if (form) {
			form.addEventListener("submit", function (ev) {
				ev.preventDefault();
				save(true);
			});
		}
		var saveBtn = $("usis-meeting-save");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				save(false);
			});
		}
		Promise.all([loadUsers(), loadCompanies()])
			.then(loadMeeting)
			.catch(function (err) {
				setErr(errMessage(err));
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
