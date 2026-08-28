/**
 * USIS chrome language (English / Español).
 * Persists in localStorage so the choice survives refresh and is not limited to /construction/.
 */
(function (global) {
	"use strict";

	var KEY = "usis.language";
	var COOKIE = "language";

	var ES = {
		USIS: "USIS",
		Dashboard: "Inicio",
		Leads: "Prospectos",
		Estimate: "Estimación",
		Projects: "Proyectos",
		Calendar: "Calendario",
		Safety: "Seguridad",
		"CRM pipeline": "Embudo CRM",
		Documents: "Documentos",
		Email: "Correo",
		HR: "RH",
		Applications: "Solicitudes",
		"HR suite": "Suite de RH",
		Expenses: "Gastos",
		Playbooks: "Guías",
		"User admin": "Admin. de usuarios",
		Procurement: "Compras",
		Invoices: "Facturas",
		Reports: "Reportes",
		Search: "Buscar",
		"Report a problem": "Reportar un problema",
		"My profile": "Mi perfil",
		Language: "Idioma",
		"Menus and login use this language.": "Los menús e inicio de sesión usan este idioma.",
		Logout: "Cerrar sesión",
		"Logout ": "Cerrar sesión",
		Login: "Iniciar sesión",
		"Sign in": "Iniciar sesión",
		"Sign in to CM": "Entrar a CM",
		"Sign in with Microsoft": "Entrar con Microsoft",
		"Sign out": "Cerrar sesión",
		Cancel: "Cancelar",
		Save: "Guardar",
		Create: "Crear",
		Send: "Enviar",
		Close: "Cerrar",
		Edit: "Editar",
		Delete: "Eliminar",
		Home: "Inicio",
		"No notifications.": "No hay notificaciones.",
		"See all notifications": "Ver todas las notificaciones",
		"Remember me": "Recordarme",
		"Forgot Password?": "¿Olvidó su contraseña?",
		Password: "Contraseña",
		"Enter your password": "Escriba su contraseña",
		"USIS Construction Management": "USIS Control de Obra",
		"Sign in to access projects, estimates, and field operations.":
			"Inicie sesión para ver proyectos, estimaciones y trabajo de campo.",
		"Need a staff account?": "¿Necesita una cuenta de personal?",
		"Create one": "Crear una",
		"Looking for a job with USIS?": "¿Busca trabajo en USIS?",
		"Apply to USIS": "Solicitar en USIS",
		"Or sign in with": "O entre con",
		"Continue your application": "Continúe su solicitud",
		"Continue job application": "Continuar solicitud de empleo",
		"Email and password are required.": "Se requieren correo y contraseña.",
		"Invalid email or password. On Render, create a user with the bootstrap script or register first.":
			"Correo o contraseña incorrectos.",
		Kind: "Tipo",
		Title: "Título",
		Details: "Detalles",
		"Your name (optional)": "Su nombre (opcional)",
		"Short summary": "Resumen corto",
		"What happened, and what did you expect?": "¿Qué pasó y qué esperaba?",
		"Tell us what broke or what to change. It will show on the Issues page.":
			"Díganos qué falló o qué cambiar. Aparecerá en la página de Issues.",
		"Something broke": "Algo falló",
		"Recommend a change on this page": "Recomendar un cambio en esta página",
		"General recommendation": "Recomendación general",
		"Sent with this report": "Se envía con este reporte",
		"Site-wide (not tied to a page).": "En todo el sitio (no ligado a una página).",
		"So we know who to follow up with": "Para saber a quién contactar",
		"Back to dashboard": "Volver al inicio",
	};

	function supported(code) {
		return code === "es_ES" || code === "en_GB";
	}

	function readCookie() {
		var parts = ("; " + document.cookie).split("; " + COOKIE + "=");
		if (parts.length < 2) return "";
		return parts.pop().split(";").shift() || "";
	}

	function writeCookie(lang) {
		document.cookie = COOKIE + "=" + lang + ";path=/;max-age=31536000;SameSite=Lax";
	}

	function getLang() {
		try {
			var stored = global.localStorage.getItem(KEY);
			if (supported(stored)) return stored;
		} catch (e) {}
		var cookie = readCookie();
		if (supported(cookie)) return cookie;
		return "en_GB";
	}

	function setLang(code) {
		var lang = supported(code) ? code : "en_GB";
		try {
			global.localStorage.setItem(KEY, lang);
		} catch (e) {}
		writeCookie(lang);
		if (document.body) document.body.setAttribute("data-language", lang);
		document.documentElement.setAttribute("lang", lang === "es_ES" ? "es" : "en");
		return lang;
	}

	function tr(key, lang) {
		lang = lang || getLang();
		if (!key) return "";
		if (lang !== "es_ES") return key;
		return ES[key] != null ? ES[key] : key;
	}

	function remember(el, attr, value) {
		var flag = "data-i18n-src" + (attr ? "-" + attr : "");
		if (!el.getAttribute(flag) && value) el.setAttribute(flag, value);
		return el.getAttribute(flag) || value || "";
	}

	function applyText(el, lang) {
		// Never flatten wrappers: .auth-form p often contains <a href> links.
		if (el.children && el.children.length) return;
		var key = el.getAttribute("data-i18n") || remember(el, "", (el.textContent || "").trim());
		if (!key) return;
		remember(el, "", key);
		el.textContent = tr(el.getAttribute("data-i18n-src") || key, lang);
	}

	function applyPlaceholder(el, lang) {
		var key = el.getAttribute("data-i18n-placeholder") || remember(el, "placeholder", el.getAttribute("placeholder") || "");
		if (!key) return;
		el.setAttribute("placeholder", tr(key, lang));
	}

	function applyTitle(el, lang) {
		var key = el.getAttribute("data-i18n-title") || remember(el, "title", el.getAttribute("title") || "");
		if (!key) return;
		el.setAttribute("title", tr(key, lang));
	}

	function applyAria(el, lang) {
		var key = el.getAttribute("data-i18n-aria") || remember(el, "aria", el.getAttribute("aria-label") || "");
		if (!key) return;
		el.setAttribute("aria-label", tr(key, lang));
	}

	function apply(lang) {
		lang = setLang(lang || getLang());
		document.querySelectorAll("[data-i18n]").forEach(function (el) {
			applyText(el, lang);
		});
		document.querySelectorAll(".deznav .nav-text, .deznav .menu-title").forEach(function (el) {
			applyText(el, lang);
		});
		document.querySelectorAll(".auth-form h3, .auth-form p, .auth-form label, .auth-form .btn, .auth-form .form-check-label, .auth-form a.btn-link, .auth-form span.small").forEach(function (el) {
			if (el.children && el.children.length) return;
			applyText(el, lang);
		});
		document.querySelectorAll("[data-i18n-placeholder], .header-search input[placeholder]").forEach(function (el) {
			applyPlaceholder(el, lang);
		});
		document.querySelectorAll("[data-i18n-title], .usis-report-problem-btn[title]").forEach(function (el) {
			applyTitle(el, lang);
		});
		document.querySelectorAll("[data-i18n-aria], .usis-report-problem-btn[aria-label]").forEach(function (el) {
			applyAria(el, lang);
		});
		document.querySelectorAll(".header-profile-dropdown .dropdown-item span, #usis-report-problem-modal .modal-title, #usis-report-problem-modal .btn, #usis-report-problem-modal .form-label, #usis-report-problem-modal .text-muted, .notification_dropdown .text-muted, .notification_dropdown a.d-block").forEach(function (el) {
			if (el.closest && el.closest("[data-i18n]")) return;
			applyText(el, lang);
		});
		var switcher = document.getElementById("langSwitcher");
		if (switcher && switcher.value !== lang) {
			switcher.value = lang;
			if (global.jQuery && global.jQuery.fn.selectpicker) {
				global.jQuery(switcher).selectpicker("val", lang);
			}
		}
		document.querySelectorAll("[data-usis-set-lang]").forEach(function (btn) {
			var on = btn.getAttribute("data-usis-set-lang") === lang;
			btn.classList.toggle("active", on);
			btn.setAttribute("aria-pressed", on ? "true" : "false");
			if (btn.classList.contains("btn")) {
				btn.classList.toggle("btn-primary", on);
				btn.classList.toggle("btn-outline-secondary", !on);
			}
		});
	}

	function profileMenuItem() {
		var menu = document.querySelector(".header-profile-dropdown .dropdown-menu");
		if (!menu) return null;
		var links = menu.querySelectorAll("a.dropdown-item[href]");
		for (var i = 0; i < links.length; i++) {
			var href = (links[i].getAttribute("href") || "").split("?")[0];
			if (href.indexOf("usis-profile.html") !== -1) return links[i].closest("li");
		}
		return null;
	}

	function ensureProfileLangMenu() {
		var menu = document.querySelector(".header-profile-dropdown .dropdown-menu");
		if (!menu || menu.querySelector("[data-usis-profile-lang]")) return;
		var li = document.createElement("li");
		li.setAttribute("data-usis-profile-lang", "1");
		li.innerHTML =
			'<div class="px-3 py-2">' +
			'<div class="small text-muted mb-1" data-i18n="Language">Language</div>' +
			'<div class="btn-group btn-group-sm w-100" role="group" aria-label="Language">' +
			'<button type="button" class="btn btn-outline-secondary" data-usis-set-lang="en_GB">English</button>' +
			'<button type="button" class="btn btn-outline-secondary" data-usis-set-lang="es_ES">Español</button>' +
			"</div></div>";
		var after = profileMenuItem();
		if (after && after.parentNode) {
			if (after.nextSibling) after.parentNode.insertBefore(li, after.nextSibling);
			else after.parentNode.appendChild(li);
			return;
		}
		var firstDivider = menu.querySelector(".dropdown-divider");
		if (firstDivider && firstDivider.closest("li")) {
			var wrap = firstDivider.closest("li");
			if (wrap.nextSibling) menu.insertBefore(li, wrap.nextSibling);
			else menu.appendChild(li);
			return;
		}
		menu.appendChild(li);
	}

	function bind() {
		var switcher = document.getElementById("langSwitcher");
		if (switcher && !switcher.getAttribute("data-usis-i18n-bound")) {
			switcher.setAttribute("data-usis-i18n-bound", "1");
			switcher.addEventListener("change", function () {
				var next = switcher.value === "es_ES" ? "es_ES" : "en_GB";
				apply(next);
			});
		}
		document.querySelectorAll("[data-usis-set-lang]").forEach(function (btn) {
			if (btn.getAttribute("data-usis-i18n-bound")) return;
			btn.setAttribute("data-usis-i18n-bound", "1");
			btn.addEventListener("click", function () {
				apply(btn.getAttribute("data-usis-set-lang"));
			});
		});
	}

	function init() {
		ensureProfileLangMenu();
		bind();
		apply(getLang());
	}

	global.USISI18n = {
		getLang: getLang,
		setLang: setLang,
		apply: apply,
		tr: tr,
		init: init,
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})(typeof window !== "undefined" ? window : this);
