/**
 * Account overview: load Settings / Security / Activity / … below the profile
 * tab bar without full page navigation (fetch sibling account/*.html fragments).
 */
(function () {
	"use strict";

	var TAB_SEL = "#tabMyProfileBottom .nav-link[data-usis-tab]";
	var OVERVIEW_PANEL = "#usis-account-overview-panel";
	var REMOTE_HOST = "#usis-account-remote-host";
	var REMOTE_ERR = "#usis-account-remote-error";
	var cache = {};

	function extractRemoteBody(doc) {
		var byId = doc.getElementById("usis-account-remote-body");
		if (byId) return byId;
		return doc.querySelector("#tabContentMyProfileBottom");
	}

	function setActiveTab(name) {
		document.querySelectorAll(TAB_SEL).forEach(function (a) {
			var t = a.getAttribute("data-usis-tab") || "";
			if (t === name) a.classList.add("active");
			else a.classList.remove("active");
		});
	}

	function showOverview() {
		var ov = document.querySelector(OVERVIEW_PANEL);
		var rh = document.querySelector(REMOTE_HOST);
		hideRemoteError();
		if (ov) ov.classList.remove("d-none");
		if (rh) {
			rh.classList.add("d-none");
			rh.innerHTML = "";
		}
		setActiveTab("overview");
	}

	function showRemoteError(msg) {
		var wrap = document.querySelector(REMOTE_ERR);
		if (!wrap) return;
		var inner = wrap.querySelector(".alert");
		if (inner) inner.textContent = msg || "Could not load this section.";
		wrap.classList.remove("d-none");
	}

	function hideRemoteError() {
		var wrap = document.querySelector(REMOTE_ERR);
		if (!wrap) return;
		wrap.classList.add("d-none");
	}

	function injectRemote(html, srcName) {
		var ov = document.querySelector(OVERVIEW_PANEL);
		var rh = document.querySelector(REMOTE_HOST);
		if (!rh) return;
		hideRemoteError();
		if (ov) ov.classList.add("d-none");
		rh.classList.remove("d-none");

		var doc = new DOMParser().parseFromString(html, "text/html");
		var body = extractRemoteBody(doc);
		if (!body) {
			rh.classList.add("d-none");
			rh.innerHTML = "";
			showOverview();
			showRemoteError("This section could not be embedded (missing #tabContentMyProfileBottom or #usis-account-remote-body).");
			return;
		}
		rh.innerHTML = "";
		rh.appendChild(document.importNode(body, true));

		if (srcName === "settings" && typeof window.USISProfileInit === "function") {
			window.USISProfileInit();
		}
		if (srcName !== "settings" && typeof window.USISProfileDashboardReload === "function") {
			setTimeout(function () {
				window.USISProfileDashboardReload();
			}, 50);
		}
	}

	function loadRemote(src, tabName) {
		if (cache[src]) {
			injectRemote(cache[src], tabName);
			setActiveTab(tabName);
			return;
		}
		var rh = document.querySelector(REMOTE_HOST);
		if (rh) {
			rh.innerHTML =
				'<div class="text-center text-muted py-5"><div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading…</div>';
			rh.classList.remove("d-none");
		}
		var ov = document.querySelector(OVERVIEW_PANEL);
		if (ov) ov.classList.add("d-none");
		hideRemoteError();
		setActiveTab(tabName);

		fetch(src, { credentials: "same-origin", cache: "no-store" })
			.then(function (r) {
				if (!r.ok) throw new Error(r.statusText);
				return r.text();
			})
			.then(function (html) {
				cache[src] = html;
				injectRemote(html, tabName);
			})
			.catch(function (err) {
				showOverview();
				showRemoteError("Could not load " + src + ": " + (err && err.message ? err.message : String(err)));
			});
	}

	function onNavClick(ev) {
		var a = ev.target.closest("a[data-usis-tab]");
		if (!a) return;
		var tab = (a.getAttribute("data-usis-tab") || "").trim();
		var src = (a.getAttribute("data-usis-src") || "").trim();
		if (!tab) return;
		ev.preventDefault();
		if (tab === "overview") {
			showOverview();
			return;
		}
		if (!src) return;
		loadRemote(src, tab);
	}

	function wire() {
		var nav = document.getElementById("tabMyProfileBottom");
		if (!nav) return;
		nav.addEventListener("click", onNavClick);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
