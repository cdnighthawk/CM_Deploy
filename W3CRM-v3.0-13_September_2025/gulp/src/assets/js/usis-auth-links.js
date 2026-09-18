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
		if (p.indexOf("apply.html") !== -1 || p.indexOf("/apply/") !== -1) {
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
		var em = (user.email || user.username || "").trim();
		if (em.length) return em.charAt(0).toUpperCase();
		return "—";
	}

	function setHeaderInitials(text) {
		document.querySelectorAll(".usis-header-avatar-initials").forEach(function (el) {
			el.textContent = text || "—";
		});
	}

	function wireOrgSwitcher(body, base) {
		var orgs = (body && body.organizations) || [];
		var current = (body && body.current_organization_id) || "";
		var wraps = document.querySelectorAll(".usis-org-switcher-wrap");
		var selects = document.querySelectorAll(".usis-org-switcher");
		var mustPick = !!(body && body.needs_organization_pick && orgs.length > 1 && !current);
		if (!orgs.length) {
			wraps.forEach(function (el) {
				el.classList.add("d-none");
			});
			return;
		}
		wraps.forEach(function (el) {
			el.classList.remove("d-none");
		});
		selects.forEach(function (sel) {
			sel.disabled = orgs.length < 2;
			if (sel.getAttribute("data-usis-org-wired") === "1") {
				sel.value = current;
				return;
			}
			sel.innerHTML = "";
			if (mustPick) {
				var blank = document.createElement("option");
				blank.value = "";
				blank.textContent = "Select company";
				sel.appendChild(blank);
			}
			orgs.forEach(function (o) {
				var opt = document.createElement("option");
				opt.value = o.id;
				opt.textContent = o.name || o.slug || o.id;
				if (String(o.id) === String(current)) opt.selected = true;
				sel.appendChild(opt);
			});
			sel.setAttribute("data-usis-org-wired", "1");
			sel.addEventListener("change", function () {
				var id = sel.value;
				if (!id || String(id) === String(current)) return;
				fetch(base + "/api/v1/auth/organization", {
					method: "POST",
					credentials: "include",
					headers: { Accept: "application/json", "Content-Type": "application/json" },
					body: JSON.stringify({ organization_id: id }),
				}).then(function (res) {
					if (res.ok) window.location.reload();
				});
			});
		});
	}

	function wireImpersonationBanner(body, base) {
		var imp = body && body.impersonation;
		var existing = document.getElementById("usis-impersonation-banner");
		if (!imp || !imp.active) {
			if (existing) existing.remove();
			return;
		}
		if (!existing) {
			existing = document.createElement("div");
			existing.id = "usis-impersonation-banner";
			existing.className = "usis-impersonation-banner";
			existing.setAttribute("role", "status");
			var wrap = document.getElementById("main-wrapper") || document.body;
			wrap.insertBefore(existing, wrap.firstChild);
		}
		existing.innerHTML =
			'<span>Viewing ' +
			String(imp.tenant_name || "tenant").replace(/</g, "&lt;") +
			' — </span><button type="button" class="btn btn-sm btn-light" id="usis-impersonation-end">End session</button>';
		var btn = document.getElementById("usis-impersonation-end");
		if (btn) {
			btn.onclick = function () {
				fetch(base + "/api/admin/impersonate/end", {
					method: "POST",
					credentials: "include",
					headers: { Accept: "application/json", "Content-Type": "application/json" },
					body: "{}",
				}).then(function () {
					window.location.href = "/admin";
				});
			};
		}
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
				if (!body || !body.authenticated || !body.user) {
					document.querySelectorAll("#usis-public-sign-in").forEach(function (el) {
						el.classList.remove("d-none");
					});
					document.querySelectorAll("#usis-apply-header-user").forEach(function (el) {
						el.classList.add("d-none");
					});
					return;
				}
				document.querySelectorAll("#usis-public-sign-in").forEach(function (el) {
					el.classList.add("d-none");
				});
				document.querySelectorAll("#usis-apply-header-user").forEach(function (el) {
					el.classList.remove("d-none");
				});
				var u = body.user;
				var email = u.email || "";
				var username = u.username || "";
				var name = [u.first_name, u.last_name]
					.filter(function (x) {
						return x && String(x).trim();
					})
					.join(" ")
					.trim();
				if (!name) name = email || username || "—";
				document.querySelectorAll(".usis-header-session-name").forEach(function (el) {
					el.textContent = name;
				});
				document.querySelectorAll(".usis-header-session-email").forEach(function (el) {
					el.textContent = email || username || "—";
				});
				setHeaderInitials(headerInitials(u));
				wireOrgSwitcher(body, base);
				wireImpersonationBanner(body, base);
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

	if (!window.USISI18n) {
		var s = document.createElement("script");
		s.src = (document.querySelector('script[src*="usis-auth-links.js"]') || {}).src
			? (document.querySelector('script[src*="usis-auth-links.js"]').src.replace(/usis-auth-links\.js.*$/, "usis-i18n.js"))
			: "assets/js/usis-i18n.js";
		s.async = false;
		document.head.appendChild(s);
	}

	if (!document.querySelector('script[src*="usis-header-notifications.js"]')) {
		var n = document.createElement("script");
		n.src = (document.querySelector('script[src*="usis-auth-links.js"]') || {}).src
			? (document.querySelector('script[src*="usis-auth-links.js"]').src.replace(/usis-auth-links\.js.*$/, "usis-header-notifications.js?v=20260912a"))
			: "assets/js/usis-header-notifications.js?v=20260912a";
		document.head.appendChild(n);
	}
})();

