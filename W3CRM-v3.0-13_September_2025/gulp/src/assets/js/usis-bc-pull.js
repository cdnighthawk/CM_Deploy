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
		var hasToast = window.USISNotify && typeof window.USISNotify[kind] === "function";
		var hasBootstrapToast = window.bootstrap && window.bootstrap.Toast;
		if (hasToast && hasBootstrapToast) {
			window.USISNotify[kind](message);
			return;
		}
		if (hasToast) {
			window.USISNotify[kind](message);
		}
		window.alert(message);
	}

	function parseBody(r) {
		return r.text().then(function (text) {
			var j = {};
			if (text) {
				try {
					j = JSON.parse(text);
				} catch (e) {
					if (!r.ok && r.status !== 202) {
						throw new Error(text.slice(0, 180) || "HTTP " + r.status);
					}
				}
			}
			if (!r.ok && r.status !== 202) {
				throw new Error((j && (j.error || j.message)) || "HTTP " + r.status);
			}
			return j;
		});
	}

	window.usisPullBuildingConnected = function (opts) {
		opts = opts || {};
		var btn = opts.button || null;
		var onDone = typeof opts.onDone === "function" ? opts.onDone : null;
		if (!onDone && typeof window.usisBcPullOnDone === "function") {
			onDone = window.usisBcPullOnDone;
		}
		var origHtml = btn ? btn.innerHTML : "";
		if (btn) {
			if (btn.getAttribute("data-usis-bc-syncing") === "1") {
				return;
			}
			btn.setAttribute("data-usis-bc-syncing", "1");
			btn.disabled = true;
			btn.innerHTML = "Syncing BC…";
		}
		fetch(apiBase() + "/api/v1/integrations/buildingconnected/sync", {
			method: "POST",
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(parseBody)
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
					btn.removeAttribute("data-usis-bc-syncing");
					btn.disabled = false;
					btn.innerHTML = origHtml;
				}
			});
	};

	document.addEventListener("click", function (e) {
		var btn = e.target && e.target.closest && e.target.closest("#usis-bc-pull, #usis-est-bc-pull");
		if (!btn) return;
		e.preventDefault();
		window.usisPullBuildingConnected({ button: btn });
	});

	if (!document.querySelector('script[src*="usis-bc-write.js"]')) {
		var s = document.createElement("script");
		s.src = "assets/js/usis-bc-write.js";
		document.head.appendChild(s);
	}
})();
