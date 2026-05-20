/**
 * Flask session login/logout URLs from ``window.USIS_API_BASE`` (``elements/meta.html``).
 * Logout uses capture-phase navigation so theme scripts cannot block leaving the shell.
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
		var port = String(loc.port || "");
		var protocol = loc.protocol || "";
		if (protocol === "https:" || port === "443" || port === "10000" || port === "") {
			return "";
		}
		if (h === "localhost" || h === "127.0.0.1") {
			return (protocol + "//" + h + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	/** Post-login URL: ``?next=`` from Flask redirect wins, else dashboard or hire wizard. */
	function shellAfterLoginUrl() {
		var loc = window.location;
		try {
			var u = new URL(loc.href);
			var n = u.searchParams.get("next");
			if (n && String(n).trim()) {
				var raw = String(n).trim();
				if (/^https?:\/\//i.test(raw)) return raw;
				if (raw.charAt(0) === "/") return loc.origin + raw;
				return loc.origin + "/" + raw.replace(/^\.\//, "");
			}
		} catch (e) {
			/* ignore */
		}
		if (window.USIS_DEFAULT_AFTER_LOGIN) return window.USIS_DEFAULT_AFTER_LOGIN;
		return loc.protocol + "//" + loc.host + "/usis-dashboard-dark.html";
	}

	function shellAfterLogoutUrl() {
		var loc = window.location;
		var p = (loc.pathname || "").replace(/\\/g, "/").toLowerCase();
		if (
			p.indexOf("page-login") !== -1 ||
			p.indexOf("page-register") !== -1 ||
			p.indexOf("apply.html") !== -1 ||
			p.indexOf("/apply/") !== -1
		) {
			return loc.protocol + "//" + loc.host + "/apply.html";
		}
		return loc.protocol + "//" + loc.host + "/page-login.html";
	}

	function logoutHref() {
		return apiBase() + "/auth/logout?next=" + encodeURIComponent(shellAfterLogoutUrl());
	}

	function headerInitials(user) {
		if (!user) return "—";
		var a = (user.first_name || "").trim().charAt(0);
		var b = (user.last_name || "").trim().charAt(0);
		if (a && b) return (a + b).toUpperCase();
		if (a) return a.toUpperCase();
		var em = (user.email || "").trim();
		if (em.length) return em.charAt(0).toUpperCase();
		return "—";
	}

	function setHeaderInitials(text) {
		document.querySelectorAll(".usis-header-avatar-initials").forEach(function (el) {
			el.textContent = text || "—";
		});
	}

	function refreshSessionHeaderDisplay() {
		var base = apiBase();
		fetch(base + "/api/v1/auth/status", {
			method: "GET",
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json();
			})
			.then(function (body) {
				if (!body || !body.authenticated || !body.user) return;
				var u = body.user;
				var email = u.email || "";
				var name = [u.first_name, u.last_name]
					.filter(function (x) {
						return x && String(x).trim();
					})
					.join(" ")
					.trim();
				if (!name) name = email || "—";
				document.querySelectorAll(".usis-header-session-name").forEach(function (el) {
					el.textContent = name;
				});
				document.querySelectorAll(".usis-header-session-email").forEach(function (el) {
					el.textContent = email || "—";
				});
				setHeaderInitials(headerInitials(u));
			})
			.catch(function () {
				/* ignore */
			});
	}

	function wire() {
		var base = apiBase();
		var nextLogin = encodeURIComponent(shellAfterLoginUrl());
		var nextOut = encodeURIComponent(shellAfterLogoutUrl());
		var outHref = base + "/auth/logout?next=" + nextOut;
		document.querySelectorAll("a.usis-logout-link").forEach(function (a) {
			a.setAttribute("href", outHref);
		});
		document.querySelectorAll("a.usis-flask-login-link").forEach(function (a) {
			a.setAttribute("href", base + "/auth/login?next=" + nextLogin);
		});
		var form = document.getElementById("usis-login-form");
		function applyLoginNext() {
			if (!form) return;
			var v = shellAfterLoginUrl();
			var hid = document.getElementById("usis-login-next");
			if (hid) {
				hid.value = v;
			} else {
				hid = document.createElement("input");
				hid.type = "hidden";
				hid.name = "next";
				hid.id = "usis-login-next";
				hid.value = v;
				form.insertBefore(hid, form.firstChild);
			}
		}
		if (form) {
			form.setAttribute("action", base + "/auth/login");
			applyLoginNext();
		}
		fetch(base + "/api/v1/auth/status", {
			credentials: "include",
			cache: "no-store",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				return r.json();
			})
			.then(function (body) {
				if (body && body.authenticated && body.applicant_only) {
					var loc = window.location;
					var nxt = new URLSearchParams(loc.search).get("next");
					var target = nxt || "apply/application.html";
					if (!/^https?:\/\//i.test(target)) {
						target = loc.origin + "/" + String(target).replace(/^\//, "");
					}
					window.location.replace(target);
					return;
				}
				if (body && body.applicant_only) {
					window.USIS_DEFAULT_AFTER_LOGIN =
						window.location.protocol + "//" + window.location.host + "/apply/application.html";
					applyLoginNext();
				}
			})
			.catch(function () {});
		refreshSessionHeaderDisplay();
	}

	function bindLogoutNav() {
		document.addEventListener(
			"click",
			function (e) {
				var t = e.target;
				if (!t || !t.closest) return;
				var a = t.closest("a.usis-logout-link");
				if (!a) return;
				var dest = a.getAttribute("href");
				if (!dest || dest === "#" || dest.indexOf("javascript:") === 0) {
					dest = logoutHref();
				}
				e.preventDefault();
				e.stopImmediatePropagation();
				window.location.assign(dest);
			},
			true
		);
	}

	bindLogoutNav();

	function runWire() {
		wire();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", runWire);
	} else {
		runWire();
	}
	window.addEventListener("load", runWire);
})();
