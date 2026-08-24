/**
 * Pull recent BuildingConnected opportunities into lead_estimates.
 * Used by the Sync BC button on Leads and Estimates.
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return String(window.usisApiBase() || "").replace(/\/$/, "");
		}
		return "";
	}

	function notify(kind, message) {
		if (window.USISNotify && typeof window.USISNotify[kind] === "function") {
			window.USISNotify[kind](message);
			return;
		}
		window.alert(message);
	}

	window.usisPullBuildingConnected = function (opts) {
		opts = opts || {};
		var btn = opts.button || null;
		var onDone = typeof opts.onDone === "function" ? opts.onDone : null;
		var origHtml = btn ? btn.innerHTML : "";
		if (btn) {
			btn.disabled = true;
			btn.innerHTML = "Syncing BC…";
		}
		fetch(apiBase() + "/api/v1/integrations/buildingconnected/sync", {
			method: "POST",
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				return r.json().then(function (j) {
					if (!r.ok && r.status !== 202) {
						throw new Error((j && (j.error || j.message)) || "HTTP " + r.status);
					}
					return j;
				});
			})
			.then(function (data) {
				notify(
					"success",
					(data && data.message) ||
						"BuildingConnected sync started. Refresh the list in about a minute."
				);
				if (onDone) {
					window.setTimeout(onDone, 4000);
				}
			})
			.catch(function (err) {
				notify("error", (err && err.message) || "BuildingConnected sync failed.");
			})
			.finally(function () {
				if (btn) {
					btn.disabled = false;
					btn.innerHTML = origHtml;
				}
			});
	};

	if (!document.querySelector('script[src*="usis-bc-write.js"]')) {
		var s = document.createElement("script");
		s.src = "assets/js/usis-bc-write.js";
		document.head.appendChild(s);
	}
})();
