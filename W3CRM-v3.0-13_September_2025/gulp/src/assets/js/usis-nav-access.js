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
				'<li><a href="' + prefix + 'usis-time-events.html">Event log</a></li>' +
				'<li><a href="' + prefix + 'usis-time-exceptions.html">Exceptions</a></li>' +
				'<li><a href="' + prefix + 'usis-time-payroll.html">Payroll period</a></li>' +
				'<li><a href="' + prefix + 'usis-time-map.html">Map</a></li>' +
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
		insertHrTimeShortcut();
		insertHeaderTime();
	}

	function insertHrTimeShortcut() {
		var menu = document.getElementById("menu") || document.querySelector(".deznav ul.metismenu");
		if (!menu) return;
		var hr = null;
		var items = menu.children;
		var i;
		for (i = 0; i < items.length; i++) {
			var label = items[i].querySelector(":scope > a .nav-text");
			if (label && (label.textContent || "").trim() === "HR") {
				hr = items[i];
				break;
			}
		}
		if (!hr) return;
		var ul = hr.querySelector(":scope > ul");
		if (!ul) return;
		if (ul.querySelector('a[href*="usis-time-"]')) return;
		var li = document.createElement("li");
		li.innerHTML = '<a href="' + timePrefix() + 'usis-time-live.html" data-i18n="Time">Time</a>';
		ul.appendChild(li);
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

	function insertHeaderTime() {
		if (document.getElementById("usis-header-time")) return;
		var toolbar = document.getElementById("usis-header-toolbar");
		if (!toolbar) return;
		var a = document.createElement("a");
		a.id = "usis-header-time";
		a.className = "btn btn-sm btn-outline-secondary px-2";
		a.href = timePrefix() + "usis-time-live.html";
		a.setAttribute("title", "Time");
		a.setAttribute("aria-label", "Time");
		a.innerHTML =
			'<i class="icon feather icon-clock"></i>' +
			'<span class="d-none d-lg-inline ms-1" data-i18n="Time">Time</span>';
		toolbar.insertBefore(a, toolbar.firstChild);
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
				if (caps.is_superuser) return;
				applyNav(caps.modules || {});
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
