(function () {
	"use strict";

	function apiBase() {
		if (window.location.protocol === "file:") return "http://127.0.0.1:5000";
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

	function showErr(msg) {
		var el = document.getElementById("usis-playbooks-alert");
		if (!el) return;
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function clearErr() {
		var el = document.getElementById("usis-playbooks-alert");
		if (!el) return;
		el.classList.add("d-none");
		el.textContent = "";
	}

	function apiFetch(path, opts) {
		opts = opts || {};
		opts.credentials = opts.credentials || "omit";
		opts.headers = Object.assign({}, actorHeaders(), opts.headers || {});
		return fetch(apiBase() + path, opts);
	}

	var state = {
		templates: [],
		selectedId: null,
		templateDetail: null,
		users: [],
		projects: [],
	};

	function esc(s) {
		if (s == null) return "";
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	function loadUsers(cb) {
		apiFetch("/api/v1/rfi-users")
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				state.users = data.items || data || [];
				if (cb) cb();
			})
			.catch(function () {
				state.users = [];
				if (cb) cb();
			});
	}

	function loadProjects(cb) {
		apiFetch("/api/v1/projects?limit=500")
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				state.projects = data.items || [];
				var sel = document.getElementById("usis-pb-run-project");
				if (sel) {
					sel.innerHTML = '<option value="">— None —</option>';
					state.projects.forEach(function (p) {
						var opt = document.createElement("option");
						opt.value = p.id;
						var label = (p.number ? p.number + " — " : "") + (p.name || p.id);
						opt.textContent = label;
						sel.appendChild(opt);
					});
				}
				if (cb) cb();
			})
			.catch(function () {
				if (cb) cb();
			});
	}

	function renderTemplateList() {
		var root = document.getElementById("usis-pb-template-list");
		if (!root) return;
		root.innerHTML = "";
		state.templates.forEach(function (t) {
			var a = document.createElement("button");
			a.type = "button";
			a.className =
				"list-group-item list-group-item-action" + (state.selectedId === t.id ? " active" : "");
			a.textContent = t.name + (t.is_active === false ? " (inactive)" : "");
			a.addEventListener("click", function () {
				selectTemplate(t.id);
			});
			root.appendChild(a);
		});
	}

	function renderStepsEditor(steps) {
		var body = document.getElementById("usis-pb-steps-body");
		if (!body) return;
		body.innerHTML = "";
		var rows = steps && steps.length ? steps : [{ title: "", body: "", default_assignee_user_id: null }];
		rows.forEach(function (s, idx) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td>" +
				(idx + 1) +
				'</td><td><input type="text" class="form-control form-control-sm usis-pb-step-title" value="' +
				esc(s.title) +
				'"></td><td><input type="text" class="form-control form-control-sm usis-pb-step-body" value="' +
				esc(s.body || "") +
				'"></td><td><select class="form-select form-select-sm usis-pb-step-user"></select></td><td><button type="button" class="btn btn-sm btn-outline-danger usis-pb-row-del">×</button></td>';
			var sel = tr.querySelector(".usis-pb-step-user");
			var o0 = document.createElement("option");
			o0.value = "";
			o0.textContent = "—";
			sel.appendChild(o0);
			state.users.forEach(function (u) {
				var o = document.createElement("option");
				o.value = u.id;
				o.textContent = (u.email || u.id).slice(0, 40);
				if (s.default_assignee_user_id && u.id === s.default_assignee_user_id) o.selected = true;
				sel.appendChild(o);
			});
			tr.querySelector(".usis-pb-row-del").addEventListener("click", function () {
				tr.remove();
				renumberSteps();
			});
			body.appendChild(tr);
		});
	}

	function renumberSteps() {
		var body = document.getElementById("usis-pb-steps-body");
		if (!body) return;
		var trs = body.querySelectorAll("tr");
		for (var i = 0; i < trs.length; i++) {
			trs[i].cells[0].textContent = String(i + 1);
		}
	}

	function collectStepsPayload() {
		var body = document.getElementById("usis-pb-steps-body");
		if (!body) return [];
		var out = [];
		var trs = body.querySelectorAll("tr");
		for (var i = 0; i < trs.length; i++) {
			var tr = trs[i];
			var title = (tr.querySelector(".usis-pb-step-title") || {}).value || "";
			title = title.trim();
			if (!title) continue;
			var b = (tr.querySelector(".usis-pb-step-body") || {}).value || "";
			var uid = (tr.querySelector(".usis-pb-step-user") || {}).value || "";
			out.push({
				title: title,
				body: b.trim() || null,
				default_assignee_user_id: uid || null,
			});
		}
		return out;
	}

	function selectTemplate(id) {
		state.selectedId = id;
		clearErr();
		renderTemplateList();
		if (!id) return;
		apiFetch("/api/v1/playbooks/templates/" + encodeURIComponent(id))
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				state.templateDetail = data;
				document.getElementById("usis-pb-no-selection").classList.add("d-none");
				document.getElementById("usis-pb-editor").classList.remove("d-none");
				document.getElementById("usis-pb-tpl-name").value = data.item.name || "";
				document.getElementById("usis-pb-tpl-desc").value = data.item.description || "";
				renderStepsEditor(data.steps || []);
			})
			.catch(function (err) {
				showErr("Could not load template: " + (err.message || err));
			});
	}

	function loadTemplates() {
		clearErr();
		apiFetch("/api/v1/playbooks/templates?active_only=0")
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				state.templates = data.items || [];
				renderTemplateList();
				if (state.selectedId) selectTemplate(state.selectedId);
			})
			.catch(function (err) {
				showErr("Could not load templates: " + (err.message || err));
			});
	}

	function saveMeta() {
		if (!state.selectedId) return;
		var name = (document.getElementById("usis-pb-tpl-name").value || "").trim();
		if (!name) {
			showErr("Name is required");
			return;
		}
		clearErr();
		apiFetch("/api/v1/playbooks/templates/" + encodeURIComponent(state.selectedId), {
			method: "PATCH",
			headers: Object.assign({ "Content-Type": "application/json" }, actorHeaders()),
			body: JSON.stringify({
				name: name,
				description: (document.getElementById("usis-pb-tpl-desc").value || "").trim() || null,
			}),
		})
			.then(function (r) {
				if (!r.ok) return r.json().then(function (j) {
					throw new Error(j.error || "HTTP " + r.status);
				});
				return r.json();
			})
			.then(function () {
				loadTemplates();
			})
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function saveSteps() {
		if (!state.selectedId) return;
		clearErr();
		var steps = collectStepsPayload();
		apiFetch("/api/v1/playbooks/templates/" + encodeURIComponent(state.selectedId) + "/steps", {
			method: "PUT",
			headers: Object.assign({ "Content-Type": "application/json" }, actorHeaders()),
			body: JSON.stringify({ steps: steps }),
		})
			.then(function (r) {
				if (!r.ok) return r.json().then(function (j) {
					throw new Error(j.error || "HTTP " + r.status);
				});
				return r.json();
			})
			.then(function () {
				selectTemplate(state.selectedId);
				loadTemplates();
			})
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function newTemplate() {
		clearErr();
		apiFetch("/api/v1/playbooks/templates", {
			method: "POST",
			headers: Object.assign({ "Content-Type": "application/json" }, actorHeaders()),
			body: JSON.stringify({ name: "New checklist template", description: "" }),
		})
			.then(function (r) {
				if (!r.ok) return r.json().then(function (j) {
					throw new Error(j.error || "HTTP " + r.status);
				});
				return r.json();
			})
			.then(function (data) {
				state.selectedId = data.item.id;
				loadTemplates();
				selectTemplate(state.selectedId);
			})
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function loadRuns() {
		var tbody = document.getElementById("usis-pb-runs-body");
		if (!tbody) return;
		tbody.innerHTML = "";
		apiFetch("/api/v1/playbooks/runs?mine=1&open_only=1")
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				var items = data.items || [];
				items.forEach(function (run) {
					var tr = document.createElement("tr");
					var openUrl = "usis-playbook-run.html?run_id=" + encodeURIComponent(run.id);
					tr.innerHTML =
						"<td>" +
						esc(run.title) +
						"</td><td>" +
						esc(run.status) +
						"</td><td>" +
						(run.progress_percent != null ? run.progress_percent : 0) +
						'%</td><td><a class="btn btn-sm btn-outline-primary" href="' +
						openUrl +
						'">Open</a></td>';
					tbody.appendChild(tr);
				});
				if (!items.length) {
					var tr0 = document.createElement("tr");
					tr0.innerHTML = '<td colspan="4" class="text-muted small">No open runs.</td>';
					tbody.appendChild(tr0);
				}
			})
			.catch(function () {
				tbody.innerHTML = '<tr><td colspan="4" class="text-danger small">Could not load runs.</td></tr>';
			});
	}

	function confirmStartRun() {
		if (!state.selectedId) return;
		var title = (document.getElementById("usis-pb-run-title").value || "").trim();
		var pid = (document.getElementById("usis-pb-run-project").value || "").trim();
		var body = { template_id: state.selectedId, title: title || undefined };
		if (pid) body.project_id = pid;
		clearErr();
		apiFetch("/api/v1/playbooks/runs", {
			method: "POST",
			headers: Object.assign({ "Content-Type": "application/json" }, actorHeaders()),
			body: JSON.stringify(body),
		})
			.then(function (r) {
				if (!r.ok) return r.json().then(function (j) {
					throw new Error(j.error || "HTTP " + r.status);
				});
				return r.json();
			})
			.then(function (data) {
				var id = data.item && data.item.id;
				if (id) window.location.href = "usis-playbook-run.html?run_id=" + encodeURIComponent(id);
				else loadRuns();
			})
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function bind() {
		var b;
		b = document.getElementById("usis-pb-refresh-templates");
		if (b) b.addEventListener("click", loadTemplates);
		b = document.getElementById("usis-pb-new-template");
		if (b) b.addEventListener("click", newTemplate);
		b = document.getElementById("usis-pb-save-meta");
		if (b) b.addEventListener("click", saveMeta);
		b = document.getElementById("usis-pb-save-steps");
		if (b) b.addEventListener("click", saveSteps);
		b = document.getElementById("usis-pb-add-step");
		if (b)
			b.addEventListener("click", function () {
				var body = document.getElementById("usis-pb-steps-body");
				if (!body) return;
				var current = [];
				body.querySelectorAll("tr").forEach(function (tr) {
					current.push({
						title: (tr.querySelector(".usis-pb-step-title") || {}).value || "",
						body: (tr.querySelector(".usis-pb-step-body") || {}).value || "",
						default_assignee_user_id: (tr.querySelector(".usis-pb-step-user") || {}).value || null,
					});
				});
				current.push({ title: "", body: "", default_assignee_user_id: null });
				renderStepsEditor(current);
			});
		b = document.getElementById("usis-pb-refresh-runs");
		if (b) b.addEventListener("click", loadRuns);
		b = document.getElementById("usis-pb-confirm-start-run");
		if (b) b.addEventListener("click", confirmStartRun);
	}

	function init() {
		bind();
		loadUsers(function () {
			loadTemplates();
			loadProjects();
			loadRuns();
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
