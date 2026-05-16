/**
 * Flask session login/logout URLs from ``window.USIS_API_BASE`` (``elements/meta.html``).
 * Logout uses capture-phase navigation so theme scripts cannot block leaving the shell.
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var h = window.location.hostname || "";
		var local = h === "localhost" || h === "127.0.0.1";
		if (local) {
			return (window.location.protocol + "//" + h + ":5000").replace(/\/$/, "");
		}
		return "http://127.0.0.1:5000";
	}

	/** Post-login URL: ``?next=`` from Flask redirect wins, else dashboard on this host. */
	function shellAfterLoginUrl() {
		var loc = window.location;
		try {
			var u = new URL(loc.href);
			var n = u.searchParams.get("next");
			if (n && String(n).trim()) {
				return String(n).trim();
			}
		} catch (e) {
			/* ignore */
		}
		return loc.protocol + "//" + loc.host + "/usis-dashboard.html";
	}

	function shellAfterLogoutUrl() {
		var loc = window.location;
		var p = (loc.pathname || "").replace(/\\/g, "/").toLowerCase();
		if (
			p.indexOf("page-login") !== -1 ||
			p.indexOf("page-register") !== -1 ||
			p.indexOf("apply.html") !== -1
		) {
			return loc.href.split("#")[0];
		}
		return loc.protocol + "//" + loc.host + "/page-login.html";
	}

	function logoutHref() {
		return apiBase() + "/auth/logout?next=" + encodeURIComponent(shellAfterLogoutUrl());
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
		if (form) {
			form.setAttribute("action", base + "/auth/login");
			var hid = document.getElementById("usis-login-next");
			var v = shellAfterLoginUrl();
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
