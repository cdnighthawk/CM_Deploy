/**
 * Shared HR applicant account delete (DELETE /api/v1/hr/applications/:userId).
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		if (host === "localhost" || host === "127.0.0.1") return (proto + "//" + host + ":5000").replace(/\/$/, "");
		return "";
	}

	function confirmDeleteApplicant(displayName) {
		var reason = window.prompt(
			"Reason for deleting this applicant account (required):" +
				(displayName ? "\n\nApplicant: " + displayName : "")
		);
		if (!reason || !String(reason).trim()) return null;
		if (
			!window.confirm(
				"Permanently delete this applicant account and all hire application data?\n\nThis cannot be undone."
			)
		) {
			return null;
		}
		return String(reason).trim();
	}

	function deleteApplicantAccount(userId, reason) {
		return fetch(apiBase() + "/api/v1/hr/applications/" + encodeURIComponent(userId), {
			method: "DELETE",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({ confirm: true, reason: reason }),
		}).then(function (r) {
			return r.json().then(function (data) {
				if (!r.ok) {
					throw new Error((data && (data.error || data.message)) || "Delete failed");
				}
				return data;
			});
		});
	}

	window.USISHrApplicantDelete = {
		confirmDeleteApplicant: confirmDeleteApplicant,
		deleteApplicantAccount: deleteApplicantAccount,
	};
})();
