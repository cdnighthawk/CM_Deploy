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

	function syncSetThemeButtons(theme) {
		var buttons = global.document.querySelectorAll("[data-usis-set-theme]");
		var i;
		var btn;
		var on;
		for (i = 0; i < buttons.length; i++) {
			btn = buttons[i];
			on = btn.getAttribute("data-usis-set-theme") === theme;
			btn.classList.toggle("active", on);
			btn.setAttribute("aria-pressed", on ? "true" : "false");
			if (btn.classList.contains("btn")) {
				btn.classList.toggle("btn-primary", on);
				btn.classList.toggle("btn-outline-secondary", !on);
			}
		}
	}

	function syncToggleButton(theme) {
		var btn = global.document.getElementById("usis-theme-toggle");
		syncSetThemeButtons(theme);
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

	function ensureDropdownTheme() {
		if (global.document.querySelector("[data-usis-profile-theme]")) {
			return;
		}
		var menu = global.document.querySelector(".header-profile-dropdown .dropdown-menu");
		if (!menu) {
			return;
		}
		var li = global.document.createElement("li");
		li.setAttribute("data-usis-profile-theme", "1");
		li.innerHTML =
			'<div class="px-3 py-2">' +
			'<div class="small text-muted mb-1" data-i18n="Appearance">Appearance</div>' +
			'<div class="btn-group btn-group-sm w-100" role="group" aria-label="Appearance">' +
			'<button type="button" class="btn btn-outline-secondary" data-usis-set-theme="light" data-i18n="Light">Light</button>' +
			'<button type="button" class="btn btn-outline-secondary" data-usis-set-theme="dark" data-i18n="Dark">Dark</button>' +
			"</div></div>";
		var lang = menu.querySelector("[data-usis-profile-lang]");
		if (lang && lang.parentNode) {
			if (lang.nextSibling) {
				lang.parentNode.insertBefore(li, lang.nextSibling);
			} else {
				lang.parentNode.appendChild(li);
			}
			return;
		}
		var logout = menu.querySelector(".usis-logout-link");
		var logoutLi = logout ? logout.closest("li") : null;
		if (logoutLi && logoutLi.parentNode) {
			logoutLi.parentNode.insertBefore(li, logoutLi);
			return;
		}
		menu.appendChild(li);
	}

	function hideStandaloneHeaderToggle() {
		if (!global.document.querySelector("[data-usis-profile-theme]")) {
			return;
		}
		var btn = global.document.getElementById("usis-theme-toggle");
		if (!btn || btn.closest(".header-profile-dropdown") || btn.closest(".auth-wrapper")) {
			return;
		}
		var item = btn.closest("li.nav-item") || btn;
		item.classList.add("d-none");
		item.setAttribute("hidden", "");
	}

	function bindSetThemeButtons() {
		var buttons = global.document.querySelectorAll("[data-usis-set-theme]");
		var i;
		for (i = 0; i < buttons.length; i++) {
			if (buttons[i].getAttribute("data-usis-theme-bound") === "1") {
				continue;
			}
			buttons[i].setAttribute("data-usis-theme-bound", "1");
			buttons[i].addEventListener("click", function (ev) {
				ev.preventDefault();
				set(this.getAttribute("data-usis-set-theme"));
			});
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

	function ensureUiJs() {
		if (global.USISUi) {
			return;
		}
		var existing = global.document.querySelector('script[src*="usis-ui.js"]');
		if (existing) {
			return;
		}
		var marker = global.document.querySelector('script[src*="usis-theme.js"]');
		var src = "assets/js/usis-ui.js";
		if (marker && marker.getAttribute("src")) {
			src = marker.getAttribute("src").replace("usis-theme.js", "usis-ui.js");
		}
		var s = global.document.createElement("script");
		s.src = src;
		s.defer = true;
		(marker && marker.parentNode ? marker.parentNode : global.document.head || global.document.body).appendChild(s);
	}

	function init() {
		var theme = readStored() || get();
		applyDom(theme);
		syncDeznav(theme);
		ensureAuthToggle();
		ensureDropdownTheme();
		hideStandaloneHeaderToggle();
		syncToggleButton(theme);
		bindToggle();
		bindSetThemeButtons();
		if (global.USISI18n && typeof global.USISI18n.apply === "function") {
			try {
				global.USISI18n.apply(global.USISI18n.getLang());
			} catch (e) { /* ignore */ }
		}
		ensureUiJs();
		if (boot && typeof boot.apply === "function") {
			/* usis-theme-boot already applied theme; re-pin UI CSS last. */
		}
		if (global.document && global.document.head) {
			var pin = global.document.querySelector('link[href*="usis-ui.css"]');
			if (pin && pin.parentNode === global.document.head) {
				global.document.head.appendChild(pin);
			}
		}
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
