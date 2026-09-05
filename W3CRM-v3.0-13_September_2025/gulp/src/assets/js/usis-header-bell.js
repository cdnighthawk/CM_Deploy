/**
 * Show the header bell only when the signed-in user has notifications.
 */
(function (global) {
	"use strict";

	function apiBase() {
		if (typeof global.usisApiBase === "function") return global.usisApiBase();
		if (typeof global.USIS_API_BASE === "string" && global.USIS_API_BASE.trim()) {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = global.location;
		if (!loc) return "";
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		if (host === "localhost" || host === "127.0.0.1") {
			return (loc.protocol + "//" + host + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function render(items) {
		var item = document.getElementById("usis-header-bell-item");
		var list = document.getElementById("usis-header-bell-list");
		if (!item || !list) return;
		if (!items || !items.length) {
			item.classList.add("d-none");
			return;
		}
		item.classList.remove("d-none");
		list.innerHTML = items
			.map(function (n) {
				var href = n.url ? esc(n.url) : "#";
				var title = esc(n.title || "Notice");
				var unread = n.read ? "" : " fw-semibold";
				return (
					'<a class="dropdown-item py-2' +
					unread +
					'" href="' +
					href +
					'" data-usis-note-id="' +
					esc(n.id || "") +
					'">' +
					title +
					"</a>"
				);
			})
			.join("");
	}

	function init() {
		var item = document.getElementById("usis-header-bell-item");
		if (!item) return;
		fetch(apiBase() + "/api/v1/me/notifications", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) throw new Error("http");
				return r.json();
			})
			.then(function (data) {
				render(data.items || []);
			})
			.catch(function () {
				item.classList.add("d-none");
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})(typeof window !== "undefined" ? window : this);
