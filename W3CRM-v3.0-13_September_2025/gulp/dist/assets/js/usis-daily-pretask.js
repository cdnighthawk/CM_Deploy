/**
 * Daily Pre-Task Safety Plan (Appendix E) — create, edit, submit.
 */
(function () {
	"use strict";

	var CHECKLIST = [
		{ key: "supervisor_walkthrough", label: "Supervisor walk-through of the work area (housekeeping, fall protection, ladders, access)." },
		{ key: "coordination_other_crafts", label: "Coordination with other crafts working in the area." },
		{ key: "equipment_check", label: "Tools, materials, and equipment are safe and available." },
		{ key: "training_complete", label: "Required training is complete; new employees are familiarized." },
		{ key: "sufficient_personnel", label: "Sufficient personnel are assigned for the task." },
	];

	var state = {
		item: null,
		locked: false,
	};

	function api() {
		return window.USIS_API;
	}

	function qs(name) {
		try {
			return new URLSearchParams(window.location.search).get(name) || "";
		} catch (e) {
			return "";
		}
	}

	function setErr(msg) {
		var el = document.getElementById("usis-pretask-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
			el.textContent = "";
		}
	}

	function setOk(msg) {
		var el = document.getElementById("usis-pretask-ok");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
			el.textContent = "";
		}
	}

	function emptyTask() {
		return { jha_complete: false, task: "", hazards: "", steps: "" };
	}

	function emptyAttendee() {
		return { print_name: "", signature: "" };
	}

	function emptyChecklist() {
		var out = {};
		CHECKLIST.forEach(function (row) {
			out[row.key] = false;
		});
		return out;
	}

	function val(id) {
		var el = document.getElementById(id);
		return el ? String(el.value || "") : "";
	}

	function setVal(id, value) {
		var el = document.getElementById(id);
		if (el) el.value = value == null ? "" : String(value);
	}

	function setDisabled(locked) {
		state.locked = !!locked;
		document.querySelectorAll("#usis-pretask-form input, #usis-pretask-form textarea, #usis-pretask-form select, #usis-pretask-form button").forEach(function (el) {
			if (el.getAttribute("data-keep-enabled") === "1") return;
			el.disabled = !!locked;
		});
		var save = document.getElementById("usis-pretask-save");
		var submit = document.getElementById("usis-pretask-submit");
		if (save) save.disabled = !!locked;
		if (submit) submit.disabled = !!locked;
		var badge = document.getElementById("usis-pretask-status");
		if (badge) {
			badge.textContent = locked ? "Submitted" : "Draft";
			badge.className = "usis-status-chip " + (locked ? "usis-status-chip--success" : "usis-status-chip--draft");
		}
	}

	function readChecklist() {
		var out = emptyChecklist();
		CHECKLIST.forEach(function (row) {
			var el = document.getElementById("chk-" + row.key);
			out[row.key] = !!(el && el.checked);
		});
		return out;
	}

	function readTasks() {
		var rows = [];
		document.querySelectorAll("#usis-pretask-tasks tr").forEach(function (tr) {
			rows.push({
				jha_complete: !!(tr.querySelector("[data-f=jha]") && tr.querySelector("[data-f=jha]").checked),
				task: tr.querySelector("[data-f=task]") ? tr.querySelector("[data-f=task]").value : "",
				hazards: tr.querySelector("[data-f=hazards]") ? tr.querySelector("[data-f=hazards]").value : "",
				steps: tr.querySelector("[data-f=steps]") ? tr.querySelector("[data-f=steps]").value : "",
			});
		});
		return rows.length ? rows : [emptyTask()];
	}

	function readAttendees() {
		var rows = [];
		document.querySelectorAll("#usis-pretask-attendees tr").forEach(function (tr) {
			rows.push({
				print_name: tr.querySelector("[data-f=print_name]") ? tr.querySelector("[data-f=print_name]").value : "",
				signature: tr.querySelector("[data-f=signature]") ? tr.querySelector("[data-f=signature]").value : "",
			});
		});
		return rows.length ? rows : [emptyAttendee()];
	}

	function payloadFromForm() {
		return {
			company_name: val("usis-pretask-company") || "DOCON, INC",
			area_of_work: val("usis-pretask-area"),
			checklist: readChecklist(),
			tasks: readTasks(),
			near_miss: document.getElementById("usis-pretask-near-miss")
				? document.getElementById("usis-pretask-near-miss").value === "yes"
				: false,
			near_miss_notes: val("usis-pretask-near-miss-notes"),
			required_permits: val("usis-pretask-permits"),
			items_concerns: val("usis-pretask-concerns"),
			quality_previous_day: val("usis-pretask-quality-prev"),
			present_items_concerns: val("usis-pretask-present"),
			attendees: readAttendees(),
			supervisor_name: val("usis-pretask-supervisor"),
			supervisor_signature: val("usis-pretask-supervisor-sig"),
		};
	}

	function addTaskRow(row) {
		row = row || emptyTask();
		var tbody = document.getElementById("usis-pretask-tasks");
		if (!tbody) return;
		var tr = document.createElement("tr");
		tr.innerHTML =
			'<td class="align-middle text-center"><input type="checkbox" class="form-check-input" data-f="jha"' +
			(row.jha_complete ? " checked" : "") +
			"></td>" +
			'<td><textarea class="form-control form-control-sm" rows="2" data-f="task">' +
			escapeText(row.task) +
			"</textarea></td>" +
			'<td><textarea class="form-control form-control-sm" rows="2" data-f="hazards">' +
			escapeText(row.hazards) +
			"</textarea></td>" +
			'<td><textarea class="form-control form-control-sm" rows="2" data-f="steps">' +
			escapeText(row.steps) +
			"</textarea></td>" +
			'<td class="align-middle"><button type="button" class="btn btn-sm btn-outline-secondary" data-remove-task>&times;</button></td>';
		tbody.appendChild(tr);
	}

	function addAttendeeRow(row) {
		row = row || emptyAttendee();
		var tbody = document.getElementById("usis-pretask-attendees");
		if (!tbody) return;
		var tr = document.createElement("tr");
		tr.innerHTML =
			'<td><input type="text" class="form-control form-control-sm" data-f="print_name" value="' +
			escapeAttr(row.print_name) +
			'"></td>' +
			'<td><input type="text" class="form-control form-control-sm" data-f="signature" value="' +
			escapeAttr(row.signature) +
			'" placeholder="Type name or paste signature"></td>' +
			'<td class="align-middle"><button type="button" class="btn btn-sm btn-outline-secondary" data-remove-attendee>&times;</button></td>';
		tbody.appendChild(tr);
	}

	function escapeText(s) {
		return String(s || "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;");
	}

	function escapeAttr(s) {
		return escapeText(s).replace(/"/g, "&quot;");
	}

	function renderChecklist(values) {
		var host = document.getElementById("usis-pretask-checklist");
		if (!host) return;
		values = values || emptyChecklist();
		host.innerHTML = CHECKLIST.map(function (row) {
			return (
				'<label class="d-flex align-items-start gap-2 mb-2">' +
				'<input type="checkbox" class="form-check-input mt-1" id="chk-' +
				row.key +
				'"' +
				(values[row.key] ? " checked" : "") +
				">" +
				'<span class="small">' +
				row.label +
				"</span></label>"
			);
		}).join("");
	}

	function applyItem(item) {
		state.item = item;
		setVal("usis-pretask-company", item.company_name || "DOCON, INC");
		setVal("usis-pretask-area", item.area_of_work || "");
		setVal("usis-pretask-date", item.work_date || "");
		setVal("usis-pretask-permits", item.required_permits || "");
		setVal("usis-pretask-concerns", item.items_concerns || "");
		setVal("usis-pretask-quality-prev", item.quality_previous_day || "");
		setVal("usis-pretask-present", item.present_items_concerns || "");
		setVal("usis-pretask-near-miss-notes", item.near_miss_notes || "");
		setVal("usis-pretask-supervisor", item.supervisor_name || "");
		setVal("usis-pretask-supervisor-sig", item.supervisor_signature || "");
		var nm = document.getElementById("usis-pretask-near-miss");
		if (nm) nm.value = item.near_miss ? "yes" : "no";
		var proj = document.getElementById("usis-pretask-project");
		if (proj && item.project_id) proj.value = item.project_id;
		renderChecklist(item.checklist);
		var tasks = document.getElementById("usis-pretask-tasks");
		if (tasks) tasks.innerHTML = "";
		(item.tasks && item.tasks.length ? item.tasks : [emptyTask(), emptyTask(), emptyTask(), emptyTask()]).forEach(addTaskRow);
		var att = document.getElementById("usis-pretask-attendees");
		if (att) att.innerHTML = "";
		(item.attendees && item.attendees.length ? item.attendees : [emptyAttendee(), emptyAttendee()]).forEach(addAttendeeRow);
		setDisabled(item.status === "submitted");
		var meta = document.getElementById("usis-pretask-meta");
		if (meta) {
			var job = (item.project_number ? item.project_number + " — " : "") + (item.project_name || "");
			meta.textContent = (job ? job + " · " : "") + (item.crew_lead_name ? "Lead: " + item.crew_lead_name : "");
		}
	}

	function loadProjects() {
		return api()
			.fetchJson("/api/v1/projects", { params: { limit: 500 } })
			.then(function (body) {
				var sel = document.getElementById("usis-pretask-project");
				if (!sel) return;
				var current = qs("project_id") || (state.item && state.item.project_id) || "";
				var items = (body && body.items) || [];
				sel.innerHTML = '<option value="">Select a project…</option>' +
					items
						.map(function (p) {
							var label = (p.number ? p.number + " — " : "") + (p.name || p.id);
							return '<option value="' + escapeAttr(p.id) + '">' + escapeText(label) + "</option>";
						})
						.join("");
				if (current) sel.value = current;
			});
	}

	function openExisting(id) {
		return api()
			.fetchJson("/api/v1/safety/pretasks/" + encodeURIComponent(id))
			.then(function (body) {
				applyItem(body.item);
			});
	}

	function openOrCreate() {
		var projectId = val("usis-pretask-project") || qs("project_id");
		var workDate = val("usis-pretask-date") || qs("date") || new Date().toISOString().slice(0, 10);
		if (!projectId) {
			setErr("Select a project to start today's pretask.");
			return Promise.resolve();
		}
		return api()
			.fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/daily-pretasks", {
				params: { date: workDate },
			})
			.then(function (body) {
				applyItem(body.item);
				var url = new URL(window.location.href);
				url.searchParams.set("id", body.item.id);
				url.searchParams.set("project_id", body.item.project_id);
				url.searchParams.set("date", body.item.work_date);
				window.history.replaceState({}, "", url.toString());
				setErr("");
			});
	}

	function save(extra) {
		if (!state.item || !state.item.id) {
			return openOrCreate().then(function () {
				if (state.item && state.item.id) return save(extra);
			});
		}
		var body = Object.assign(payloadFromForm(), extra || {});
		setErr("");
		setOk("");
		return api()
			.fetchJson("/api/v1/daily-pretasks/" + encodeURIComponent(state.item.id), {
				method: "PUT",
				body: body,
			})
			.then(function (res) {
				applyItem(res.item);
				setOk("Saved.");
				return res.item;
			});
	}

	function submit() {
		return save().then(function () {
			if (!state.item || !state.item.id) return;
			return api()
				.fetchJson("/api/v1/daily-pretasks/" + encodeURIComponent(state.item.id) + "/submit", {
					method: "POST",
					body: {},
				})
				.then(function (res) {
					applyItem(res.item);
					setOk("Submitted. This plan is locked for field edits.");
				});
		});
	}

	function wire() {
		renderChecklist(emptyChecklist());
		[emptyTask(), emptyTask(), emptyTask(), emptyTask()].forEach(addTaskRow);
		[emptyAttendee(), emptyAttendee()].forEach(addAttendeeRow);
		setVal("usis-pretask-date", qs("date") || new Date().toISOString().slice(0, 10));
		setVal("usis-pretask-company", "DOCON, INC");

		document.getElementById("usis-pretask-add-task") &&
			document.getElementById("usis-pretask-add-task").addEventListener("click", function () {
				addTaskRow();
			});
		document.getElementById("usis-pretask-add-attendee") &&
			document.getElementById("usis-pretask-add-attendee").addEventListener("click", function () {
				addAttendeeRow();
			});
		document.getElementById("usis-pretask-tasks") &&
			document.getElementById("usis-pretask-tasks").addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-remove-task]");
				if (btn) btn.closest("tr").remove();
			});
		document.getElementById("usis-pretask-attendees") &&
			document.getElementById("usis-pretask-attendees").addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-remove-attendee]");
				if (btn) btn.closest("tr").remove();
			});
		document.getElementById("usis-pretask-load") &&
			document.getElementById("usis-pretask-load").addEventListener("click", function () {
				openOrCreate().catch(showFail);
			});
		document.getElementById("usis-pretask-save") &&
			document.getElementById("usis-pretask-save").addEventListener("click", function () {
				save().catch(showFail);
			});
		document.getElementById("usis-pretask-submit") &&
			document.getElementById("usis-pretask-submit").addEventListener("click", function () {
				submit().catch(showFail);
			});

		loadProjects()
			.then(function () {
				if (qs("id")) return openExisting(qs("id"));
				if (qs("project_id")) return openOrCreate();
			})
			.catch(showFail);
	}

	function showFail(err) {
		var msg = (err && err.message) || "Request failed.";
		var body = err && err.body;
		if (typeof body === "string") {
			try {
				var parsed = JSON.parse(body);
				if (parsed && parsed.error) msg = parsed.error;
			} catch (e) {}
		}
		if (String(msg).indexOf("401") !== -1) {
			msg = "Sign in required. Field crews can also set localStorage usisActorUserId on this machine.";
		}
		setOk("");
		setErr(msg);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
