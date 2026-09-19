/**
 * Hide sidebar nav items the signed-in user cannot access (role module permissions).
 */
(function () {
	"use strict";

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

	function timePrefix() {
		var baseEl = document.querySelector("base");
		var baseHref = baseEl ? (baseEl.getAttribute("href") || "") : "";
		if (baseHref.indexOf("..") >= 0) return "";
		var path = (window.location.pathname || "").replace(/\\/g, "/");
		return path.indexOf("/construction/") >= 0 ? "../" : "";
	}

	function insertTimeNav() {
		var menu = document.getElementById("menu") || document.querySelector(".deznav ul.metismenu");
		if (!menu) return;
		if (!document.getElementById("usis-time-nav")) {
			var prefix = timePrefix();
			var li = document.createElement("li");
			li.id = "usis-time-nav";
			li.innerHTML =
				'<a class="has-arrow" href="javascript:void(0);" aria-expanded="false">' +
				'<i class="icon feather icon-clock"></i>' +
				'<span class="nav-text" data-i18n="Time">Time</span></a>' +
				"<ul aria-expanded=\"false\">" +
				'<li><a href="' + prefix + 'usis-time-live.html">Live</a></li>' +
				'<li><a href="' + prefix + 'usis-time-me.html">My Time</a></li>' +
				'<li><a href="' + prefix + 'usis-time-cards.html">Time cards</a></li>' +
				'<li><a href="' + prefix + 'usis-time-payroll.html">Payroll period</a></li>' +
				'<li><a href="' + prefix + 'usis-time-settings.html">Settings</a></li>' +
				"</ul>";
			var safety = null;
			var items = menu.children;
			var i;
			for (i = 0; i < items.length; i++) {
				var label = items[i].querySelector(":scope > a .nav-text");
				if (label && (label.textContent || "").trim() === "Safety") {
					safety = items[i];
					break;
				}
			}
			if (safety && safety.nextSibling) menu.insertBefore(li, safety.nextSibling);
			else menu.appendChild(li);
		}
		retargetDemoTimeSheets();
		insertPeopleNav();
		insertIngestNav();
	}

	function insertIngestNav() {
		var menu = document.getElementById("menu") || document.querySelector(".deznav ul.metismenu");
		if (!menu || document.getElementById("usis-ingest-nav")) return;
		var prefix = timePrefix();
		var li = document.createElement("li");
		li.id = "usis-ingest-nav";
		li.setAttribute("data-usis-module", "estimate");
		li.innerHTML =
			'<a href="' +
			prefix +
			'construction/ingest.html" aria-expanded="false">' +
			'<i class="icon feather icon-download"></i>' +
			'<span class="nav-text" data-i18n="Ingest">Ingest</span></a>';
		var estimate = null;
		var items = menu.children;
		var i;
		for (i = 0; i < items.length; i++) {
			var label = items[i].querySelector(":scope > a .nav-text");
			if (label && (label.textContent || "").trim() === "Estimate") {
				estimate = items[i];
				break;
			}
		}
		if (estimate && estimate.nextSibling) menu.insertBefore(li, estimate.nextSibling);
		else if (estimate) estimate.insertAdjacentElement("afterend", li);
		else menu.appendChild(li);
	}

	function insertPeopleNav() {
		var menu = document.getElementById("menu") || document.querySelector(".deznav ul.metismenu");
		if (!menu) return;
		if (document.getElementById("usis-people-nav")) return;
		var prefix = timePrefix();
		var li = document.createElement("li");
		li.id = "usis-people-nav";
		li.setAttribute("data-usis-module", "hr");
		li.innerHTML =
			'<a class="has-arrow" href="javascript:void(0);" aria-expanded="false">' +
			'<i class="icon feather icon-users"></i>' +
			'<span class="nav-text" data-i18n="People">People</span></a>' +
			'<ul aria-expanded="false">' +
			'<li data-usis-module="hr"><a href="' + prefix + 'usis-people-directory.html">Directory</a></li>' +
			'<li data-usis-module="hr"><a href="' + prefix + 'usis-people-hiring.html">Hiring</a></li>' +
			'<li data-usis-module="hr"><a href="' + prefix + 'usis-hr-applications.html">Applications</a></li>' +
			"</ul>";
		var timeNav = document.getElementById("usis-time-nav");
		if (timeNav && timeNav.nextSibling) menu.insertBefore(li, timeNav.nextSibling);
		else menu.appendChild(li);
	}

	function retargetDemoTimeSheets() {
		var prefix = timePrefix();
		document.querySelectorAll('.deznav a[href*="time-sheet.html"]').forEach(function (a) {
			a.setAttribute("href", prefix + "usis-time-live.html");
			a.textContent = "Time";
			a.setAttribute("data-i18n", "Time");
			var item = a.closest("li");
			if (item) {
				item.style.display = "";
				item.removeAttribute("aria-hidden");
			}
		});
	}

	function applyNav(modules) {
		if (!modules) return;
		document.querySelectorAll("[data-usis-module]").forEach(function (li) {
			var code = li.getAttribute("data-usis-module");
			if (!code) return;
			var level = modules[code] || "none";
			if (level === "none") {
				li.style.display = "none";
				li.setAttribute("aria-hidden", "true");
			} else {
				li.style.display = "";
				li.removeAttribute("aria-hidden");
				if (level === "read") {
					li.classList.add("usis-nav-read-only");
				} else {
					li.classList.remove("usis-nav-read-only");
				}
			}
		});
		document.querySelectorAll(".deznav .metismenu > li").forEach(function (parent) {
			var kids = parent.querySelectorAll(":scope > ul > li[data-usis-module]");
			if (!kids.length) return;
			// Keep a parent that is itself an allowed module link (Projects is tagged
			// data-usis-module="projects" and must stay visible when that module is allowed).
			if (
				parent.getAttribute("data-usis-module") &&
				parent.getAttribute("aria-hidden") !== "true" &&
				parent.style.display !== "none"
			) {
				return;
			}
			var anyVisible = false;
			kids.forEach(function (kid) {
				if (kid.getAttribute("aria-hidden") !== "true" && kid.style.display !== "none") {
					anyVisible = true;
				}
			});
			if (anyVisible) {
				parent.style.display = "";
				parent.removeAttribute("aria-hidden");
			} else {
				parent.style.display = "none";
				parent.setAttribute("aria-hidden", "true");
			}
		});
	}

	function refresh() {
		var base = apiBase();
		fetch(base + "/api/v1/me", { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) return;
				var caps = (res.body && res.body.capabilities) || {};
				var platform = !!caps.is_platform_operator;
				var ents = caps.entitlements || {};
				document.querySelectorAll("#usis-platform-admin-nav, [data-usis-module='platform']").forEach(function (li) {
					if (platform) {
						li.style.display = "";
						li.removeAttribute("aria-hidden");
					} else {
						li.style.display = "none";
						li.setAttribute("aria-hidden", "true");
					}
				});
				if (ents.time === false) {
					var timeNav = document.getElementById("usis-time-nav");
					if (timeNav) {
						timeNav.style.display = "none";
						timeNav.setAttribute("aria-hidden", "true");
					}
				}
				if (ents.hiring === false) {
					document.querySelectorAll('a[href*="people-hiring"], a[href="/people/hiring"]').forEach(function (a) {
						var li = a.closest("li");
						if (li) {
							li.style.display = "none";
							li.setAttribute("aria-hidden", "true");
						}
					});
				}
				if (caps.org_status === "suspended") {
					var wrap = document.getElementById("main-wrapper") || document.body;
					if (!document.getElementById("usis-suspended-banner")) {
						var ban = document.createElement("div");
						ban.id = "usis-suspended-banner";
						ban.className = "alert alert-warning mb-0";
						ban.textContent = "This organization is suspended. Settings are read-only.";
						wrap.insertBefore(ban, wrap.firstChild);
					}
				}
				if (caps.is_superuser) return;
				applyNav(caps.modules || {});
				if (!platform) {
					document.querySelectorAll("#usis-platform-admin-nav, [data-usis-module='platform']").forEach(function (li) {
						li.style.display = "none";
						li.setAttribute("aria-hidden", "true");
					});
				}
			})
			.catch(function () {});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			insertTimeNav();
			refresh();
		});
	} else {
		insertTimeNav();
		refresh();
	}
	window.addEventListener("load", insertTimeNav);
})();
