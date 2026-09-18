/**
 * Platform contractor onboarding — GET/POST /api/v1/platform/organizations.
 */
(function () {
	"use strict";

	var inviteOnly = false;

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

	function esc(s) {
		if (s == null) return "";
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function showFlash(msg, kind) {
		var el = document.getElementById("usis-pc-flash");
		if (!el) return;
		el.textContent = msg || "";
		el.className = "alert py-2 px-3 mb-3 alert-" + (kind || "success");
		if (!msg) el.classList.add("d-none");
		else el.classList.remove("d-none");
	}

	function modalErr(msg) {
		var el = document.getElementById("usis-pc-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
			el.textContent = "";
		}
	}

	function setForbidden(on) {
		var box = document.getElementById("usis-pc-forbidden");
		var header = document.getElementById("usis-pc-header");
		var card = document.getElementById("usis-pc-card");
		if (box) box.classList.toggle("d-none", !on);
		if (header) header.classList.toggle("d-none", on);
		if (card) card.classList.toggle("d-none", on);
	}

	function inviteMessage(body) {
		if (!body) return "Invite sent.";
		if (body.email_sent) return "Set-password email sent.";
		if (body.dry_run) return "Invite created (email dry-run; no message was sent).";
		return "Invite created. Check mail settings if the admin did not receive a link.";
	}

	function parseError(res, body) {
		if (res.status === 401) return "Your session expired. Sign in again, then retry.";
		if (res.status === 403) return (body && body.error) || "Platform administrator required.";
		return (body && body.error) || "Request failed (" + res.status + ").";
	}

	function jsonOrEmpty(res) {
		return res.json().catch(function () {
			return {};
		});
	}

	function renderRows(items) {
		var tbody = document.getElementById("usis-pc-tbody");
		if (!tbody) return;
		if (!items || !items.length) {
			tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No contractor companies yet.</td></tr>';
			return;
		}
		tbody.innerHTML = items
			.map(function (o) {
				var id = esc(o.id);
				var sso = o.microsoft_sso_enabled ? "Yes" : "No";
				return (
					"<tr>" +
					"<td>" +
					esc(o.name) +
					"</td>" +
					"<td><code>" +
					esc(o.slug) +
					"</code></td>" +
					"<td>" +
					sso +
					"</td>" +
					'<td class="text-end"><button type="button" class="btn btn-sm btn-outline-primary" data-usis-pc-invite="' +
					id +
					'" data-usis-pc-name="' +
					esc(o.name) +
					'">Invite admin</button></td>' +
					"</tr>"
				);
			})
			.join("");
	}

	function loadOrgs() {
		var tbody = document.getElementById("usis-pc-tbody");
		if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Loading…</td></tr>';
		return apiFetch("/api/v1/platform/organizations")
			.then(function (res) {
				return jsonOrEmpty(res).then(function (body) {
					return { res: res, body: body };
				});
			})
			.then(function (pack) {
				if (pack.res.status === 403 || pack.res.status === 401) {
					setForbidden(true);
					return;
				}
				if (!pack.res.ok) {
					setForbidden(false);
					showFlash(parseError(pack.res, pack.body), "danger");
					return;
				}
				setForbidden(false);
				renderRows(pack.body.items || []);
			})
			.catch(function () {
				showFlash("Could not load contractor companies.", "danger");
			});
	}

	function modalEl() {
		return document.getElementById("usis-pc-modal");
	}

	function showModal() {
		var el = modalEl();
		if (!el || !window.bootstrap) return;
		window.bootstrap.Modal.getOrCreateInstance(el).show();
	}

	function hideModal() {
		var el = modalEl();
		if (!el || !window.bootstrap) return;
		var inst = window.bootstrap.Modal.getInstance(el);
		if (inst) inst.hide();
	}

	function openCreate() {
		inviteOnly = false;
		modalErr("");
		document.getElementById("usis-pc-modal-title").textContent = "Add contractor";
		document.getElementById("usis-pc-save").textContent = "Create and invite";
		document.getElementById("usis-pc-org-id").value = "";
		document.getElementById("usis-pc-name").value = "";
		document.getElementById("usis-pc-first").value = "";
		document.getElementById("usis-pc-last").value = "";
		document.getElementById("usis-pc-email").value = "";
		document.getElementById("usis-pc-catalog").checked = true;
		document.getElementById("usis-pc-name-wrap").classList.remove("d-none");
		document.getElementById("usis-pc-catalog-wrap").classList.remove("d-none");
		showModal();
	}

	function openInvite(orgId, name) {
		inviteOnly = true;
		modalErr("");
		document.getElementById("usis-pc-modal-title").textContent = "Invite admin — " + (name || "contractor");
		document.getElementById("usis-pc-save").textContent = "Send invite";
		document.getElementById("usis-pc-org-id").value = orgId || "";
		document.getElementById("usis-pc-name").value = name || "";
		document.getElementById("usis-pc-first").value = "";
		document.getElementById("usis-pc-last").value = "";
		document.getElementById("usis-pc-email").value = "";
		document.getElementById("usis-pc-name-wrap").classList.add("d-none");
		document.getElementById("usis-pc-catalog-wrap").classList.add("d-none");
		showModal();
	}

	function postJson(path, payload) {
		return apiFetch(path, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(payload),
		}).then(function (res) {
			return jsonOrEmpty(res).then(function (body) {
				return { res: res, body: body };
			});
		});
	}

	function inviteAdmin(orgId, first, last, email) {
		return postJson("/api/v1/platform/organizations/" + encodeURIComponent(orgId) + "/invites", {
			email: email,
			first_name: first,
			last_name: last,
		});
	}

	function save() {
		var email = (document.getElementById("usis-pc-email").value || "").trim().toLowerCase();
		var first = (document.getElementById("usis-pc-first").value || "").trim();
		var last = (document.getElementById("usis-pc-last").value || "").trim();
		modalErr("");
		if (!email || email.indexOf("@") < 0) {
			modalErr("Admin email is required.");
			return;
		}
		var btn = document.getElementById("usis-pc-save");
		btn.disabled = true;
		var done = function () {
			btn.disabled = false;
		};

		if (inviteOnly) {
			var existingId = document.getElementById("usis-pc-org-id").value;
			if (!existingId) {
				modalErr("Missing company id.");
				done();
				return;
			}
			inviteAdmin(existingId, first, last, email)
				.then(function (pack) {
					if (!pack.res.ok) {
						modalErr(parseError(pack.res, pack.body));
						return;
					}
					hideModal();
					showFlash(inviteMessage(pack.body), "success");
					return loadOrgs();
				})
				.catch(function () {
					modalErr("Could not send invite.");
				})
				.then(done, done);
			return;
		}

		var name = (document.getElementById("usis-pc-name").value || "").trim();
		if (!name) {
			modalErr("Company name is required.");
			done();
			return;
		}
		var copyCatalog = document.getElementById("usis-pc-catalog").checked;
		postJson("/api/v1/platform/organizations", { name: name, copy_catalog: copyCatalog })
			.then(function (created) {
				if (!created.res.ok) {
					modalErr(parseError(created.res, created.body));
					return null;
				}
				var org = (created.body && created.body.item) || {};
				if (!org.id) {
					modalErr("Company was created but no id was returned.");
					return null;
				}
				return inviteAdmin(org.id, first, last, email).then(function (inv) {
					if (!inv.res.ok) {
						modalErr(
							"Company created, but invite failed: " + parseError(inv.res, inv.body)
						);
						return loadOrgs();
					}
					hideModal();
					showFlash("Contractor created. " + inviteMessage(inv.body), "success");
					return loadOrgs();
				});
			})
			.catch(function () {
				modalErr("Could not create contractor.");
			})
			.then(done, done);
	}

	function checkAccessThenLoad() {
		return apiFetch("/api/v1/me")
			.then(function (res) {
				return jsonOrEmpty(res).then(function (body) {
					return { res: res, body: body };
				});
			})
			.then(function (pack) {
				var caps = (pack.body && pack.body.capabilities) || {};
				if (!pack.res.ok || !caps.is_superuser) {
					setForbidden(true);
					return;
				}
				setForbidden(false);
				return loadOrgs();
			})
			.catch(function () {
				setForbidden(true);
			});
	}

	function wire() {
		var addBtn = document.getElementById("usis-pc-add");
		if (addBtn) addBtn.addEventListener("click", openCreate);
		var refresh = document.getElementById("usis-pc-refresh");
		if (refresh) refresh.addEventListener("click", loadOrgs);
		var saveBtn = document.getElementById("usis-pc-save");
		if (saveBtn) saveBtn.addEventListener("click", save);
		var tbody = document.getElementById("usis-pc-tbody");
		if (tbody) {
			tbody.addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-usis-pc-invite]");
				if (!btn) return;
				openInvite(btn.getAttribute("data-usis-pc-invite"), btn.getAttribute("data-usis-pc-name"));
			});
		}
		checkAccessThenLoad();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
