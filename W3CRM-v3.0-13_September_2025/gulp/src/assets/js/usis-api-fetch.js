/**
 * Shared credentialed API helpers for the USIS shell (session cookies on Render + local dev).
 * Depends on ``usis-api-base.js`` (``window.usisApiBase``).
 */
(function (global) {
	"use strict";

	function apiBase() {
		if (typeof global.usisApiBase === "function") {
			return global.usisApiBase();
		}
		if (typeof global.USIS_API_BASE === "string") {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		return "";
	}

	function actorHeaders() {
		var id = null;
		try {
			id = global.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function buildUrl(path, params) {
		var url = apiBase() + path;
		if (!params) return url;
		var qs = [];
		Object.keys(params).forEach(function (k) {
			var v = params[k];
			if (v === undefined || v === null || v === "") return;
			if (Array.isArray(v)) {
				qs.push(encodeURIComponent(k) + "=" + encodeURIComponent(v.join(",")));
			} else {
				qs.push(encodeURIComponent(k) + "=" + encodeURIComponent(String(v)));
			}
		});
		if (qs.length) {
			url += (url.indexOf("?") === -1 ? "?" : "&") + qs.join("&");
		}
		return url;
	}

	/**
	 * @param {string} path - API path e.g. ``/api/v1/auth/status``
	 * @param {{ method?: string, body?: *, headers?: object, params?: object }} [opts]
	 */
	function fetchJson(path, opts) {
		var o = opts || {};
		var url = typeof path === "string" && path.indexOf("/api/") === 0 ? buildUrl(path, o.params) : path;
		var headers = Object.assign({ Accept: "application/json" }, actorHeaders(), o.headers || {});
		var init = {
			method: o.method || "GET",
			headers: headers,
			credentials: "include",
		};
		if (o.body !== undefined && o.body !== null) {
			if (!init.headers["Content-Type"]) {
				init.headers["Content-Type"] = "application/json";
			}
			init.body = typeof o.body === "string" ? o.body : JSON.stringify(o.body);
		}
		return fetch(url, init).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					var err = new Error(res.status + " " + (t || res.statusText));
					err.status = res.status;
					err.body = t;
					throw err;
				});
			}
			if (res.status === 204) return null;
			return res.json();
		});
	}

	global.USIS_API = {
		apiBase: apiBase,
		actorHeaders: actorHeaders,
		buildUrl: buildUrl,
		fetchJson: fetchJson,
	};
})(typeof window !== "undefined" ? window : this);
