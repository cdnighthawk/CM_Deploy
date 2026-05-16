/**
 * HR suite home — loads ``GET /api/v1/hrms/dashboard``.
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var p = String(loc.port || "");
		if (p && p !== "5000") return loc.protocol + "//" + (loc.hostname || "127.0.0.1") + ":5000";
		return "";
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) return { "X-Usis-User-Id": id.trim() };
		return {};
	}

	function setErr(msg) {
		var el = document.getElementById("usis-hrms-dash-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function applyCounts(counts) {
		if (!counts) return;
		document.querySelectorAll("[data-usis-hrms-k]").forEach(function (node) {
			var k = node.getAttribute("data-usis-hrms-k");
			if (k && counts[k] != null) node.textContent = String(counts[k]);
		});
	}

	function loadDash() {
		setErr("");
		var url = apiBase() + "/api/v1/hrms/dashboard";
		fetch(url, { headers: Object.assign({ Accept: "application/json" }, actorHeaders()), credentials: "include" })
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, status: r.status, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					setErr((res.body && res.body.error) || "Dashboard failed (" + res.status + "). Set localStorage usisActorUserId or sign in.");
					return;
				}
				var item = res.body.item || {};
				var sc = document.getElementById("usis-hrms-scope");
				if (sc) sc.textContent = item.scope || "—";
				applyCounts(item.counts);
				var raw = document.getElementById("usis-hrms-raw");
				if (raw) raw.textContent = JSON.stringify(item, null, 2);
			})
			.catch(function () {
				setErr("Network error — is Flask running on :5000?");
			});
	}

	function wire() {
		var btn = document.getElementById("usis-hrms-reload");
		if (btn) btn.addEventListener("click", loadDash);
		loadDash();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
