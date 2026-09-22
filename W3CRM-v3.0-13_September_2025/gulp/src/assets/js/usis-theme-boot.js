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

	function applyWordmark(doc) {
		if (!doc) {
			return;
		}
		var titles = doc.querySelectorAll(".usis-logo-title");
		var i;
		var el;
		for (i = 0; i < titles.length; i++) {
			el = titles[i];
			if (el.getAttribute("data-usis-wordmark") === "1") {
				continue;
			}
			el.setAttribute("data-usis-wordmark", "1");
			el.classList.add("usis-wordmark");
			el.innerHTML =
				'<span class="usis-wordmark__worx">WorX</span> <span class="usis-wordmark__cm">CM</span>';
		}
		var logos = doc.querySelectorAll(".usis-brand-logo");
		for (i = 0; i < logos.length; i++) {
			logos[i].setAttribute("aria-label", "WorX CM");
		}
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
		link.href = "/assets/css/usis-ui.css?v=20260921a";
		doc.head.appendChild(link);
		applyWordmark(doc);
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
