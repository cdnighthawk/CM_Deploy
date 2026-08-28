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
		document.addEventListener("DOMContentLoaded", refresh);
	} else {
		refresh();
	}
})();
