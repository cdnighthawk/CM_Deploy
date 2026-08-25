/**
 * Populate the header bell from GET /api/v1/me/notifications.
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
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

	function dropdownRoot() {
		return document.querySelector(".nav-item.dropdown.notification_dropdown");
	}

	function formatWhen(iso) {
		if (!iso) return "";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return "";
		return d.toLocaleString();
	}

	function setBadge(root, unread) {
		var btn = root.querySelector("button.nav-link, a.nav-link");
		if (!btn) return;
		var badge = btn.querySelector(".usis-notif-badge");
		if (!unread) {
			if (badge) badge.remove();
			return;
		}
		if (!badge) {
			badge = document.createElement("span");
			badge.className = "usis-notif-badge badge bg-danger rounded-circle position-absolute";
			badge.style.cssText = "top:4px;right:2px;min-width:1.05rem;height:1.05rem;font-size:0.65rem;line-height:1.05rem;padding:0;";
			if (!btn.classList.contains("position-relative")) {
				btn.classList.add("position-relative");
			}
			btn.appendChild(badge);
		}
		badge.textContent = unread > 9 ? "9+" : String(unread);
	}

	function render(root, data) {
		var list = root.querySelector(".dz-scroll") || root.querySelector(".dropdown-menu");
		if (!list) return;
		var items = (data && data.items) || [];
		setBadge(root, Number((data && data.unread) || 0));
		var seeAll = root.querySelector("a.d-block.border-top, a.d-block.text-center");
		if (seeAll) seeAll.classList.add("d-none");
		if (!items.length) {
			list.innerHTML =
				'<p class="text-muted small text-center mb-0 py-5">No notifications.</p>';
			return;
		}
		list.innerHTML = items
			.map(function (n) {
				var unread = !n.read;
				var href = String(n.url || "").trim();
				if (href && href.charAt(0) !== "/" && !/^https?:\/\//i.test(href)) {
					href = "/" + href.replace(/^\.\//, "");
				}
				return (
					'<a class="dropdown-item d-flex align-items-start p-2 rounded text-decoration-none text-body usis-header-notif-item' +
					(unread ? " bg-action-light" : "") +
					'" href="' +
					esc(href || "#") +
					'" data-notif-url="' +
					esc(href) +
					'" data-notif-id="' +
					esc(n.id) +
					'">' +
					'<div class="avatar avatar-sm avatar-primary rounded-circle flex-shrink-0 d-flex align-items-center justify-content-center"><i class="fa fa-bell"></i></div>' +
					'<div class="ms-2">' +
					'<h6 class="fs-13 mb-0 fw-semibold">' +
					esc(n.title) +
					"</h6>" +
					(n.body ? '<div class="small mt-1">' + esc(n.body) + "</div>" : "") +
					'<small class="text-muted">' +
					esc(formatWhen(n.created_at)) +
					"</small>" +
					"</div></a>"
				);
			})
			.join("");
		list.querySelectorAll(".usis-header-notif-item").forEach(function (a) {
			a.addEventListener("click", function (ev) {
				var id = a.getAttribute("data-notif-id");
				var href = a.getAttribute("data-notif-url") || a.getAttribute("href") || "";
				if (id) {
					fetch(apiBase() + "/api/v1/me/notifications/" + encodeURIComponent(id) + "/read", {
						method: "POST",
						credentials: "include",
						headers: { Accept: "application/json" },
					}).catch(function () {});
				}
				if (href && href !== "#" && href.indexOf("javascript:") !== 0) {
					ev.preventDefault();
					window.location.assign(href);
				}
			});
		});
	}

	function refresh() {
		var root = dropdownRoot();
		if (!root) return;
		fetch(apiBase() + "/api/v1/me/notifications", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) return null;
				return r.json();
			})
			.then(function (data) {
				if (data) render(root, data);
			})
			.catch(function () {});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", refresh);
	} else {
		refresh();
	}
})();
