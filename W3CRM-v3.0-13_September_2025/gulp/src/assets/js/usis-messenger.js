/**
 * In-app 1:1 messenger — conversations list + chat thread.
 */
(function () {
	"use strict";

	var POLL_MS = 4000;
	var LIST_POLL_MS = 8000;
	var activeId = "";
	var lastMessageId = "";
	var convos = [];
	var pollTimer = null;
	var listTimer = null;
	var searchTimer = null;
	var stickToBottom = true;

	function api() {
		return window.USIS_API || {};
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function $(id) {
		return document.getElementById(id);
	}

	function flash(msg, kind) {
		var el = $("usis-msg-flash");
		if (!el) return;
		el.className = "alert py-2 px-3 mb-3 " + (kind === "error" ? "alert-danger" : "alert-success");
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function formatWhen(iso) {
		if (!iso) return "";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return "";
		var now = new Date();
		var sameDay = d.toDateString() === now.toDateString();
		return sameDay
			? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
			: d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
	}

	function preview(text) {
		var t = String(text || "").replace(/\s+/g, " ").trim();
		if (t.length > 72) return t.slice(0, 69) + "…";
		return t;
	}

	function initials(name) {
		var parts = String(name || "")
			.trim()
			.split(/\s+/)
			.filter(Boolean);
		if (!parts.length) return "?";
		if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
		return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
	}

	function setThreadOpen(open) {
		var shell = document.querySelector(".usis-msg-shell");
		if (!shell) return;
		shell.classList.toggle("is-thread-open", !!open);
	}

	function renderConvos() {
		var root = $("usis-msg-convos");
		if (!root) return;
		if (!convos.length) {
			root.innerHTML =
				'<p class="text-muted small px-3 py-4 mb-0" data-i18n="No conversations yet.">No conversations yet. Search for someone above.</p>';
			return;
		}
		root.innerHTML = convos
			.map(function (c) {
				var name = (c.other && c.other.name) || "Conversation";
				var last = (c.last_message && c.last_message.body) || "No messages yet";
				var unread = Number(c.unread || 0);
				return (
					'<button type="button" class="usis-msg-convo' +
					(c.id === activeId ? " is-active" : "") +
					'" data-conv="' +
					esc(c.id) +
					'">' +
					'<span class="usis-msg-avatar" aria-hidden="true">' +
					esc(initials(name)) +
					"</span>" +
					'<span class="usis-msg-convo__text">' +
					'<span class="usis-msg-convo__name">' +
					esc(name) +
					(unread
						? '<span class="badge bg-danger rounded-pill ms-1">' + esc(String(unread > 9 ? "9+" : unread)) + "</span>"
						: "") +
					"</span>" +
					'<span class="usis-msg-convo__preview">' +
					esc(preview(last)) +
					"</span>" +
					"</span>" +
					'<span class="usis-msg-convo__when">' +
					esc(formatWhen(c.last_message && c.last_message.created_at ? c.last_message.created_at : c.updated_at)) +
					"</span>" +
					"</button>"
				);
			})
			.join("");
	}

	function loadConvos() {
		return fetchJson("/api/v1/me/chat/conversations")
			.then(function (d) {
				convos = (d && d.items) || [];
				renderConvos();
			})
			.catch(function (err) {
				flash(err.message || "Could not load conversations.", "error");
			});
	}

	function appendBubbles(items, replace) {
		var root = $("usis-msg-bubbles");
		if (!root) return;
		if (replace) root.innerHTML = "";
		if ((!items || !items.length) && replace) {
			root.innerHTML = '<p class="text-muted small text-center mb-0 py-5">No messages yet. Say hello.</p>';
			return;
		}
		if (!items || !items.length) return;
		var empty = root.querySelector("p.text-muted");
		if (empty) empty.remove();
		var html = items
			.map(function (m) {
				lastMessageId = m.id || lastMessageId;
				return (
					'<div class="usis-msg-bubble' +
					(m.mine ? " is-mine" : "") +
					'">' +
					'<div class="usis-msg-bubble__body">' +
					esc(m.body).replace(/\n/g, "<br>") +
					"</div>" +
					'<div class="usis-msg-bubble__meta">' +
					esc(m.mine ? "You" : (m.sender && m.sender.name) || "") +
					" · " +
					esc(formatWhen(m.created_at)) +
					"</div>" +
					"</div>"
				);
			})
			.join("");
		root.insertAdjacentHTML("beforeend", html);
		if (stickToBottom) {
			root.scrollTop = root.scrollHeight;
		}
	}

	function setComposerEnabled(on) {
		var input = $("usis-msg-input");
		var send = $("usis-msg-send");
		if (input) input.disabled = !on;
		if (send) send.disabled = !on;
	}

	function setPeer(conv) {
		var name = $("usis-msg-peer-name");
		var email = $("usis-msg-peer-email");
		if (name) name.textContent = (conv && conv.other && conv.other.name) || "Conversation";
		if (email) email.textContent = (conv && conv.other && conv.other.email) || "";
	}

	function markRead(id) {
		if (!id) return Promise.resolve();
		return fetchJson("/api/v1/me/chat/conversations/" + encodeURIComponent(id) + "/read", {
			method: "POST",
		}).catch(function () {});
	}

	function openConversation(id, convHint) {
		if (!id) return;
		activeId = id;
		lastMessageId = "";
		stickToBottom = true;
		setThreadOpen(true);
		setComposerEnabled(true);
		if (convHint) setPeer(convHint);
		renderConvos();
		var root = $("usis-msg-bubbles");
		if (root) root.innerHTML = '<p class="text-muted small text-center mb-0 py-5">Loading…</p>';
		return fetchJson("/api/v1/me/chat/conversations/" + encodeURIComponent(id) + "/messages")
			.then(function (d) {
				if (d && d.conversation) setPeer(d.conversation);
				appendBubbles((d && d.items) || [], true);
				return markRead(id).then(function () {
					return loadConvos();
				});
			})
			.catch(function (err) {
				flash(err.message || "Could not load messages.", "error");
			});
	}

	function pollMessages() {
		if (!activeId) return;
		var path = "/api/v1/me/chat/conversations/" + encodeURIComponent(activeId) + "/messages";
		if (lastMessageId) path += "?after=" + encodeURIComponent(lastMessageId);
		fetchJson(path)
			.then(function (d) {
				var items = (d && d.items) || [];
				if (items.length) {
					appendBubbles(items, false);
					markRead(activeId);
					loadConvos();
				}
			})
			.catch(function () {});
	}

	function startOrOpenUser(userId) {
		if (!userId) return;
		return fetchJson("/api/v1/me/chat/conversations", {
			method: "POST",
			body: { user_id: userId },
		})
			.then(function (d) {
				var item = d && d.item;
				if (!item) return;
				var exists = convos.some(function (c) {
					return c.id === item.id;
				});
				if (!exists) convos.unshift(item);
				hidePeople();
				var q = $("usis-msg-people");
				if (q) q.value = "";
				return openConversation(item.id, item);
			})
			.catch(function (err) {
				flash(err.message || "Could not start conversation.", "error");
			});
	}

	function hidePeople() {
		var box = $("usis-msg-people-results");
		if (box) {
			box.classList.add("d-none");
			box.innerHTML = "";
		}
	}

	function searchPeople(q) {
		var box = $("usis-msg-people-results");
		if (!box) return;
		if (!q || q.length < 1) {
			hidePeople();
			return;
		}
		fetchJson("/api/v1/me/chat/users", { params: { q: q, limit: 12 } })
			.then(function (d) {
				var items = (d && d.items) || [];
				if (!items.length) {
					box.innerHTML = '<div class="usis-msg-people-empty text-muted small">No matches.</div>';
					box.classList.remove("d-none");
					return;
				}
				box.innerHTML = items
					.map(function (u) {
						return (
							'<button type="button" class="usis-msg-people-item" role="option" data-user="' +
							esc(u.id) +
							'">' +
							'<span class="usis-msg-avatar usis-msg-avatar--sm" aria-hidden="true">' +
							esc(initials(u.name)) +
							"</span>" +
							"<span><span class='d-block fw-semibold'>" +
							esc(u.name) +
							"</span><span class='small text-muted'>" +
							esc(u.email || "") +
							"</span></span>" +
							"</button>"
						);
					})
					.join("");
				box.classList.remove("d-none");
			})
			.catch(function () {
				hidePeople();
			});
	}

	function sendMessage(ev) {
		if (ev) ev.preventDefault();
		if (!activeId) return;
		var input = $("usis-msg-input");
		var text = input ? String(input.value || "").trim() : "";
		if (!text) return;
		setComposerEnabled(false);
		fetchJson("/api/v1/me/chat/conversations/" + encodeURIComponent(activeId) + "/messages", {
			method: "POST",
			body: { body: text },
		})
			.then(function (d) {
				if (input) input.value = "";
				stickToBottom = true;
				if (d && d.item) appendBubbles([d.item], false);
				return loadConvos();
			})
			.catch(function (err) {
				flash(err.message || "Could not send message.", "error");
			})
			.then(function () {
				setComposerEnabled(true);
				if (input) input.focus();
			});
	}

	function applyQuery() {
		var params = new URLSearchParams(window.location.search || "");
		var cid = (params.get("c") || "").trim();
		var uid = (params.get("user") || "").trim();
		if (cid) return openConversation(cid);
		if (uid) return startOrOpenUser(uid);
		return Promise.resolve();
	}

	document.addEventListener("DOMContentLoaded", function () {
		var people = $("usis-msg-people");
		if (people) {
			people.addEventListener("input", function () {
				clearTimeout(searchTimer);
				var q = people.value.trim();
				searchTimer = setTimeout(function () {
					searchPeople(q);
				}, 180);
			});
			people.addEventListener("keydown", function (ev) {
				if (ev.key === "Escape") hidePeople();
			});
		}
		var results = $("usis-msg-people-results");
		if (results) {
			results.addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-user]");
				if (btn) startOrOpenUser(btn.getAttribute("data-user"));
			});
		}
		var convosEl = $("usis-msg-convos");
		if (convosEl) {
			convosEl.addEventListener("click", function (ev) {
				var btn = ev.target.closest("[data-conv]");
				if (btn) openConversation(btn.getAttribute("data-conv"));
			});
		}
		var form = $("usis-msg-form");
		if (form) form.addEventListener("submit", sendMessage);
		var input = $("usis-msg-input");
		if (input) {
			input.addEventListener("keydown", function (ev) {
				if (ev.key === "Enter" && !ev.shiftKey) {
					ev.preventDefault();
					sendMessage();
				}
			});
		}
		var back = $("usis-msg-back");
		if (back) {
			back.addEventListener("click", function () {
				activeId = "";
				setThreadOpen(false);
				setComposerEnabled(false);
			});
		}
		var bubbles = $("usis-msg-bubbles");
		if (bubbles) {
			bubbles.addEventListener("scroll", function () {
				var gap = bubbles.scrollHeight - bubbles.scrollTop - bubbles.clientHeight;
				stickToBottom = gap < 48;
			});
		}
		document.addEventListener("click", function (ev) {
			if (ev.target.closest("#usis-msg-people, #usis-msg-people-results")) return;
			hidePeople();
		});
		loadConvos()
			.then(applyQuery)
			.then(function () {
				pollTimer = setInterval(pollMessages, POLL_MS);
				listTimer = setInterval(loadConvos, LIST_POLL_MS);
			});
		document.addEventListener("visibilitychange", function () {
			if (!document.hidden) {
				loadConvos();
				pollMessages();
			}
		});
	});
})();
