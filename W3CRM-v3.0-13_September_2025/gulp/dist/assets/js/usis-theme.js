/**
 * Site-wide light/dark theme toggle (persists in localStorage).
 */
(function (global) {
	"use strict";

	var boot = global.USISThemeBoot;
	var STORAGE_KEY = boot ? boot.STORAGE_KEY : "usis-color-scheme";

	function readStored() {
		if (boot && boot.readStored) {
			return boot.readStored();
		}
		try {
			var v = global.localStorage.getItem(STORAGE_KEY);
			if (v === "light" || v === "dark") {
				return v;
			}
		} catch (e) { /* ignore */ }
		return null;
	}

	function get() {
		var body = global.document.body;
		if (body) {
			var attr = body.getAttribute("data-bs-theme");
			if (attr === "light" || attr === "dark") {
				return attr;
			}
		}
		return boot && boot.resolve ? boot.resolve() : "light";
	}

	function applyDom(theme) {
		if (boot && boot.apply) {
			boot.apply(theme);
			return;
		}
		var body = global.document.body;
		if (body) {
			body.setAttribute("data-theme-version", theme);
			body.setAttribute("data-bs-theme", theme);
		}
		global.document.documentElement.setAttribute("data-theme-version", theme);
		global.document.documentElement.setAttribute("data-bs-theme", theme);
	}

	function syncDeznav(theme) {
		if (typeof global.dzSettingsOptions !== "undefined") {
			global.dzSettingsOptions.version = theme;
		}
	}

	function syncToggleButton(theme) {
		var btn = global.document.getElementById("usis-theme-toggle");
		if (!btn) {
			return;
		}
		var isDark = theme === "dark";
		btn.setAttribute("aria-pressed", isDark ? "true" : "false");
		btn.setAttribute(
			"aria-label",
			isDark ? "Switch to light mode" : "Switch to dark mode"
		);
		btn.setAttribute(
			"title",
			isDark ? "Switch to light mode" : "Switch to dark mode"
		);
		var moon = btn.querySelector("[data-usis-icon-dark]");
		var sun = btn.querySelector("[data-usis-icon-light]");
		if (moon) {
			moon.classList.toggle("d-none", isDark);
		}
		if (sun) {
			sun.classList.toggle("d-none", !isDark);
		}
	}

	function set(theme) {
		if (theme !== "light" && theme !== "dark") {
			return;
		}
		try {
			global.localStorage.setItem(STORAGE_KEY, theme);
		} catch (e) { /* ignore */ }
		applyDom(theme);
		syncDeznav(theme);
		syncToggleButton(theme);
		global.dispatchEvent(
			new CustomEvent("usis-theme-change", { detail: { theme: theme } })
		);
	}

	function toggle() {
		set(get() === "dark" ? "light" : "dark");
	}

	function bindToggle() {
		var btn = global.document.getElementById("usis-theme-toggle");
		if (!btn || btn.getAttribute("data-usis-theme-bound") === "1") {
			return;
		}
		btn.setAttribute("data-usis-theme-bound", "1");
		btn.addEventListener("click", function (ev) {
			ev.preventDefault();
			toggle();
		});
	}

	function ensureAuthToggle() {
		if (global.document.getElementById("usis-theme-toggle")) {
			return;
		}
		if (!global.document.querySelector(".auth-wrapper")) {
			return;
		}
		var btn = global.document.createElement("button");
		btn.type = "button";
		btn.id = "usis-theme-toggle";
		btn.className = "btn btn-outline-secondary btn-sm position-fixed shadow-sm";
		btn.style.top = "1rem";
		btn.style.right = "1rem";
		btn.style.zIndex = "1050";
		btn.innerHTML =
			'<i class="icon feather icon-moon" data-usis-icon-dark aria-hidden="true"></i>' +
			'<i class="icon feather icon-sun d-none" data-usis-icon-light aria-hidden="true"></i>';
		global.document.body.appendChild(btn);
	}

	function init() {
		var theme = readStored() || get();
		applyDom(theme);
		syncDeznav(theme);
		ensureAuthToggle();
		syncToggleButton(theme);
		bindToggle();
	}

	global.USISTheme = {
		get: get,
		set: set,
		toggle: toggle,
	};

	if (global.document.readyState === "loading") {
		global.document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})(window);
