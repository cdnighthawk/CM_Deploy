/**
 * Populate the header bell from GET /api/v1/me/notifications.
 */
(function (global) {
	"use strict";

	var unreadCount = 0;

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

	function setBellVisible(root, on) {
		if (!root) return;
		if (on) root.classList.remove("d-none");
		else root.classList.add("d-none");
	}

	function setBadge(root, unread) {
		unreadCount = Number(unread || 0);
		var btn = root.querySelector("button.nav-link, a.nav-link");
		if (!btn) return;
		var badge = btn.querySelector(".usis-notif-badge");
		if (!unreadCount) {
			if (badge) badge.remove();
			return;
		}
		if (!badge) {
			badge = document.createElement("span");
			badge.className = "usis-notif-badge badge bg-danger rounded-circle position-absolute";
			badge.style.cssText =
				"top:4px;right:2px;min-width:1.05rem;height:1.05rem;font-size:0.65rem;line-height:1.05rem;padding:0;";
			if (!btn.classList.contains("position-relative")) {
				btn.classList.add("position-relative");
			}
			btn.appendChild(badge);
		}
		badge.textContent = unreadCount > 9 ? "9+" : String(unreadCount);
	}

	function markRead(id) {
		if (!id) return Promise.resolve();
		return fetch(apiBase() + "/api/v1/me/notifications/" + encodeURIComponent(id) + "/read", {
			method: "POST",
			credentials: "include",
			keepalive: true,
			headers: { Accept: "application/json" },
		}).catch(function () {});
	}

	function markAllRead() {
		return fetch(apiBase() + "/api/v1/me/notifications/read-all", {
			method: "POST",
			credentials: "include",
			keepalive: true,
			headers: { Accept: "application/json" },
		}).catch(function () {});
	}

	function bindList(root, list) {
		list.querySelectorAll(".usis-header-notif-item").forEach(function (a) {
			a.addEventListener("click", function (ev) {
				var id = a.getAttribute("data-notif-id");
				var href = a.getAttribute("data-notif-url") || a.getAttribute("href") || "";
				if (a.classList.contains("bg-action-light")) {
					a.classList.remove("bg-action-light");
					setBadge(root, Math.max(0, unreadCount - 1));
				}
				if (id) markRead(id);
				if (href && href !== "#" && href.indexOf("javascript:") !== 0) {
					ev.preventDefault();
					window.setTimeout(function () {
						window.location.assign(href);
					}, 50);
					return;
				}
				ev.preventDefault();
			});
		});
		var markAll = list.querySelector("[data-usis-notif-mark-all]");
		if (markAll) {
			markAll.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				setBadge(root, 0);
				markAllRead().then(function () {
					refresh();
				});
			});
		}
	}

	function render(root, data) {
		var list = root.querySelector("#usis-header-bell-list") || root.querySelector(".dz-scroll");
		if (!list) return;
		var items = (data && data.items) || [];
		var unread = Number((data && data.unread) || 0);
		setBadge(root, unread);
		setBellVisible(root, items.length > 0 || unread > 0);
		var seeAll = root.querySelector("a.d-block.border-top, a.d-block.text-center");
		if (seeAll) seeAll.classList.add("d-none");
		if (!items.length) {
			list.innerHTML =
				'<p class="text-muted small text-center mb-0 py-5">No notifications.</p>';
			return;
		}
		var markAllHtml =
			unread > 0
				? '<div class="d-flex justify-content-end px-1 pb-1">' +
					'<button type="button" class="btn btn-link btn-sm text-decoration-none py-0" data-usis-notif-mark-all>Mark all as read</button>' +
					"</div>"
				: "";
		list.innerHTML =
			markAllHtml +
			items
				.map(function (n) {
					var itemUnread = !n.read;
					var href = String(n.url || "").trim();
					if (href && href.charAt(0) !== "/" && !/^https?:\/\//i.test(href)) {
						href = "/" + href.replace(/^\.\//, "");
					}
					return (
						'<a class="dropdown-item d-flex align-items-start p-2 rounded text-decoration-none text-body usis-header-notif-item' +
						(itemUnread ? " bg-action-light" : "") +
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
		bindList(root, list);
	}

	function setMessagesBadge(unread) {
		var link = document.getElementById("usis-header-messages");
		if (!link) return;
		var badge = link.querySelector(".usis-msg-badge");
		var n = Number(unread || 0);
		if (!n) {
			if (badge) badge.remove();
			return;
		}
		if (!badge) {
			badge = document.createElement("span");
			badge.className = "usis-msg-badge badge bg-danger rounded-circle position-absolute";
			link.classList.add("position-relative");
			link.appendChild(badge);
		}
		badge.textContent = n > 9 ? "9+" : String(n);
	}

	function refreshMessagesBadge() {
		fetch(apiBase() + "/api/v1/me/chat/unread-count", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) return null;
				return r.json();
			})
			.then(function (data) {
				if (data) setMessagesBadge(data.unread);
			})
			.catch(function () {});
	}

	function refresh() {
		var root = dropdownRoot();
		if (root) {
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
		refreshMessagesBadge();
	}

	function wireDropdownRefresh() {
		var root = dropdownRoot();
		if (!root || root.getAttribute("data-usis-notif-wired") === "1") return;
		root.setAttribute("data-usis-notif-wired", "1");
		root.addEventListener("shown.bs.dropdown", function () {
			refresh();
		});
	}

	global.usisRefreshHeaderNotifications = refresh;

	function start() {
		wireDropdownRefresh();
		refresh();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start);
	} else {
		start();
	}
})(typeof window !== "undefined" ? window : this);
