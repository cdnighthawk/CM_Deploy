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

	function actorOverrideAllowed() {
		try {
			var host = (global.location && global.location.hostname) || "";
			return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
		} catch (e) {
			return false;
		}
	}

	function actorHeaders() {
		if (!actorOverrideAllowed()) {
			return {};
		}
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

	var QUEUE_KEY = "usisClientErrorQueue";
	var MAX_QUEUE = 40;
	var DEDUP_MS = 60000;
	var FLUSH_MS = 15000;
	var recent = {};
	var flushTimer = null;
	var sending = false;

	function isLogUrl(url) {
		return typeof url === "string" && url.indexOf("/api/v1/client-errors") !== -1;
	}

	function requestUrl(input) {
		if (typeof input === "string") return input;
		if (input && typeof input.url === "string") return input.url;
		try {
			return String(input || "");
		} catch (e) {
			return "";
		}
	}

	function requestMethod(input, init) {
		if (init && init.method) return String(init.method).toUpperCase();
		if (input && typeof input === "object" && input.method) return String(input.method).toUpperCase();
		return "GET";
	}

	function readQueue() {
		try {
			var raw = global.localStorage.getItem(QUEUE_KEY);
			var parsed = raw ? JSON.parse(raw) : [];
			return Array.isArray(parsed) ? parsed : [];
		} catch (e) {
			return [];
		}
	}

	function writeQueue(items) {
		try {
			global.localStorage.setItem(QUEUE_KEY, JSON.stringify(items.slice(-MAX_QUEUE)));
		} catch (e) {}
	}

	function enqueue(evt) {
		var q = readQueue();
		q.push(evt);
		writeQueue(q);
		scheduleFlush();
	}

	function scheduleFlush() {
		if (flushTimer) return;
		flushTimer = global.setTimeout(function () {
			flushTimer = null;
			flushQueue();
		}, 400);
	}

	function nativeFetch() {
		return (global.fetch && global.fetch.__usisNative) || global.fetch;
	}

	function flushQueue() {
		if (sending) return;
		var q = readQueue();
		if (!q.length) return;
		var send = nativeFetch();
		if (typeof send !== "function") return;
		sending = true;
		var batch = q.slice(0, 20);
		send(apiBase() + "/api/v1/client-errors", {
			method: "POST",
			credentials: "include",
			headers: Object.assign({ Accept: "application/json", "Content-Type": "application/json" }, actorHeaders()),
			body: JSON.stringify({ events: batch }),
			keepalive: true,
		})
			.then(function (res) {
				sending = false;
				if (res && res.ok) {
					writeQueue(readQueue().slice(batch.length));
					if (readQueue().length) scheduleFlush();
					return;
				}
				if (res && res.status === 429) return;
				throw new Error("log failed");
			})
			.catch(function () {
				sending = false;
			});
	}

	function reportError(evt) {
		if (!evt || !evt.message) return;
		var now = Date.now();
		var key = [evt.kind || "", evt.url || "", evt.message].join("|");
		if (recent[key] && now - recent[key] < DEDUP_MS) return;
		recent[key] = now;
		var payload = {
			kind: evt.kind || "connect",
			source: "browser",
			message: String(evt.message).slice(0, 2000),
			url: evt.url ? String(evt.url).slice(0, 1000) : "",
			method: evt.method ? String(evt.method).slice(0, 10) : "",
			status: typeof evt.status === "number" ? evt.status : null,
			page: (global.location && (global.location.pathname + global.location.search)) || "",
			user_agent: (global.navigator && global.navigator.userAgent) || "",
			occurred_at: now,
			extra: evt.extra || undefined,
		};
		enqueue(payload);
	}

	function shouldLogStatus(status) {
		return status === 0 || status === 502 || status === 503 || status === 504 || status >= 500;
	}

	function isAbort(err) {
		if (!err) return false;
		if (err.name === "AbortError") return true;
		var msg = String(err.message || err);
		return /The user aborted a request|AbortError/i.test(msg);
	}

	function isConnectError(err) {
		if (!err || isAbort(err)) return false;
		var msg = String(err.message || err);
		return /Failed to fetch|NetworkError|Load failed|Network request failed|ERR_CONNECTION|ECONNREFUSED|Failed to load/i.test(
			msg
		);
	}

	function wrapFetch() {
		var orig = global.fetch;
		if (typeof orig !== "function" || orig.__usisErrorWrapped) return;
		function wrapped(input, init) {
			var url = requestUrl(input);
			if (isLogUrl(url)) return orig.call(this, input, init);
			return orig.call(this, input, init).then(
				function (res) {
					if (shouldLogStatus(res.status)) {
						reportError({
							kind: res.status >= 500 ? "http_error" : "connect",
							message: "HTTP " + res.status + (res.statusText ? " " + res.statusText : ""),
							url: url,
							method: requestMethod(input, init),
							status: res.status,
						});
					}
					return res;
				},
				function (err) {
					if (isConnectError(err)) {
						reportError({
							kind: "connect",
							message: err && err.message ? err.message : "Failed to fetch",
							url: url,
							method: requestMethod(input, init),
						});
					}
					throw err;
				}
			);
		}
		wrapped.__usisErrorWrapped = true;
		wrapped.__usisNative = orig.__usisNative || orig;
		global.fetch = wrapped;
	}

	function wireWindowErrors() {
		if (global.__usisClientErrorWindow) return;
		global.__usisClientErrorWindow = true;
		global.addEventListener("unhandledrejection", function (ev) {
			var reason = ev && ev.reason;
			if (isAbort(reason)) return;
			if (reason && typeof reason.status === "number") return;
			if (isConnectError(reason)) return;
			var msg = reason && reason.message ? reason.message : String(reason || "unhandledrejection");
			reportError({ kind: "unhandled", message: msg, url: (global.location && global.location.href) || "" });
		});
		global.addEventListener("error", function (ev) {
			if (!ev) return;
			var msg = ev.message || (ev.error && ev.error.message) || "Script error";
			if (msg === "Script error." || msg === "Script error") return;
			reportError({
				kind: "js_error",
				message: msg,
				url: ev.filename || ((global.location && global.location.href) || ""),
				extra: { line: ev.lineno, col: ev.colno },
			});
		});
		global.addEventListener("online", function () {
			flushQueue();
		});
		global.addEventListener("pagehide", function () {
			flushQueue();
		});
	}

	wrapFetch();
	wireWindowErrors();
	if (global.setInterval) {
		global.setInterval(flushQueue, FLUSH_MS);
	}
	scheduleFlush();

	global.USIS_API = {
		apiBase: apiBase,
		actorHeaders: actorHeaders,
		buildUrl: buildUrl,
		fetchJson: fetchJson,
		reportError: reportError,
		flushErrorLog: flushQueue,
	};
})(typeof window !== "undefined" ? window : this);
