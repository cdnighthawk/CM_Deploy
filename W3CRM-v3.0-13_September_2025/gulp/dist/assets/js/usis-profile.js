/**
 * My profile: load and PATCH ``/api/v1/me`` (session cookie).
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		var h = loc.hostname || "";
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		if (h === "localhost" || h === "127.0.0.1") {
			return (loc.protocol + "//" + h + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	function fetchErrorMessage(err) {
		if (!err) return "Could not load profile.";
		if (err.message === "Failed to fetch" || err.name === "TypeError") {
			return "Could not reach the API. Check that the backend is running and try again.";
		}
		return err.message || String(err);
	}

	function showAlert(el, msg, kind) {
		if (!el) return;
		el.textContent = msg || "";
		el.className = "alert alert-" + (kind || "info") + (msg ? "" : " d-none");
		if (!msg) el.classList.add("d-none");
		else el.classList.remove("d-none");
	}

	function initials(first, last, email) {
		var a = (first || "").trim().charAt(0);
		var b = (last || "").trim().charAt(0);
		if (a && b) return (a + b).toUpperCase();
		if (a) return a.toUpperCase();
		var em = (email || "").trim();
		if (em.length) return em.charAt(0).toUpperCase();
		return "?";
	}

	function roleLine(roles) {
		if (!roles || !roles.length) return "Roles: —";
		var parts = roles.map(function (r) {
			return r.name || r.code || "";
		}).filter(Boolean);
		return "Roles: " + (parts.length ? parts.join(", ") : "—");
	}

	function fillOfficeSelect(offices, selectedId) {
		var sel = document.getElementById("usis-pf-office");
		if (!sel) return;
		var html = '<option value="">Company default</option>';
		(offices || []).forEach(function (o) {
			var label = o.label || o.name || "Office";
			html += '<option value="' + String(o.id || "").replace(/"/g, "&quot;") + '">' + String(label).replace(/</g, "&lt;") + "</option>";
		});
		sel.innerHTML = html;
		sel.value = selectedId || "";
	}

	function loadOffices(selectedId) {
		return fetch(apiBase() + "/api/v1/office-locations", {
			method: "GET",
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json().then(function (body) {
					if (!res.ok) throw new Error((body && body.error) || res.statusText);
					return body.items || [];
				});
			})
			.then(function (items) {
				fillOfficeSelect(items, selectedId);
			})
			.catch(function () {
				fillOfficeSelect([], selectedId);
			});
	}

	function loadProfile() {
		var alertEl = document.getElementById("usis-profile-alert");
		return fetch(apiBase() + "/api/v1/me", {
			method: "GET",
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				if (res.status === 401) {
					window.location.href = apiBase() + "/auth/login?next=" + encodeURIComponent(window.location.href.split("#")[0]);
					return Promise.reject(new Error("unauthorized"));
				}
				return res.json().then(function (body) {
					if (!res.ok) throw new Error((body && body.error) || res.statusText);
					return body.item;
				});
			})
			.then(function (u) {
				document.getElementById("usis-pf-first").value = u.first_name || "";
				document.getElementById("usis-pf-last").value = u.last_name || "";
				document.getElementById("usis-pf-email").value = u.email || "";
				document.getElementById("usis-pf-phone").value = u.phone || "";
				loadOffices(u.office_id || "");
				document.getElementById("usis-pf-password").value = "";
				document.getElementById("usis-pf-password2").value = "";
				var name = [u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.email;
				document.getElementById("usis-profile-card-name").textContent = name;
				document.getElementById("usis-profile-card-email").textContent = u.email || "";
				document.getElementById("usis-profile-card-roles").textContent = roleLine(u.roles);
				var ini = initials(u.first_name, u.last_name, u.email);
				document.getElementById("usis-profile-avatar-initials").textContent = ini;
				if (u.is_superuser) {
					document.getElementById("usis-profile-card-roles").textContent += " · Superuser";
				}
				showAlert(alertEl, "", "info");
			})
			.catch(function (e) {
				if (e && e.message === "unauthorized") return;
				showAlert(alertEl, fetchErrorMessage(e), "danger");
			});
	}

	function saveProfile(ev) {
		ev.preventDefault();
		var alertEl = document.getElementById("usis-profile-alert");
		var p1 = document.getElementById("usis-pf-password").value;
		var p2 = document.getElementById("usis-pf-password2").value;
		if (p1 || p2) {
			if (p1 !== p2) {
				showAlert(alertEl, "New password and confirmation do not match.", "danger");
				return;
			}
		}
		var officeSel = document.getElementById("usis-pf-office");
		var body = {
			email: document.getElementById("usis-pf-email").value.trim(),
			first_name: document.getElementById("usis-pf-first").value.trim() || null,
			last_name: document.getElementById("usis-pf-last").value.trim() || null,
			phone: document.getElementById("usis-pf-phone").value.trim() || null,
			office_id: officeSel && officeSel.value ? officeSel.value : null,
		};
		if (p1) body.password = p1;
		var btn = document.getElementById("usis-pf-save");
		if (btn) btn.disabled = true;
		fetch(apiBase() + "/api/v1/me", {
			method: "PATCH",
			credentials: "include",
			headers: { Accept: "application/json", "Content-Type": "application/json" },
			body: JSON.stringify(body),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error((j && j.error) || res.statusText);
					return j.item;
				});
			})
			.then(function (u) {
				showAlert(alertEl, "Profile saved.", "success");
				if (window.USISNotify && typeof window.USISNotify.success === "function") {
					window.USISNotify.success("Profile saved.");
				}
				document.getElementById("usis-pf-password").value = "";
				document.getElementById("usis-pf-password2").value = "";
				var name = [u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.email;
				document.getElementById("usis-profile-card-name").textContent = name;
				document.getElementById("usis-profile-card-email").textContent = u.email || "";
				document.getElementById("usis-profile-card-roles").textContent = roleLine(u.roles);
				if (u.is_superuser) {
					document.getElementById("usis-profile-card-roles").textContent += " · Superuser";
				}
				document.getElementById("usis-profile-avatar-initials").textContent = initials(
					u.first_name,
					u.last_name,
					u.email
				);
			})
			.catch(function (e) {
				var msg = fetchErrorMessage(e) || "Save failed.";
				showAlert(alertEl, msg, "danger");
				if (window.USISNotify && typeof window.USISNotify.error === "function") {
					window.USISNotify.error(msg);
				}
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	function init() {
		var form = document.getElementById("usis-profile-form");
		if (!form) return;
		if (form.getAttribute("data-usis-profile-wired") === "1") {
			loadProfile();
			return;
		}
		form.setAttribute("data-usis-profile-wired", "1");
		loadProfile();
		form.addEventListener("submit", saveProfile);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
	window.USISProfileInit = init;
})();
