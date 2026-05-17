/**
 * USIS user directory — GET/POST/PATCH /api/v1/admin/users and GET /api/v1/admin/roles.
 */
(function () {
	"use strict";

	var state = { users: [], roles: [], searchTimer: null };

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
		root.innerHTML = state.roles
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

	function renderUsersTable() {
		var tb = document.getElementById("usis-ud-users-body");
		if (!tb) return;
		if (!state.users.length) {
			tb.innerHTML =
				'<tr><td colspan="7" class="text-muted small">No users match this search, or the list is empty.</td></tr>';
		} else {
			tb.innerHTML = state.users
				.map(function (u) {
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
						'">Edit</button></td>' +
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
			tb.innerHTML = '<tr><td colspan="3" class="text-muted small">No roles returned (check admin access).</td></tr>';
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
					"</td></tr>"
				);
			})
			.join("");
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

	function loadUsers() {
		clearPageErr();
		var q = (document.getElementById("usis-ud-search") || {}).value || "";
		var qs = "?limit=200";
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
					renderUsersTable();
					return;
				}
				state.users = res.body.items || [];
				var meta = document.getElementById("usis-ud-users-meta");
				if (meta) {
					if (res.body.total != null) {
						meta.textContent =
							"Showing " +
							state.users.length +
							" of " +
							res.body.total +
							" user(s). Use search to narrow.";
					} else {
						meta.textContent = state.users.length ? "Showing " + state.users.length + " user(s)." : "";
					}
				}
				renderUsersTable();
			})
			.catch(function () {
				showPageErr("Network error loading users.");
				state.users = [];
				renderUsersTable();
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
				var m = userModal();
				if (m) m.hide();
				loadUsers();
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
		if (ref) ref.addEventListener("click", function () {
			loadUsers();
		});
		var saveBtn = document.getElementById("usis-ud-modal-save");
		if (saveBtn) saveBtn.addEventListener("click", saveUserModal);
		var tbody = document.getElementById("usis-ud-users-body");
		if (tbody) tbody.addEventListener("click", function (ev) {
			var b = ev.target.closest(".usis-ud-edit");
			if (b && b.getAttribute("data-id")) {
				openEditUser(b.getAttribute("data-id"));
			}
		});
		var search = document.getElementById("usis-ud-search");
		if (search) {
			search.addEventListener("input", function () {
				if (state.searchTimer) clearTimeout(state.searchTimer);
				state.searchTimer = setTimeout(function () {
					loadUsers();
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
		loadRoles(function (err) {
			if (err) showPageErr(err);
			loadUsers();
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
