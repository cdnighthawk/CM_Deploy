/**
 * Shared helpers for vendor invoice pages.
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

	function esc(s) {
		if (s == null) return "";
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	function fmtMoney(amount, currency) {
		if (amount == null || amount === "") return "—";
		try {
			return new Intl.NumberFormat(undefined, {
				style: "currency",
				currency: currency || "USD",
			}).format(Number(amount));
		} catch (e) {
			return esc(amount) + (currency ? " " + esc(currency) : "");
		}
	}

	function statusBadge(status) {
		var s = status || "received";
		var cls = "bg-secondary";
		if (s === "received") cls = "bg-info";
		if (s === "routed") cls = "bg-primary";
		if (s === "pending_approval") cls = "bg-warning text-dark";
		if (s === "approved") cls = "bg-success";
		if (s === "rejected") cls = "bg-danger";
		if (s === "paid") cls = "bg-dark";
		if (s === "void") cls = "bg-secondary";
		return '<span class="badge ' + cls + '">' + esc(s.replace(/_/g, " ")) + "</span>";
	}

	function apiFetch(path, options) {
		options = options || {};
		var headers = Object.assign({ Accept: "application/json" }, actorHeaders(), options.headers || {});
		return fetch(apiBase() + path, Object.assign({ credentials: "include", headers: headers }, options)).then(function (r) {
			var ct = (r.headers.get("content-type") || "").toLowerCase();
			if (ct.indexOf("application/json") >= 0) {
				return r.json().then(function (body) {
					if (!r.ok) throw new Error((body && body.error) || "Request failed (" + r.status + ")");
					return body;
				});
			}
			if (!r.ok) throw new Error("Request failed (" + r.status + ")");
			return r;
		});
	}

	function fillSelect(el, items, selectedId, emptyLabel) {
		if (!el) return;
		var opts = '<option value="">' + esc(emptyLabel || "—") + "</option>";
		(items || []).forEach(function (row) {
			var id = row.id;
			var label = row.label || row.name || row.reference_number || id;
			opts +=
				'<option value="' +
				esc(id) +
				'"' +
				(selectedId && String(selectedId) === String(id) ? " selected" : "") +
				">" +
				esc(label) +
				"</option>";
		});
		el.innerHTML = opts;
	}

	window.USISInvoices = {
		apiBase: apiBase,
		actorHeaders: actorHeaders,
		esc: esc,
		fmtMoney: fmtMoney,
		statusBadge: statusBadge,
		apiFetch: apiFetch,
		fillSelect: fillSelect,
	};
})();
