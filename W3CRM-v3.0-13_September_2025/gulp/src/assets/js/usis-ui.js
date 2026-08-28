/**
 * Shared chrome helpers: StatusChip, AiReviewButton, EmptyState.
 * Visual only — does not change API payloads or workflow data.
 */
(function (global) {
	"use strict";

	var FAMILY = {
		draft: "draft",
		new: "new",
		sent: "sent",
		"in progress": "progress",
		in_progress: "progress",
		progress: "progress",
		estimating: "estimating",
		invited: "progress",
		submitted: "progress",
		awarded: "awarded",
		approved: "approved",
		released: "approved",
		signed: "approved",
		won: "awarded",
		lost: "lost",
		rejected: "rejected",
		declined: "rejected",
		overdue: "overdue",
		warning: "warning",
		partial: "partial",
		"due soon": "warning",
		locked: "draft",
		critical: "critical",
		major: "major",
		minor: "minor",
		info: "info",
	};

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function familyOf(status) {
		var key = String(status || "")
			.trim()
			.toLowerCase()
			.replace(/[_-]+/g, " ");
		if (FAMILY[key]) return FAMILY[key];
		if (FAMILY[key.replace(/\s+/g, "_")]) return FAMILY[key.replace(/\s+/g, "_")];
		if (/critical/.test(key)) return "critical";
		if (/major/.test(key)) return "major";
		if (/minor/.test(key)) return "minor";
		if (/award|approv|releas/.test(key)) return "awarded";
		if (/lost|reject|declin|overdue/.test(key)) return "lost";
		if (/warn|partial|due/.test(key)) return "warning";
		if (/sent|progress|estimat|invit|submit/.test(key)) return "progress";
		if (/draft|new|lock/.test(key)) return "draft";
		return "draft";
	}

	function chipClass(family, filled) {
		var map = {
			draft: "usis-status-chip--draft",
			new: "usis-status-chip--new",
			sent: "usis-status-chip--sent",
			progress: "usis-status-chip--progress",
			estimating: "usis-status-chip--estimating",
			awarded: "usis-status-chip--awarded",
			approved: "usis-status-chip--approved",
			lost: "usis-status-chip--lost",
			rejected: "usis-status-chip--rejected",
			overdue: "usis-status-chip--overdue",
			warning: "usis-status-chip--warning",
			partial: "usis-status-chip--partial",
			critical: "usis-status-chip--critical",
			major: "usis-status-chip--major",
			minor: "usis-status-chip--minor",
			info: "usis-status-chip--info",
		};
		var extra = map[family] || "usis-status-chip--draft";
		if (filled && (family === "critical" || family === "major" || family === "warning")) {
			extra += " usis-status-chip--filled";
		}
		return "usis-status-chip " + extra;
	}

	function statusChip(status, opts) {
		opts = opts || {};
		var label = opts.label != null ? opts.label : status || "—";
		var family = opts.family || familyOf(status);
		var filled = opts.filled === true || family === "critical" || family === "major";
		var title = opts.title || String(status || label);
		return (
			'<span class="' +
			chipClass(family, filled) +
			'" title="' +
			esc(title) +
			'">' +
			esc(label) +
			"</span>"
		);
	}

	function severityChip(sev) {
		var s = String(sev || "").toLowerCase();
		if (!s) return "—";
		var family = s === "critical" ? "critical" : s === "major" ? "major" : s === "minor" ? "minor" : "info";
		var label = s.charAt(0).toUpperCase() + s.slice(1);
		return (
			'<span class="' +
			chipClass(family, family === "critical" || family === "major") +
			'" title="' +
			esc(label) +
			'"><span class="usis-status-dot usis-status-dot--' +
			family +
			'" aria-hidden="true"></span>' +
			esc(label) +
			"</span>"
		);
	}

	function aiReviewButton(opts) {
		opts = opts || {};
		var label = opts.label || "Review with Local AI";
		var size = opts.size === "small" ? " btn-sm" : "";
		var id = opts.id ? ' id="' + esc(opts.id) + '"' : "";
		return (
			'<button type="button" class="btn usis-ai-review' +
			size +
			'"' +
			id +
			">" +
			'<i class="icon feather icon-star me-1" aria-hidden="true"></i>' +
			esc(label) +
			"</button>"
		);
	}

	function emptyState(opts) {
		opts = opts || {};
		var icon = opts.icon || "icon-inbox";
		var title = opts.title || "Nothing here yet";
		var body = opts.body || "";
		var action = opts.actionHtml || "";
		return (
			'<div class="usis-empty">' +
			'<div class="usis-empty__icon" aria-hidden="true"><i class="icon feather ' +
			esc(icon) +
			'"></i></div>' +
			'<div class="usis-empty__title">' +
			esc(title) +
			"</div>" +
			(body ? '<p class="usis-empty__body mb-0">' + esc(body) + "</p>" : "") +
			(action ? '<div class="mt-3">' + action + "</div>" : "") +
			"</div>"
		);
	}

	function restyleAiButtons(root) {
		var scope = root || global.document;
		if (!scope || !scope.querySelectorAll) return;
		scope.querySelectorAll("#usis-qc-ai, #usis-dv-ai-stub, [data-usis-ai-review]").forEach(function (btn) {
			btn.classList.add("usis-ai-review");
			btn.classList.remove("btn-primary", "btn-secondary");
			btn.style.background = "";
			btn.style.color = "";
			if (!btn.querySelector(".icon") && !btn.querySelector("i")) {
				btn.insertAdjacentHTML(
					"afterbegin",
					'<i class="icon feather icon-star me-1" aria-hidden="true"></i>'
				);
			}
		});
	}

	global.USISUi = {
		statusChip: statusChip,
		severityChip: severityChip,
		aiReviewButton: aiReviewButton,
		emptyState: emptyState,
		familyOf: familyOf,
		restyleAiButtons: restyleAiButtons,
	};

	if (global.document.readyState === "loading") {
		global.document.addEventListener("DOMContentLoaded", function () {
			restyleAiButtons();
		});
	} else {
		restyleAiButtons();
	}
})(window);
