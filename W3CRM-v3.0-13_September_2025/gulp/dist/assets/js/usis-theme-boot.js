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

	var theme = resolveTheme();
	applyToEl(global.document.documentElement, theme);

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
