/**
 * Estimate API helpers — independent estimates per lead.
 * GET/POST /api/v1/leads/<id>/estimates, GET /api/v1/estimates/<id>, lock/approve/unlock, quote report.
 */
(function (global) {
	"use strict";

	function apiBase() {
		if (typeof global.usisApiBase === "function") {
			return String(global.usisApiBase() || "").replace(/\/$/, "");
		}
		if (typeof global.USIS_API_BASE === "string") {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = global.location;
		if (!loc) return "http://127.0.0.1:5000";
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var port = String(loc.port || "");
		if (["3000", "3001", "3002", "3003", "5173", "8080"].indexOf(port) >= 0) {
			return loc.protocol + "//" + (loc.hostname || "127.0.0.1") + ":5000";
		}
		var host = loc.hostname || "";
		if ((host === "localhost" || host === "127.0.0.1") && port && port !== "5000") {
			return (loc.protocol + "//" + host + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	function parseJsonResponse(res) {
		return res.text().then(function (text) {
			var body = {};
			try {
				body = text ? JSON.parse(text) : {};
			} catch (e) {
				body = {};
			}
			var err = new Error(
				(body && body.error) || (text && !body.error ? text.slice(0, 180) : "HTTP " + res.status)
			);
			err.status = res.status;
			err.body = body;
			err.error_code = body && body.error_code;
			if (!res.ok) throw err;
			return body;
		});
	}

	function fetchJson(path, opts) {
		var options = opts ? Object.assign({}, opts) : {};
		options.credentials = "include";
		options.headers = Object.assign({ Accept: "application/json" }, options.headers || {});
		return fetch(apiBase() + path, options).then(parseJsonResponse);
	}

	function leadIdFromItem(item) {
		if (!item) return null;
		var lead = item.lead || {};
		return (
			item.lead_id ||
			item.lead_estimate_id ||
			lead.id ||
			lead.external_id ||
			item.external_id ||
			null
		);
	}

	function estimateIdFromItem(item) {
		if (!item) return null;
		return item.current_estimate_id || (item.entity === "estimate" ? item.id : null) || item.id || null;
	}

	function estimateDetailHref(estimateId) {
		if (!estimateId) return "javascript:void(0);";
		return "construction/estimate-detail.html?id=" + encodeURIComponent(String(estimateId));
	}

	function leadDetailHref(leadId) {
		if (!leadId) return "construction/leads.html";
		return "construction/lead-detail.html?id=" + encodeURIComponent(String(leadId));
	}

	function quoteReportUrl(estimateId, columns) {
		var q = columns && columns.length ? "?columns=" + encodeURIComponent(columns.join(",")) : "";
		return apiBase() + "/api/v1/estimates/" + encodeURIComponent(estimateId) + "/render/quote-report" + q;
	}

	function listForLead(leadId) {
		return fetchJson("/api/v1/leads/" + encodeURIComponent(leadId) + "/estimates");
	}

	function createForLead(leadId, body) {
		return fetchJson("/api/v1/leads/" + encodeURIComponent(leadId) + "/estimates", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body || {}),
		});
	}

	function getEstimate(estimateId) {
		return fetchJson("/api/v1/estimates/" + encodeURIComponent(estimateId));
	}

	function getLead(leadId) {
		return fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(leadId));
	}

	function listDrawingSets(leadId) {
		return fetchJson("/api/v1/leads/" + encodeURIComponent(leadId) + "/drawing-sets");
	}

	function postEstimateAction(estimateId, action) {
		return fetchJson("/api/v1/estimates/" + encodeURIComponent(estimateId) + "/" + action, {
			method: "POST",
		});
	}

	/**
	 * Resolve a URL id that may be either an estimate UUID or a legacy lead id.
	 * On lead-id hits, replace the URL with the current estimate id.
	 */
	function resolveEstimateId(urlId) {
		if (!urlId) return Promise.reject(new Error("Missing estimate id."));
		return getEstimate(urlId)
			.then(function (data) {
				return { item: data.item, redirected: false };
			})
			.catch(function (err) {
				if (err.status !== 404) throw err;
				return getLead(urlId).then(function (data) {
					var lead = data.item;
					var eid = lead && lead.current_estimate_id;
					if (!eid) {
						var missing = new Error(
							"This lead has no estimates yet. Open the lead and create one."
						);
						missing.status = 404;
						missing.lead = lead;
						throw missing;
					}
					if (global.history && global.history.replaceState) {
						try {
							var u = new URL(global.location.href);
							u.searchParams.set("id", eid);
							global.history.replaceState({}, "", u.pathname + u.search + u.hash);
						} catch (e2) {
							/* ignore */
						}
					}
					return getEstimate(eid).then(function (est) {
						return { item: est.item, redirected: true, lead: lead };
					});
				});
			});
	}

	function feeToPercent(value) {
		if (value == null || value === "") return "";
		var n = Number(value);
		if (!isFinite(n)) return "";
		if (Math.abs(n) <= 1) n = n * 100;
		return String(Math.round(n * 1000) / 1000);
	}

	function percentToFee(value) {
		if (value == null || value === "") return null;
		var n = Number(value);
		if (!isFinite(n)) return null;
		if (Math.abs(n) > 1) n = n / 100;
		return n;
	}

	global.USISEstimateApi = {
		apiBase: apiBase,
		fetchJson: fetchJson,
		leadIdFromItem: leadIdFromItem,
		estimateIdFromItem: estimateIdFromItem,
		estimateDetailHref: estimateDetailHref,
		leadDetailHref: leadDetailHref,
		quoteReportUrl: quoteReportUrl,
		listForLead: listForLead,
		createForLead: createForLead,
		getEstimate: getEstimate,
		getLead: getLead,
		listDrawingSets: listDrawingSets,
		postEstimateAction: postEstimateAction,
		resolveEstimateId: resolveEstimateId,
		feeToPercent: feeToPercent,
		percentToFee: percentToFee,
	};
})(typeof window !== "undefined" ? window : this);
