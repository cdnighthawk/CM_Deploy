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
		return n || u.email || "—";
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
		root.innerHTML = sortRolesForDisplay(state.roles)
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
		if (!state.users.length) {
			tb.innerHTML =
				'<tr><td colspan="7" class="text-muted small">No users match this search, or the list is empty.</td></tr>';
		} else {
			tb.innerHTML = state.users
				.map(function (u) {
					var applicantActions = "";
					if (isApplicantOnly(u)) {
						applicantActions =
							'<a class="btn btn-sm btn-outline-secondary py-0 me-1" href="usis-hr-application-detail.html?id=' +
							encodeURIComponent(u.id) +
							'">View application</a>' +
							'<button type="button" class="btn btn-sm btn-outline-danger py-0 usis-ud-delete-applicant" data-id="' +
							esc(u.id) +
							'">Delete applicant</button>';
					}
					return (
						"<tr>" +
						"<td>" +
						esc(displayName(u)) +
						"</td>" +
						"<td>" +
						esc(u.email) +
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
						'<td class="text-center">' +
						(u.has_password ? "Yes" : "—") +
						"</td>" +
						'<td><button type="button" class="btn btn-sm btn-outline-primary py-0 usis-ud-edit" data-id="' +
						esc(u.id) +
						'">Edit</button> ' +
						applicantActions +
						"</td>" +
						"</tr>"
					);
				})
				.join("");
		}
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
					'</td><td><button type="button" class="btn btn-sm btn-outline-primary py-0 usis-ud-role-edit" data-id="' +
					esc(r.id) +
					'">Edit</button></td></tr>'
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
		document.getElementById("usis-ud-modal-phone").value = "";
		document.getElementById("usis-ud-modal-fn").value = "";
		document.getElementById("usis-ud-modal-ln").value = "";
		document.getElementById("usis-ud-modal-pw").value = "";
		document.getElementById("usis-ud-modal-active").checked = true;
		document.getElementById("usis-ud-modal-super").checked = false;
		document.getElementById("usis-ud-modal-email").removeAttribute("readonly");
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
		document.getElementById("usis-ud-modal-phone").value = u.phone || "";
		document.getElementById("usis-ud-modal-fn").value = u.first_name || "";
		document.getElementById("usis-ud-modal-ln").value = u.last_name || "";
		document.getElementById("usis-ud-modal-pw").value = "";
		document.getElementById("usis-ud-modal-active").checked = !!u.is_active;
		document.getElementById("usis-ud-modal-super").checked = !!u.is_superuser;
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
		var phone = document.getElementById("usis-ud-modal-phone").value.trim();
		var fn = document.getElementById("usis-ud-modal-fn").value.trim();
		var ln = document.getElementById("usis-ud-modal-ln").value.trim();
		var pw = document.getElementById("usis-ud-modal-pw").value;
		var active = document.getElementById("usis-ud-modal-active").checked;
		var sup = document.getElementById("usis-ud-modal-super").checked;
		var roleIds = collectRoleIds();
		var projectIds = collectProjectIds();
		if (!email) {
			modalErr("Email is required.");
			return;
		}
		var payload = {
			email: email,
			first_name: fn || null,
			last_name: ln || null,
			phone: phone || null,
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

	function wire() {
		var addBtn = document.getElementById("usis-ud-add");
		if (addBtn) {
			addBtn.addEventListener("click", function (e) {
				e.preventDefault();
				openAddUser();
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
		var tbody = document.getElementById("usis-ud-users-body");
		if (tbody) tbody.addEventListener("click", function (ev) {
			var b = ev.target.closest(".usis-ud-edit");
			if (b && b.getAttribute("data-id")) {
				openEditUser(b.getAttribute("data-id"));
				return;
			}
			var del = ev.target.closest(".usis-ud-delete-applicant");
			if (del && del.getAttribute("data-id")) {
				var uid = del.getAttribute("data-id");
				var reason = window.prompt("Reason for deleting this applicant account (required):");
				if (!reason || !String(reason).trim()) return;
				if (!window.confirm("Permanently delete this applicant and all hire data?")) return;
				apiFetch("/api/v1/hr/applications/" + encodeURIComponent(uid), {
					method: "DELETE",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ confirm: true, reason: String(reason).trim() }),
				})
					.then(function (r) {
						return r.json().then(function (j) {
							return { ok: r.ok, body: j };
						});
					})
					.then(function (res) {
						if (!res.ok) throw new Error((res.body && (res.body.error || res.body.message)) || "Delete failed");
						loadUsers(false);
					})
					.catch(function (e) {
						showPageErr(e.message || String(e));
					});
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
		readPageSize();
		guardPageAccess();
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
