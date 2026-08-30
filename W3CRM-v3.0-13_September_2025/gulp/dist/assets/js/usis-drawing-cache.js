/**
 * Shared employee-PC cache — Flask on this PC writes
 * %LOCALAPPDATA%\USISCM\{projectId}\{drawingId}\{fileName}
 * plus company JSON and takeoff.json.
 *
 * The browser does not write that folder. This script asks the API to refresh
 * company/takeoff files and prefetches drawing /file URLs so Flask can cache PDFs.
 */
(function (global) {
	"use strict";

	function apiBase() {
		if (typeof global.usisApiBase === "function") return global.usisApiBase();
		if (typeof global.USIS_API_BASE === "string") return String(global.USIS_API_BASE).replace(/\/$/, "");
		return "";
	}

	function drawingIdN(id) {
		var s = String(id || "")
			.trim()
			.toLowerCase()
			.replace(/-/g, "");
		return /^[0-9a-f]{32}$/.test(s) ? s : "";
	}

	function sanitizeFileName(fileName) {
		if (fileName == null || !String(fileName).trim()) return null;
		var name = String(fileName).trim().replace(/\\/g, "/");
		var slash = name.lastIndexOf("/");
		if (slash >= 0) name = name.slice(slash + 1);
		name = name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_");
		return name.trim() ? name : null;
	}

	function preferredFileName(drawingId, fileName) {
		var n = drawingIdN(drawingId);
		return sanitizeFileName(fileName) || (n ? n + ".pdf" : "drawing.pdf");
	}

	function isAuthPage() {
		var p = (global.location.pathname || "").replace(/\\/g, "/").toLowerCase();
		return (
			p.indexOf("page-login") !== -1 ||
			p.indexOf("page-register") !== -1 ||
			p.indexOf("page-forgot-password") !== -1 ||
			p.indexOf("page-reset-password") !== -1 ||
			p.indexOf("page-lock-screen") !== -1 ||
			p.indexOf("apply.html") !== -1 ||
			p.indexOf("/apply/") !== -1
		);
	}

	function projectIdFromPage() {
		var ctx = global.USISProjectContext;
		if (ctx && typeof ctx.projectIdFromQuery === "function") {
			var fromCtx = ctx.projectIdFromQuery();
			if (fromCtx) return fromCtx;
		}
		try {
			var p = new URLSearchParams(global.location.search);
			return (p.get("project_id") || p.get("projectId") || "").trim() || "";
		} catch (e) {
			return "";
		}
	}

	function refresh(projectId) {
		var pid = projectId || projectIdFromPage();
		var url = apiBase() + "/api/v1/pc-cache/refresh";
		if (pid) url += "?project_id=" + encodeURIComponent(pid);
		return fetch(url, { method: "POST", credentials: "include", headers: { Accept: "application/json" } }).catch(
			function () {
				return null;
			}
		);
	}

	function jobFromSheet(sheet) {
		var cr = (sheet && sheet.current_revision) || sheet || {};
		if (!cr.id) return null;
		var raw = cr.file_url || "";
		var url = "";
		if (raw) {
			url = /^https?:\/\//i.test(raw)
				? raw
				: apiBase() + (raw.charAt(0) === "/" ? raw : "/" + raw);
		} else {
			url = apiBase() + "/api/v1/drawings/" + encodeURIComponent(cr.id) + "/file";
		}
		return {
			drawingId: cr.id,
			fileName: cr.original_filename || null,
			url: url,
			name: preferredFileName(cr.id, cr.original_filename),
			projectId: cr.project_id || (sheet && sheet.project_id) || null,
		};
	}

	var prefetchQueue = Promise.resolve();

	function prefetchSheets(sheets) {
		var jobs = (sheets || []).map(jobFromSheet).filter(Boolean);
		if (!jobs.length) return Promise.resolve();
		prefetchQueue = prefetchQueue.then(function () {
			var i = 0;
			function next() {
				if (i >= jobs.length) return Promise.resolve();
				var job = jobs[i++];
				return fetch(job.url, { credentials: "include", headers: { Range: "bytes=0-0" } })
					.catch(function () {})
					.then(next);
			}
			return next();
		});
		return prefetchQueue;
	}

	global.USISDrawingCache = {
		drawingIdN: drawingIdN,
		sanitizeFileName: sanitizeFileName,
		preferredFileName: preferredFileName,
		jobFromSheet: jobFromSheet,
		prefetchSheets: prefetchSheets,
		refresh: refresh,
		projectIdFromPage: projectIdFromPage,
	};

	function boot() {
		if (isAuthPage()) return;
		refresh();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
})(typeof window !== "undefined" ? window : this);
