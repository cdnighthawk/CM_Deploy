/**
 * Apply saved color scheme before first paint (included from elements/meta.html).
 */
(function (global) {
	"use strict";

	var STORAGE_KEY = "usis-color-scheme";

	function readStored() {
		try {
			var v = global.localStorage.getItem(STORAGE_KEY);
			if (v === "light" || v === "dark") {
				return v;
			}
		} catch (e) { /* private mode */ }
		return null;
	}

	function systemPrefersDark() {
		return global.matchMedia && global.matchMedia("(prefers-color-scheme: dark)").matches;
	}

	function resolveTheme() {
		return readStored() || (systemPrefersDark() ? "dark" : "light");
	}

	function applyToEl(el, theme) {
		if (!el) {
			return;
		}
		el.setAttribute("data-theme-version", theme);
		el.setAttribute("data-bs-theme", theme);
	}

	function apply(theme) {
		var doc = global.document;
		if (!doc) {
			return;
		}
		applyToEl(doc.documentElement, theme);
		applyToEl(doc.body, theme);
	}

	function ensureUiCss() {
		var doc = global.document;
		if (!doc || !doc.head) {
			return;
		}
		var existing = doc.querySelectorAll('link[href*="usis-ui.css"]');
		var i;
		for (i = 0; i < existing.length; i++) {
			existing[i].parentNode.removeChild(existing[i]);
		}
		var link = doc.createElement("link");
		link.rel = "stylesheet";
		link.href = "assets/css/usis-ui.css?v=20260902a";
		doc.head.appendChild(link);
	}

	var theme = resolveTheme();
	applyToEl(global.document.documentElement, theme);
	ensureUiCss();
	if (global.document.readyState === "loading") {
		global.document.addEventListener("DOMContentLoaded", ensureUiCss);
	} else {
		ensureUiCss();
	}

	if (global.document.body) {
		applyToEl(global.document.body, theme);
	} else {
		global.document.addEventListener("DOMContentLoaded", function () {
			applyToEl(global.document.body, theme);
		});
	}

	global.USISThemeBoot = {
		STORAGE_KEY: STORAGE_KEY,
		readStored: readStored,
		resolve: resolveTheme,
		apply: apply,
	};
})(window);
