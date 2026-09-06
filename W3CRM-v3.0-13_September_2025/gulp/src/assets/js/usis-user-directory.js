/**
 * USIS user directory — GET/POST/PATCH /api/v1/admin/users and GET /api/v1/admin/roles.
 */
(function () {
	"use strict";

	var PAGE_SIZE_KEY = "usisUdPageSize";
	var PAGE_SIZES = [25, 50, 100, 200];
	var ACCESS_LEVELS = ["none", "read", "write", "admin"];
	var ACCESS_LABELS = { none: "None", read: "Read", write: "Write", admin: "Admin" };
	var CM_ROLE_ORDER = [
		"admin",
		"executive",
		"project_manager",
		"superintendent",
		"project_engineer",
		"estimator",
		"project_accountant",
		"safety_manager",
		"office_coordinator",
		"field_readonly",
		"website_reviewer",
	];
	var state = {
		users: [],
		roles: [],
		allProjects: [],
		moduleCatalog: [],
		searchTimer: null,
		page: 1,
		limit: 200,
		total: 0,
		meId: "",
		activityDays: 7,
		activityType: "",
		activityUserId: "",
		activityPeople: [],
		activityFeed: [],
		offices: [],
		officesLoaded: false,
	};

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		if (host === "localhost" || host === "127.0.0.1") {
			return (proto + "//" + host + ":5000").replace(/\/$/, "");
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

	function apiFetch(path, opts) {
		opts = opts || {};
		opts.credentials = opts.credentials || "include";
		opts.headers = Object.assign({ Accept: "application/json" }, actorHeaders(), opts.headers || {});
		return fetch(apiBase() + path, opts);
	}

	function authErrorMessage(res, body) {
		if (res.status === 401) {
			return "Your session expired. Sign in again, then retry.";
		}
		if (res.status === 403) {
			return (
				(body && body.error) ||
				"Admin privileges required. Your account must have the admin or superuser role."
			);
		}
		return (body && body.error) || "Request failed (" + res.status + ").";
	}

	function showPageErr(msg) {
		var el = document.getElementById("usis-ud-alert");
		if (!el) return;
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function clearPageErr() {
		var el = document.getElementById("usis-ud-alert");
		if (!el) return;
		el.classList.add("d-none");
		el.textContent = "";
	}

	function modalErr(msg) {
		var el = document.getElementById("usis-ud-modal-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function esc(s) {
		if (s == null) return "";
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function displayName(u) {
		var n = [u.first_name, u.last_name].filter(Boolean).join(" ").trim();
		return n || u.email || u.username || "—";
	}

	function fillOfficeSelect(selectedId) {
		var sel = document.getElementById("usis-ud-modal-office");
		if (!sel) return;
		var html = '<option value="">Company default</option>';
		(state.offices || []).forEach(function (o) {
			html += '<option value="' + esc(o.id) + '">' + esc(o.label || o.name || "Office") + "</option>";
		});
		sel.innerHTML = html;
		sel.value = selectedId || "";
	}

	function loadOffices(selectedId, done) {
		function finish() {
			fillOfficeSelect(selectedId);
			if (done) done();
		}
		if (state.officesLoaded) {
			finish();
			return;
		}
		apiFetch("/api/v1/office-locations")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				state.offices = res.ok && res.body && res.body.items ? res.body.items : [];
				state.officesLoaded = true;
				finish();
			})
			.catch(function () {
				state.offices = [];
				state.officesLoaded = true;
				finish();
			});
	}

	function fmtWhen(iso) {
		if (!iso) return "Never";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return String(iso);
		var sec = (Date.now() - d.getTime()) / 1000;
		var abs = Math.abs(sec);
		var label;
		if (abs < 45) label = "Just now";
		else if (abs < 3600) label = Math.max(1, Math.round(abs / 60)) + " min ago";
		else if (abs < 86400) label = Math.max(1, Math.round(abs / 3600)) + " hr ago";
		else if (abs < 86400 * 7) label = Math.max(1, Math.round(abs / 86400)) + " days ago";
		else
			label = d.toLocaleString(undefined, {
				year: "numeric",
				month: "short",
				day: "numeric",
				hour: "numeric",
				minute: "2-digit",
			});
		return label;
	}

	function fmtWhenTitle(iso) {
		if (!iso) return "Never";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return String(iso);
		return d.toLocaleString();
	}

	function loginLabel(u) {
		if (u.email && u.username) return u.email + " · " + u.username;
		return u.email || u.username || "—";
	}

	function roleLabels(u) {
		var r = u.roles || [];
		if (!r.length) return "—";
		return r
			.map(function (x) {
				return x.code || x.name;
			})
			.join(", ");
	}

	function isApplicantOnly(u) {
		if (!u) return false;
		if (u.is_superuser) return false;
		if (u.is_applicant_only) return true;
		var r = u.roles || [];
		if (!r.length) return false;
		return r.length === 1 && r[0].code === "applicant";
	}

	function renderRoleChecks(selectedIds) {
		var root = document.getElementById("usis-ud-modal-role-checks");
		if (!root) return;
		var set = {};
		(selectedIds || []).forEach(function (id) {
			set[id] = 1;
		});
		if (!state.roles.length) {
			root.innerHTML = '<p class="text-muted small mb-0">No roles in database yet.</p>';
			return;
		}
		var assignable = state.roles.filter(function (r) {
			return r.code !== "applicant";
		});
		root.innerHTML = sortRolesForDisplay(assignable)
			.map(function (r) {
				var chk = set[r.id] ? " checked" : "";
				return (
					'<div class="form-check">' +
					'<input class="form-check-input usis-ud-role-cb" type="checkbox" value="' +
					esc(r.id) +
					'" id="usis-ud-rc-' +
					esc(r.id) +
					'"' +
					chk +
					">" +
					'<label class="form-check-label small" for="usis-ud-rc-' +
					esc(r.id) +
					'">' +
					esc(r.code) +
					" — " +
					esc(r.name) +
					"</label></div>"
				);
			})
			.join("");
	}

	function collectRoleIds() {
		var out = [];
		document.querySelectorAll(".usis-ud-role-cb:checked").forEach(function (cb) {
			out.push(cb.value);
		});
		return out;
	}

	function sortRolesForDisplay(roles) {
		var rank = {};
		CM_ROLE_ORDER.forEach(function (code, i) {
			rank[code] = i;
		});
		return roles.slice().sort(function (a, b) {
			var ra = rank[a.code] != null ? rank[a.code] : 999;
			var rb = rank[b.code] != null ? rank[b.code] : 999;
			if (ra !== rb) return ra - rb;
			return (a.code || "").localeCompare(b.code || "");
		});
	}

	function renderProjectChecks(selectedIds) {
		var root = document.getElementById("usis-ud-modal-project-checks");
		if (!root) return;
		var set = {};
		(selectedIds || []).forEach(function (id) {
			set[id] = 1;
		});
		if (!state.allProjects.length) {
			root.innerHTML =
				'<p class="text-muted small mb-0">No projects loaded. Save the user after projects exist in the directory.</p>';
			return;
		}
		root.innerHTML = state.allProjects
			.map(function (p) {
				var chk = set[p.id] ? " checked" : "";
				var label = (p.number ? p.number + " — " : "") + (p.name || p.id);
				return (
					'<div class="form-check">' +
					'<input class="form-check-input usis-ud-project-cb" type="checkbox" value="' +
					esc(p.id) +
					'" id="usis-ud-pc-' +
					esc(p.id) +
					'"' +
					chk +
					">" +
					'<label class="form-check-label small" for="usis-ud-pc-' +
					esc(p.id) +
					'">' +
					esc(label) +
					"</label></div>"
				);
			})
			.join("");
	}

	function collectProjectIds() {
		var out = [];
		document.querySelectorAll(".usis-ud-project-cb:checked").forEach(function (cb) {
			out.push(cb.value);
		});
		return out;
	}

	function setAllProjectChecks(checked) {
		document.querySelectorAll(".usis-ud-project-cb").forEach(function (cb) {
			cb.checked = !!checked;
		});
	}

	function loadAllProjectsForPicker(cb) {
		if (state.allProjects.length) {
			if (cb) cb(null);
			return;
		}
		apiFetch("/api/v1/projects?limit=2000")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					if (cb) cb((res.body && res.body.error) || "Could not load projects.");
					return;
				}
				state.allProjects = res.body.items || [];
				if (cb) cb(null);
			})
			.catch(function () {
				if (cb) cb("Network error loading projects.");
			});
	}

	function loadUserProjectMemberships(userId, cb) {
		apiFetch("/api/v1/admin/users/" + encodeURIComponent(userId) + "/project-memberships")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					if (cb) cb((res.body && res.body.error) || "Could not load project assignments.");
					return;
				}
				if (cb) cb(null, res.body.project_ids || []);
			})
			.catch(function () {
				if (cb) cb("Network error loading project assignments.");
			});
	}

	function saveUserProjectMemberships(userId, projectIds, cb) {
		apiFetch("/api/v1/admin/users/" + encodeURIComponent(userId) + "/project-memberships", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ project_ids: projectIds }),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					if (cb) cb((res.body && res.body.error) || "Could not save project assignments.");
					return;
				}
				if (cb) cb(null);
			})
			.catch(function () {
				if (cb) cb("Network error saving project assignments.");
			});
	}

	function renderUsersTable() {
		var tb = document.getElementById("usis-ud-users-body");
		if (!tb) return;
		var rows = (state.users || []).filter(function (u) {
			return !isApplicantOnly(u);
		});
		if (!rows.length) {
			tb.innerHTML =
				'<tr><td colspan="8" class="text-muted small">No staff users match this search. Job applicants are listed under Applications.</td></tr>';
			return;
		}
		tb.innerHTML = rows
			.map(function (u) {
				var menuItems = {
					id: u.id,
					editClass: "usis-ud-edit",
					createTarget: "#usis-ud-add",
					remove: u.id !== state.meId,
					deleteClass: "usis-ud-delete",
					extras: [
						{ label: "Activity", className: "usis-ud-activity", data: { id: u.id } },
					],
				};
				var actions =
					window.USISUi && window.USISUi.rowMenu
						? window.USISUi.rowMenu(menuItems)
						: '<button type="button" class="btn btn-sm btn-outline-primary py-0 usis-ud-edit" data-id="' +
							esc(u.id) +
							'">Edit</button>' +
							' <button type="button" class="btn btn-sm btn-outline-secondary py-0 usis-ud-activity" data-id="' +
							esc(u.id) +
							'">Activity</button>' +
							(u.id !== state.meId
								? ' <button type="button" class="btn btn-sm btn-outline-danger py-0 usis-ud-delete" data-id="' +
									esc(u.id) +
									'">Delete</button>'
								: "");
				return (
					"<tr>" +
					"<td>" +
					esc(displayName(u)) +
					"</td>" +
					"<td>" +
					esc(loginLabel(u)) +
					"</td>" +
					"<td><span class=\"small\">" +
					esc(roleLabels(u)) +
					"</span></td>" +
					'<td class="text-center">' +
					(u.is_active ? '<span class="text-success">Yes</span>' : '<span class="text-muted">No</span>') +
					"</td>" +
					'<td class="text-center">' +
					(u.is_superuser ? "Yes" : "—") +
					"</td>" +
					'<td class="text-nowrap" title="' +
					esc(fmtWhenTitle(u.last_login_at)) +
					'">' +
					esc(fmtWhen(u.last_login_at)) +
					"</td>" +
					'<td class="text-nowrap" title="' +
					esc(fmtWhenTitle(u.last_seen_at)) +
					'">' +
					esc(fmtWhen(u.last_seen_at)) +
					"</td>" +
					"<td class=\"text-nowrap\">" +
					actions +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
	}

	function renderRolesTable() {
		var tb = document.getElementById("usis-ud-roles-body");
		if (!tb) return;
		if (!state.roles.length) {
			tb.innerHTML =
				'<tr><td colspan="4" class="text-muted small">No roles returned (check admin access).</td></tr>';
			return;
		}
		tb.innerHTML = state.roles
			.map(function (r) {
				return (
					"<tr><td><code>" +
					esc(r.code) +
					"</code></td><td>" +
					esc(r.name) +
					"</td><td>" +
					esc(r.description || "—") +
					'</td><td class="text-end">' +
					(window.USISUi && window.USISUi.rowMenu
						? window.USISUi.rowMenu({
								id: r.id,
								editClass: "usis-ud-role-edit",
								createTarget: "#usis-ud-role-add",
							})
						: '<button type="button" class="btn btn-sm btn-outline-primary py-0 usis-ud-role-edit" data-id="' +
							esc(r.id) +
							'">Edit</button>') +
					"</td></tr>"
				);
			})
			.join("");
	}

	function roleModalErr(msg) {
		var el = document.getElementById("usis-ud-modal-role-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function roleModal() {
		var el = document.getElementById("usis-ud-modal-role");
		if (!el || typeof bootstrap === "undefined") return null;
		return bootstrap.Modal.getOrCreateInstance(el);
	}

	function loadModuleCatalog(cb) {
		if (state.moduleCatalog.length) {
			if (cb) cb(null);
			return;
		}
		apiFetch("/api/v1/permissions/catalog")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					if (cb) cb((res.body && res.body.error) || "Could not load module catalog.");
					return;
				}
				state.moduleCatalog = res.body.items || [];
				if (cb) cb(null);
			})
			.catch(function () {
				if (cb) cb("Network error loading module catalog.");
			});
	}

	function renderRolePermGrid(permissions) {
		var tb = document.getElementById("usis-ud-modal-role-perms-body");
		if (!tb) return;
		var perms = permissions || {};
		var catalog = state.moduleCatalog.length
			? state.moduleCatalog
			: Object.keys(perms).map(function (code) {
					return { code: code, name: code };
				});
		if (!catalog.length) {
			tb.innerHTML = '<tr><td colspan="2" class="text-muted small">No modules defined.</td></tr>';
			return;
		}
		tb.innerHTML = catalog
			.map(function (m) {
				var code = m.code;
				var cur = perms[code] || "none";
				var opts = ACCESS_LEVELS.map(function (lv) {
					var sel = lv === cur ? " selected" : "";
					return (
						'<option value="' + esc(lv) + '"' + sel + ">" + esc(ACCESS_LABELS[lv] || lv) + "</option>"
					);
				}).join("");
				return (
					"<tr>" +
					"<td>" +
					esc(m.name || code) +
					(m.description ? '<div class="text-muted small">' + esc(m.description) + "</div>" : "") +
					"</td>" +
					'<td><select class="form-select form-select-sm usis-ud-perm-level" data-module="' +
					esc(code) +
					'">' +
					opts +
					"</select></td></tr>"
				);
			})
			.join("");
	}

	function collectRolePermissions() {
		var out = {};
		document.querySelectorAll(".usis-ud-perm-level").forEach(function (sel) {
			var code = sel.getAttribute("data-module");
			if (code) out[code] = sel.value || "none";
		});
		return out;
	}

	function openEditRole(id) {
		var r = null;
		for (var i = 0; i < state.roles.length; i++) {
			if (state.roles[i].id === id) {
				r = state.roles[i];
				break;
			}
		}
		if (!r) return;
		roleModalErr("");
		document.getElementById("usis-ud-modal-role-id").value = r.id;
		document.getElementById("usis-ud-modal-role-title").textContent = "Permissions: " + (r.name || r.code);
		var meta = document.getElementById("usis-ud-modal-role-meta");
		if (meta) meta.textContent = "Role code: " + (r.code || "") + " — controls nav visibility and API access.";
		loadModuleCatalog(function (err) {
			if (err) {
				roleModalErr(err);
				return;
			}
			renderRolePermGrid(r.permissions || {});
			var m = roleModal();
			if (m) m.show();
		});
	}

	function saveRolePermissions() {
		roleModalErr("");
		var id = document.getElementById("usis-ud-modal-role-id").value.trim();
		if (!id) return;
		var perms = collectRolePermissions();
		apiFetch("/api/v1/admin/roles/" + encodeURIComponent(id), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ permissions: perms }),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					roleModalErr(authErrorMessage(res, res.body));
					return;
				}
				if (res.body && res.body.item) {
					for (var i = 0; i < state.roles.length; i++) {
						if (state.roles[i].id === id) {
							state.roles[i] = res.body.item;
							break;
						}
					}
					renderRolesTable();
				}
				var m = roleModal();
				if (m) m.hide();
			})
			.catch(function () {
				roleModalErr("Network error.");
			});
	}

	function guardPageAccess() {
		apiFetch("/api/v1/me")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) return;
				state.meId = (res.body && res.body.item && res.body.item.id) || "";
				var caps = (res.body && res.body.capabilities) || {};
				var mods = caps.modules || {};
				var level = mods.user_admin || "none";
				if (level === "none" && !caps.is_superuser) {
					showPageErr("You do not have access to User admin.");
					var addBtn = document.getElementById("usis-ud-add");
					if (addBtn) addBtn.disabled = true;
				}
				var purgeBtn = document.getElementById("usis-ud-purge-test");
				if (purgeBtn && caps.is_superuser) {
					purgeBtn.classList.remove("d-none");
				}
			})
			.catch(function () {});
	}

	function purgeTestUsers() {
		clearPageErr();
		apiFetch("/api/v1/admin/purge-test-users?sample=8")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					showPageErr(authErrorMessage(res, res.body));
					return;
				}
				var n = res.body.matched || 0;
				if (!n) {
					if (window.USISNotify && window.USISNotify.info) {
						window.USISNotify.info("No pytest test users matched.");
					} else {
						alert("No pytest test users matched.");
					}
					return;
				}
				var sample = (res.body.sample || [])
					.map(function (u) {
						return u.email;
					})
					.join("\n");
				var msg =
					"Delete " +
					n +
					" automated test user(s) (@t.com, @example.com, etc.)?\n\n" +
					"Keeps charles@gousis.com and @godocon.com / @gousis.com accounts.\n\n" +
					(sample ? "Examples:\n" + sample + (res.body.sample_truncated ? "\n…" : "") + "\n\n" : "") +
					"This cannot be undone.";
				if (!window.confirm(msg)) return;
				var includeHr = window.confirm(
					"Also remove HR demo users (hr.demo.employee@usis.local, charles.dossett@usis.local)?\n\nChoose Cancel to skip HR demos."
				);
				return apiFetch("/api/v1/admin/purge-test-users", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ confirm: true, include_hr_demos: includeHr }),
				})
					.then(function (r2) {
						return r2.json().then(function (j2) {
							return { ok: r2.ok, status: r2.status, body: j2 };
						});
					})
					.then(function (res2) {
						if (!res2.ok) {
							showPageErr(authErrorMessage(res2, res2.body));
							return;
						}
						var deleted = res2.body.deleted || 0;
						if (window.USISNotify && window.USISNotify.success) {
							window.USISNotify.success("Removed " + deleted + " test user(s).");
						} else {
							alert("Removed " + deleted + " test user(s).");
						}
						loadUsers(true);
					});
			})
			.catch(function () {
				showPageErr("Network error while purging test users.");
			});
	}

	function loadRoles(cb) {
		apiFetch("/api/v1/admin/roles")
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					state.roles = [];
					if (res.body && res.body.error) {
						if (cb) cb(res.body.error);
					} else if (cb) cb("Could not load roles.");
					return;
				}
				state.roles = res.body.items || [];
				renderRolesTable();
				if (cb) cb(null);
			})
			.catch(function () {
				state.roles = [];
				if (cb) cb("Network error loading roles.");
			});
	}

	function readPageSize() {
		var n = state.limit;
		try {
			var stored = sessionStorage.getItem(PAGE_SIZE_KEY);
			if (stored) {
				n = parseInt(stored, 10);
			}
		} catch (e) {}
		if (PAGE_SIZES.indexOf(n) < 0) {
			n = 50;
		}
		state.limit = n;
		var sel = document.getElementById("usis-ud-page-size");
		if (sel) sel.value = String(n);
	}

	function persistPageSize() {
		try {
			sessionStorage.setItem(PAGE_SIZE_KEY, String(state.limit));
		} catch (e) {}
	}

	function totalPages() {
		if (!state.total) return 1;
		return Math.max(1, Math.ceil(state.total / state.limit));
	}

	function updatePaginationControls() {
		var prev = document.getElementById("usis-ud-prev");
		var next = document.getElementById("usis-ud-next");
		var pages = totalPages();
		if (prev) prev.disabled = state.page <= 1;
		if (next) next.disabled = state.page >= pages;
	}

	function updateUsersMeta() {
		var meta = document.getElementById("usis-ud-users-meta");
		if (!meta) return;
		if (!state.total) {
			meta.textContent = state.users.length ? "No users found." : "";
			return;
		}
		var start = state.total ? (state.page - 1) * state.limit + 1 : 0;
		var end = Math.min(state.page * state.limit, state.total);
		var pages = totalPages();
		meta.textContent =
			"Showing " +
			start +
			"–" +
			end +
			" of " +
			state.total +
			" user(s) · Page " +
			state.page +
			" of " +
			pages;
	}

	function loadUsers(resetPage) {
		clearPageErr();
		if (resetPage) {
			state.page = 1;
		}
		var q = (document.getElementById("usis-ud-search") || {}).value || "";
		var offset = (state.page - 1) * state.limit;
		var qs = "?limit=" + encodeURIComponent(state.limit) + "&offset=" + encodeURIComponent(offset);
		if (q.trim()) qs += "&q=" + encodeURIComponent(q.trim());
		apiFetch("/api/v1/admin/users" + qs)
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					var msg = authErrorMessage(res, res.body);
					showPageErr(msg);
					state.users = [];
					state.total = 0;
					renderUsersTable();
					updatePaginationControls();
					updateUsersMeta();
					return;
				}
				state.users = res.body.items || [];
				state.total = res.body.total != null ? res.body.total : state.users.length;
				if (res.body.limit != null) {
					state.limit = res.body.limit;
				}
				if (state.page > totalPages()) {
					state.page = totalPages();
					if (offset > 0 && state.users.length === 0 && state.total > 0) {
						loadUsers(false);
						return;
					}
				}
				updatePaginationControls();
				updateUsersMeta();
				renderUsersTable();
			})
			.catch(function () {
				showPageErr("Network error loading users.");
				state.users = [];
				state.total = 0;
				renderUsersTable();
				updatePaginationControls();
				updateUsersMeta();
			});
	}

	function setActivityTypeButtons() {
		document.querySelectorAll(".usis-ud-act-type").forEach(function (btn) {
			var on = (btn.getAttribute("data-type") || "") === state.activityType;
			btn.classList.toggle("btn-primary", on);
			btn.classList.toggle("btn-outline-secondary", !on);
		});
	}

	function setActivityDayButtons() {
		document.querySelectorAll(".usis-ud-act-days").forEach(function (btn) {
			var on = String(btn.getAttribute("data-days") || "") === String(state.activityDays);
			btn.classList.toggle("btn-primary", on);
			btn.classList.toggle("btn-outline-secondary", !on);
		});
	}

	function renderActivityPeople() {
		var tb = document.getElementById("usis-ud-activity-people");
		if (!tb) return;
		var rows = state.activityPeople || [];
		if (!rows.length) {
			tb.innerHTML = '<tr><td colspan="6" class="text-muted small">No staff users to show.</td></tr>';
			return;
		}
		tb.innerHTML = rows
			.map(function (u) {
				var active = u.id === state.activityUserId ? " table-active" : "";
				return (
					'<tr class="usis-ud-act-person' +
					active +
					'" data-id="' +
					esc(u.id) +
					'" style="cursor:pointer">' +
					"<td>" +
					esc(u.name || displayName(u)) +
					'<div class="small text-muted">' +
					esc(u.email || u.username || "") +
					"</div></td>" +
					'<td class="text-nowrap" title="' +
					esc(fmtWhenTitle(u.last_login_at)) +
					'">' +
					esc(fmtWhen(u.last_login_at)) +
					"</td>" +
					'<td class="text-nowrap" title="' +
					esc(fmtWhenTitle(u.last_seen_at)) +
					'">' +
					esc(fmtWhen(u.last_seen_at)) +
					"</td>" +
					'<td class="text-end">' +
					esc(u.actions_today || 0) +
					"</td>" +
					'<td class="text-end">' +
					esc(u.actions_period || 0) +
					"</td>" +
					'<td class="text-end">' +
					esc(u.logins_period || 0) +
					"</td></tr>"
				);
			})
			.join("");
	}

	function renderActivityFeed() {
		var tb = document.getElementById("usis-ud-activity-feed");
		if (!tb) return;
		var title = document.getElementById("usis-ud-activity-feed-title");
		var clearBtn = document.getElementById("usis-ud-activity-clear");
		var person = null;
		if (state.activityUserId) {
			for (var i = 0; i < state.activityPeople.length; i++) {
				if (state.activityPeople[i].id === state.activityUserId) {
					person = state.activityPeople[i];
					break;
				}
			}
		}
		if (title) {
			title.textContent = person ? "Activity — " + (person.name || person.email || person.username) : "Recent activity";
		}
		if (clearBtn) clearBtn.classList.toggle("d-none", !state.activityUserId);
		var rows = state.activityFeed || [];
		if (!rows.length) {
			tb.innerHTML = '<tr><td colspan="3" class="text-muted small">No activity in this range yet.</td></tr>';
			return;
		}
		tb.innerHTML = rows
			.map(function (ev) {
				return (
					"<tr><td class=\"text-nowrap\" title=\"" +
					esc(fmtWhenTitle(ev.created_at)) +
					'">' +
					esc(fmtWhen(ev.created_at)) +
					"</td><td>" +
					esc(ev.user_name || ev.user_email || "—") +
					'</td><td>' +
					esc(ev.summary || ev.event_type) +
					(ev.path
						? '<div class="small text-muted text-break">' + esc(ev.path) + "</div>"
						: "") +
					"</td></tr>"
				);
			})
			.join("");
	}

	function loadActivity() {
		setActivityDayButtons();
		setActivityTypeButtons();
		var days = state.activityDays || 7;
		apiFetch("/api/v1/admin/activity/summary?days=" + encodeURIComponent(days))
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					showPageErr(authErrorMessage(res, res.body));
					return;
				}
				state.activityPeople = res.body.items || [];
				renderActivityPeople();
			})
			.catch(function () {
				showPageErr("Network error loading activity.");
			});
		var qs =
			"?days=" +
			encodeURIComponent(days) +
			"&limit=200";
		if (state.activityUserId) qs += "&user_id=" + encodeURIComponent(state.activityUserId);
		if (state.activityType) qs += "&event_type=" + encodeURIComponent(state.activityType);
		apiFetch("/api/v1/admin/activity" + qs)
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) return;
				state.activityFeed = res.body.items || [];
				renderActivityFeed();
			})
			.catch(function () {});
	}

	function showUserActivity(userId) {
		state.activityUserId = userId || "";
		var tab = document.getElementById("usis-ud-tab-activity");
		if (tab && typeof bootstrap !== "undefined") {
			bootstrap.Tab.getOrCreateInstance(tab).show();
		}
		loadActivity();
	}

	function userModal() {
		var el = document.getElementById("usis-ud-modal-user");
		if (!el || typeof bootstrap === "undefined") return null;
		return bootstrap.Modal.getOrCreateInstance(el);
	}

	function openAddUser() {
		modalErr("");
		document.getElementById("usis-ud-modal-title").textContent = "Add user";
		document.getElementById("usis-ud-modal-user-id").value = "";
		document.getElementById("usis-ud-modal-email").value = "";
		document.getElementById("usis-ud-modal-username").value = "";
		document.getElementById("usis-ud-modal-phone").value = "";
		document.getElementById("usis-ud-modal-fn").value = "";
		document.getElementById("usis-ud-modal-ln").value = "";
		loadOffices("");
		document.getElementById("usis-ud-modal-pw").value = "";
		document.getElementById("usis-ud-modal-active").checked = true;
		document.getElementById("usis-ud-modal-super").checked = false;
		var actAdd = document.getElementById("usis-ud-modal-activity");
		if (actAdd) actAdd.textContent = "Last login: — · Last seen: —";
		document.getElementById("usis-ud-modal-email").removeAttribute("readonly");
		var resendAdd = document.getElementById("usis-ud-modal-resend");
		if (resendAdd) resendAdd.classList.add("d-none");
		renderRoleChecks([]);
		loadAllProjectsForPicker(function (err) {
			if (err) modalErr(err);
			renderProjectChecks([]);
		});
		var m = userModal();
		if (m) m.show();
	}

	function openEditUser(id) {
		var u = null;
		for (var i = 0; i < state.users.length; i++) {
			if (state.users[i].id === id) {
				u = state.users[i];
				break;
			}
		}
		if (!u) return;
		modalErr("");
		document.getElementById("usis-ud-modal-title").textContent = "Edit user";
		document.getElementById("usis-ud-modal-user-id").value = u.id;
		document.getElementById("usis-ud-modal-email").value = u.email || "";
		document.getElementById("usis-ud-modal-username").value = u.username || "";
		document.getElementById("usis-ud-modal-phone").value = u.phone || "";
		document.getElementById("usis-ud-modal-fn").value = u.first_name || "";
		document.getElementById("usis-ud-modal-ln").value = u.last_name || "";
		loadOffices(u.office_id || "");
		document.getElementById("usis-ud-modal-pw").value = "";
		document.getElementById("usis-ud-modal-active").checked = !!u.is_active;
		document.getElementById("usis-ud-modal-super").checked = !!u.is_superuser;
		var actEdit = document.getElementById("usis-ud-modal-activity");
		if (actEdit) {
			actEdit.textContent =
				"Last login: " +
				fmtWhen(u.last_login_at) +
				" · Last seen: " +
				fmtWhen(u.last_seen_at);
		}
		var resendEdit = document.getElementById("usis-ud-modal-resend");
		if (resendEdit) {
			if (u.email) resendEdit.classList.remove("d-none");
			else resendEdit.classList.add("d-none");
		}
		var sel = (u.roles || []).map(function (r) {
			return r.id;
		});
		renderRoleChecks(sel);
		loadAllProjectsForPicker(function (err) {
			if (err) {
				modalErr(err);
				renderProjectChecks([]);
				return;
			}
			loadUserProjectMemberships(u.id, function (err2, pids) {
				if (err2) modalErr(err2);
				renderProjectChecks(pids || []);
			});
		});
		var m = userModal();
		if (m) m.show();
	}

	function saveUserModal() {
		modalErr("");
		var id = document.getElementById("usis-ud-modal-user-id").value.trim();
		var email = document.getElementById("usis-ud-modal-email").value.trim();
		var username = (document.getElementById("usis-ud-modal-username") || {}).value || "";
		username = String(username).trim();
		var phone = document.getElementById("usis-ud-modal-phone").value.trim();
		var fn = document.getElementById("usis-ud-modal-fn").value.trim();
		var ln = document.getElementById("usis-ud-modal-ln").value.trim();
		var pw = document.getElementById("usis-ud-modal-pw").value;
		var active = document.getElementById("usis-ud-modal-active").checked;
		var sup = document.getElementById("usis-ud-modal-super").checked;
		var roleIds = collectRoleIds();
		var projectIds = collectProjectIds();
		if (!email && !username) {
			modalErr("Email or username is required.");
			return;
		}
		if (!email && !pw && !id) {
			modalErr("Password is required when the user has no email.");
			return;
		}
		var officeSel = document.getElementById("usis-ud-modal-office");
		var payload = {
			email: email || null,
			username: username || null,
			first_name: fn || null,
			last_name: ln || null,
			phone: phone || null,
			office_id: officeSel && officeSel.value ? officeSel.value : null,
			is_active: active,
			is_superuser: sup,
			role_ids: roleIds,
		};
		if (pw) {
			payload.password = pw;
		}
		var isEdit = !!id;
		var url = "/api/v1/admin/users" + (isEdit ? "/" + encodeURIComponent(id) : "");
		var method = isEdit ? "PATCH" : "POST";
		if (isEdit && !pw) {
			delete payload.password;
		}
		apiFetch(url, {
			method: method,
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					modalErr(authErrorMessage(res, res.body));
					if (res.status === 401) {
						var base = apiBase();
						window.setTimeout(function () {
							window.location.href =
								base + "/auth/login?next=" + encodeURIComponent(window.location.href.split("#")[0]);
						}, 1200);
					}
					return;
				}
				var savedId =
					(res.body && res.body.item && res.body.item.id) ||
					id ||
					(document.getElementById("usis-ud-modal-user-id").value || "").trim();
				if (!savedId) {
					var m0 = userModal();
					if (m0) m0.hide();
					loadUsers();
					return;
				}
				saveUserProjectMemberships(savedId, projectIds, function (err3) {
					if (err3) {
						modalErr(err3);
						return;
					}
					var m = userModal();
					if (m) m.hide();
					loadUsers();
				});
			})
			.catch(function () {
				modalErr("Network error.");
			});
	}

	function inviteResultMessage(body) {
		var inv = (body && body.invite) || {};
		if (inv.sent) return "Invite email sent.";
		if (inv.dry_run) return "Invite recorded (mail is in dry-run; no message was delivered).";
		return (inv.error && String(inv.error)) || (body && body.error) || "Could not send invite.";
	}

	function resendUserInvite() {
		var id = (document.getElementById("usis-ud-modal-user-id").value || "").trim();
		if (!id) return;
		var btn = document.getElementById("usis-ud-modal-resend");
		if (btn) btn.disabled = true;
		modalErr("");
		apiFetch("/api/v1/admin/users/" + encodeURIComponent(id) + "/resend-invite", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: "{}",
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (btn) btn.disabled = false;
				if (!res.ok) {
					modalErr(inviteResultMessage(res.body) || "Could not send invite.");
					return;
				}
				var msg = inviteResultMessage(res.body);
				if (res.body && res.body.invite && (res.body.invite.sent || res.body.invite.dry_run)) {
					if (window.USISNotify && window.USISNotify.success) {
						window.USISNotify.success(msg);
					} else {
						modalErr(msg);
					}
				} else {
					modalErr(msg);
				}
			})
			.catch(function () {
				if (btn) btn.disabled = false;
				modalErr("Network error sending invite.");
			});
	}

	function deleteStaffUser(userId) {
		var u = null;
		for (var i = 0; i < state.users.length; i++) {
			if (state.users[i].id === userId) {
				u = state.users[i];
				break;
			}
		}
		var label = u ? u.email || displayName(u) : "this user";
		if (
			!window.confirm(
				"Permanently delete " +
					label +
					"?\n\nThis removes their login. Job applicants are deleted from Applications, not here."
			)
		) {
			return;
		}
		clearPageErr();
		apiFetch("/api/v1/admin/users/" + encodeURIComponent(userId), {
			method: "DELETE",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ confirm: true }),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					showPageErr((res.body && res.body.error) || "Could not delete user.");
					return;
				}
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success("Deleted " + label + ".");
				}
				loadUsers(false);
			})
			.catch(function () {
				showPageErr("Network error deleting user.");
			});
	}

	function reviewModal() {
		var el = document.getElementById("usis-ud-modal-review");
		if (!el || typeof bootstrap === "undefined") return null;
		return bootstrap.Modal.getOrCreateInstance(el);
	}

	function reviewErr(msg) {
		var el = document.getElementById("usis-ud-review-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function reviewRoleIds() {
		var codes = { website_reviewer: 1, read_only: 1 };
		return state.roles
			.filter(function (r) {
				return codes[r.code];
			})
			.map(function (r) {
				return r.id;
			});
	}

	function collectReviewAccounts() {
		var usernames = document.querySelectorAll(".usis-ud-review-username");
		var fns = document.querySelectorAll(".usis-ud-review-fn");
		var lns = document.querySelectorAll(".usis-ud-review-ln");
		var pws = document.querySelectorAll(".usis-ud-review-pw");
		var out = [];
		for (var i = 0; i < usernames.length; i++) {
			out.push({
				username: (usernames[i].value || "").trim(),
				first_name: (fns[i] && fns[i].value ? fns[i].value.trim() : "") || null,
				last_name: (lns[i] && lns[i].value ? lns[i].value.trim() : "") || null,
				password: pws[i] ? pws[i].value : "",
			});
		}
		return out;
	}

	function createOneReviewUser(account, roleIds, projectIds) {
		return apiFetch("/api/v1/admin/users", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				email: null,
				username: account.username,
				first_name: account.first_name,
				last_name: account.last_name,
				password: account.password,
				is_active: true,
				is_superuser: false,
				role_ids: roleIds,
				send_invite: false,
			}),
		})
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					throw new Error(
						(res.body && res.body.error) ||
							"Could not create " + account.username + " (" + res.status + ")."
					);
				}
				var savedId = res.body && res.body.item && res.body.item.id;
				if (!savedId || !projectIds.length) return account.username;
				return new Promise(function (resolve, reject) {
					saveUserProjectMemberships(savedId, projectIds, function (err) {
						if (err) reject(new Error(err));
						else resolve(account.username);
					});
				});
			});
	}

	function openReviewLogins() {
		reviewErr("");
		var m = reviewModal();
		if (m) m.show();
	}

	function saveReviewLogins() {
		reviewErr("");
		var accounts = collectReviewAccounts();
		if (accounts.length !== 3) {
			reviewErr("Three review accounts are required.");
			return;
		}
		for (var i = 0; i < accounts.length; i++) {
			if (!accounts[i].username) {
				reviewErr("Each review login needs a username.");
				return;
			}
			if (!accounts[i].password || accounts[i].password.length < 8) {
				reviewErr("Each review login needs a password of at least 8 characters.");
				return;
			}
		}
		var roleIds = reviewRoleIds();
		if (!roleIds.length) {
			reviewErr("The website_reviewer role is missing. Refresh roles, then try again.");
			return;
		}
		var btn = document.getElementById("usis-ud-review-save");
		if (btn) btn.disabled = true;
		loadAllProjectsForPicker(function (err) {
			if (err) {
				if (btn) btn.disabled = false;
				reviewErr(err);
				return;
			}
			var projectIds = state.allProjects.map(function (p) {
				return p.id;
			});
			var chain = Promise.resolve();
			accounts.forEach(function (account) {
				chain = chain.then(function () {
					return createOneReviewUser(account, roleIds, projectIds);
				});
			});
			chain
				.then(function () {
					if (btn) btn.disabled = false;
					var m = reviewModal();
					if (m) m.hide();
					if (window.USISNotify && window.USISNotify.success) {
						window.USISNotify.success("Created 3 review logins (dev usernames, no email).");
					}
					loadUsers(true);
				})
				.catch(function (e) {
					if (btn) btn.disabled = false;
					reviewErr((e && e.message) || "Could not create review logins.");
				});
		});
	}

	function t(key) {
		if (window.USISI18n && typeof window.USISI18n.tr === "function") {
			return window.USISI18n.tr(key);
		}
		return key;
	}

	function filenameFromDisposition(header) {
		if (!header) return "";
		var star = /filename\*=UTF-8''([^;]+)/i.exec(header);
		if (star) {
			try {
				return decodeURIComponent(star[1].trim());
			} catch (e) {
				return star[1].trim();
			}
		}
		var m = /filename="?([^";]+)"?/i.exec(header);
		return m ? m[1].trim() : "";
	}

	function setDesktopVersion(text) {
		var ver = document.getElementById("usis-ud-desktop-ver");
		if (!ver) return;
		ver.textContent = text ? " (" + text + ")" : "";
	}

	function loadDesktopApp() {
		var btn = document.getElementById("usis-ud-desktop");
		if (!btn) return;
		apiFetch("/api/v1/admin/desktop-app")
			.then(function (r) {
				return r.json().then(
					function (j) {
						return { ok: r.ok, status: r.status, body: j };
					},
					function () {
						return { ok: r.ok, status: r.status, body: {} };
					}
				);
			})
			.then(function (res) {
				if (!res.ok) {
					btn.disabled = true;
					btn.title =
						(res.body && res.body.error) ||
						"Desktop app download is not available.";
					setDesktopVersion("");
					return;
				}
				var item = (res.body && res.body.item) || {};
				btn.disabled = false;
				btn.title = t("Download the latest Windows installer. Open the file to install or update.");
				setDesktopVersion(item.version || "");
				if (item.filename) btn.setAttribute("data-filename", item.filename);
			})
			.catch(function () {
				btn.disabled = true;
				btn.title = "Desktop app download is not available.";
			});
	}

	function downloadDesktopApp() {
		var btn = document.getElementById("usis-ud-desktop");
		if (!btn || btn.disabled) return;
		var ver = document.getElementById("usis-ud-desktop-ver");
		var prevVer = ver ? ver.textContent : "";
		btn.disabled = true;
		if (ver) ver.textContent = " — " + t("Downloading…");
		clearPageErr();
		apiFetch("/api/v1/admin/desktop-app/download")
			.then(function (r) {
				if (!r.ok) {
					return r.json().then(
						function (j) {
							throw new Error(authErrorMessage(r, j));
						},
						function () {
							throw new Error("Could not download the desktop app (" + r.status + ").");
						}
					);
				}
				var name =
					filenameFromDisposition(r.headers.get("Content-Disposition")) ||
					btn.getAttribute("data-filename") ||
					"USIS-Setup.exe";
				return r.blob().then(function (blob) {
					return { blob: blob, name: name };
				});
			})
			.then(function (file) {
				var a = document.createElement("a");
				a.href = URL.createObjectURL(file.blob);
				a.download = file.name;
				document.body.appendChild(a);
				a.click();
				a.remove();
				setTimeout(function () {
					URL.revokeObjectURL(a.href);
				}, 8000);
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success("Downloaded " + file.name + ". Open the file to install.");
				}
			})
			.catch(function (e) {
				showPageErr((e && e.message) || "Could not download the desktop app.");
			})
			.then(function () {
				btn.disabled = false;
				if (ver) ver.textContent = prevVer;
			});
	}

	function wire() {
		var addBtn = document.getElementById("usis-ud-add");
		if (addBtn) {
			addBtn.addEventListener("click", function (e) {
				e.preventDefault();
				openAddUser();
			});
		}
		var reviewBtn = document.getElementById("usis-ud-review-logins");
		if (reviewBtn) {
			reviewBtn.addEventListener("click", function (e) {
				e.preventDefault();
				openReviewLogins();
			});
		}
		var reviewSave = document.getElementById("usis-ud-review-save");
		if (reviewSave) reviewSave.addEventListener("click", saveReviewLogins);
		var projAll = document.getElementById("usis-ud-projects-all");
		if (projAll) {
			projAll.addEventListener("click", function (e) {
				e.preventDefault();
				setAllProjectChecks(true);
			});
		}
		var projNone = document.getElementById("usis-ud-projects-none");
		if (projNone) {
			projNone.addEventListener("click", function (e) {
				e.preventDefault();
				setAllProjectChecks(false);
			});
		}
		var ref = document.getElementById("usis-ud-refresh");
		if (ref) {
			ref.addEventListener("click", function () {
				loadUsers(false);
			});
		}
		var purgeBtn = document.getElementById("usis-ud-purge-test");
		if (purgeBtn) {
			purgeBtn.addEventListener("click", function () {
				purgeTestUsers();
			});
		}
		var prevBtn = document.getElementById("usis-ud-prev");
		if (prevBtn) {
			prevBtn.addEventListener("click", function () {
				if (state.page > 1) {
					state.page -= 1;
					loadUsers(false);
				}
			});
		}
		var nextBtn = document.getElementById("usis-ud-next");
		if (nextBtn) {
			nextBtn.addEventListener("click", function () {
				if (state.page < totalPages()) {
					state.page += 1;
					loadUsers(false);
				}
			});
		}
		var pageSize = document.getElementById("usis-ud-page-size");
		if (pageSize) {
			pageSize.addEventListener("change", function () {
				var n = parseInt(pageSize.value, 10);
				if (PAGE_SIZES.indexOf(n) < 0) return;
				state.limit = n;
				state.page = 1;
				persistPageSize();
				loadUsers(false);
			});
		}
		var saveBtn = document.getElementById("usis-ud-modal-save");
		if (saveBtn) saveBtn.addEventListener("click", saveUserModal);
		var resendBtn = document.getElementById("usis-ud-modal-resend");
		if (resendBtn) {
			resendBtn.addEventListener("click", function (e) {
				e.preventDefault();
				resendUserInvite();
			});
		}
		var tbody = document.getElementById("usis-ud-users-body");
		if (tbody) tbody.addEventListener("click", function (ev) {
			var b = ev.target.closest(".usis-ud-edit");
			if (b && b.getAttribute("data-id")) {
				openEditUser(b.getAttribute("data-id"));
				return;
			}
			var del = ev.target.closest(".usis-ud-delete");
			if (del && del.getAttribute("data-id")) {
				deleteStaffUser(del.getAttribute("data-id"));
				return;
			}
			var act = ev.target.closest(".usis-ud-activity");
			if (act && act.getAttribute("data-id")) {
				showUserActivity(act.getAttribute("data-id"));
			}
		});
		var search = document.getElementById("usis-ud-search");
		if (search) {
			search.addEventListener("input", function () {
				if (state.searchTimer) clearTimeout(state.searchTimer);
				state.searchTimer = setTimeout(function () {
					loadUsers(true);
				}, 350);
			});
		}
		var rolesTab = document.getElementById("usis-ud-tab-roles");
		if (rolesTab) rolesTab.addEventListener("shown.bs.tab", function () {
			if (!state.roles.length) {
				loadRoles(function (err) {
					if (err) showPageErr(err);
				});
			}
		});
		var activityTab = document.getElementById("usis-ud-tab-activity");
		if (activityTab) {
			activityTab.addEventListener("shown.bs.tab", function () {
				loadActivity();
			});
		}
		document.querySelectorAll(".usis-ud-act-days").forEach(function (btn) {
			btn.addEventListener("click", function () {
				state.activityDays = parseInt(btn.getAttribute("data-days") || "7", 10) || 7;
				loadActivity();
			});
		});
		document.querySelectorAll(".usis-ud-act-type").forEach(function (btn) {
			btn.addEventListener("click", function () {
				state.activityType = btn.getAttribute("data-type") || "";
				loadActivity();
			});
		});
		var peopleBody = document.getElementById("usis-ud-activity-people");
		if (peopleBody) {
			peopleBody.addEventListener("click", function (ev) {
				var row = ev.target.closest(".usis-ud-act-person");
				if (!row) return;
				var id = row.getAttribute("data-id") || "";
				state.activityUserId = id === state.activityUserId ? "" : id;
				loadActivity();
			});
		}
		var clearPerson = document.getElementById("usis-ud-activity-clear");
		if (clearPerson) {
			clearPerson.addEventListener("click", function () {
				state.activityUserId = "";
				loadActivity();
			});
		}
		var rolesBody = document.getElementById("usis-ud-roles-body");
		if (rolesBody) {
			rolesBody.addEventListener("click", function (ev) {
				var b = ev.target.closest(".usis-ud-role-edit");
				if (b && b.getAttribute("data-id")) {
					openEditRole(b.getAttribute("data-id"));
				}
			});
		}
		var roleSaveBtn = document.getElementById("usis-ud-modal-role-save");
		if (roleSaveBtn) roleSaveBtn.addEventListener("click", saveRolePermissions);
		var desktopBtn = document.getElementById("usis-ud-desktop");
		if (desktopBtn) {
			desktopBtn.addEventListener("click", function (e) {
				e.preventDefault();
				downloadDesktopApp();
			});
		}
		readPageSize();
		guardPageAccess();
		loadDesktopApp();
		loadRoles(function (err) {
			if (err) showPageErr(err);
			loadUsers(false);
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
