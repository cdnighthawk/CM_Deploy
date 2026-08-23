/**
 * Fluent Outlook mailbox UI for usis-email.html (Graph via /api/v1/mail/*).
 */
(function () {
	"use strict";

	var folder = "inbox";
	var selectedId = null;
	var selectedMeta = null;
	var listCache = [];
	var FOLDER_TITLES = {
		inbox: "Inbox",
		sent: "Sent Items",
		drafts: "Drafts",
		deleted: "Deleted Items",
	};
	var AVATAR_COLORS = ["#c239b3", "#0078d4", "#5c2e91", "#ca5010", "#498205", "#038387", "#8764b8", "#004e8c"];

	function api() {
		return window.USIS_API;
	}

	function notify() {
		return window.USISNotify || null;
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function setStatus(msg, isError) {
		var el = document.getElementById("usis-mail-status");
		if (!el) return;
		el.className = "usis-ol-status" + (isError ? " text-danger" : "");
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function setToolbar(enabled) {
		["usis-mail-delete-btn", "usis-mail-reply-btn"].forEach(function (id) {
			var btn = document.getElementById(id);
			if (btn) btn.disabled = !enabled;
		});
	}

	function showEmpty() {
		var empty = document.getElementById("usis-mail-empty");
		var wrap = document.getElementById("usis-mail-read-wrap");
		if (empty) empty.classList.remove("d-none");
		if (wrap) wrap.classList.add("d-none");
		setToolbar(false);
	}

	function showRead() {
		var empty = document.getElementById("usis-mail-empty");
		var wrap = document.getElementById("usis-mail-read-wrap");
		if (empty) empty.classList.add("d-none");
		if (wrap) wrap.classList.remove("d-none");
		setToolbar(true);
	}

	function showCompose(show) {
		var read = document.getElementById("usis-mail-read-card");
		var compose = document.getElementById("usis-mail-compose-card");
		if (read) read.classList.toggle("d-none", !!show);
		if (compose) compose.classList.toggle("d-none", !show);
		if (show) setToolbar(false);
	}

	function formatWhen(iso, longForm) {
		if (!iso) return "";
		var dt = new Date(iso);
		if (isNaN(dt.getTime())) return String(iso);
		if (longForm) {
			return dt.toLocaleString(undefined, {
				weekday: "short",
				month: "short",
				day: "numeric",
				hour: "numeric",
				minute: "2-digit",
			});
		}
		var now = new Date();
		var sameDay =
			dt.getFullYear() === now.getFullYear() &&
			dt.getMonth() === now.getMonth() &&
			dt.getDate() === now.getDate();
		if (sameDay) {
			return dt.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
		}
		return dt.toLocaleDateString(undefined, { month: "numeric", day: "numeric" });
	}

	function initials(name) {
		var parts = String(name || "")
			.replace(/[^A-Za-z0-9 ]/g, " ")
			.trim()
			.split(/\s+/);
		if (!parts[0]) return "?";
		if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
		return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
	}

	function avatarColor(name) {
		var n = 0;
		String(name || "")
			.split("")
			.forEach(function (ch) {
				n += ch.charCodeAt(0);
			});
		return AVATAR_COLORS[n % AVATAR_COLORS.length];
	}

	function displayName(m) {
		var from = (m.from && (m.from.name || m.from.address)) || "";
		if (folder === "sent") {
			var to0 = (m.to && m.to[0]) || {};
			from = to0.name || to0.address || from;
		}
		return from;
	}

	function loadMe() {
		if (!api()) return;
		api()
			.fetchJson("/api/v1/me")
			.then(function (data) {
				var email = (data.item && data.item.email) || "";
				var account = document.getElementById("usis-mail-account");
				var asEl = document.getElementById("usis-mail-sending-as");
				if (account && email) account.textContent = email;
				if (asEl && email) asEl.textContent = email;
			})
			.catch(function () {});
	}

	function setFolder(next) {
		folder = next;
		selectedId = null;
		selectedMeta = null;
		document.querySelectorAll("[data-folder]").forEach(function (btn) {
			btn.classList.toggle("is-active", btn.getAttribute("data-folder") === folder);
		});
		var title = document.getElementById("usis-mail-folder-title");
		if (title) title.textContent = FOLDER_TITLES[folder] || "Inbox";
		var search = document.getElementById("usis-mail-search");
		if (search) search.value = "";
		showCompose(false);
		showEmpty();
		loadList();
	}

	function matchesSearch(m, q) {
		if (!q) return true;
		var blob = [
			displayName(m),
			m.subject,
			m.preview,
			m.from && m.from.address,
		]
			.join(" ")
			.toLowerCase();
		return blob.indexOf(q) !== -1;
	}

	function renderList() {
		var list = document.getElementById("usis-mail-list");
		if (!list) return;
		var q = ((document.getElementById("usis-mail-search") || {}).value || "").trim().toLowerCase();
		var items = listCache.filter(function (m) {
			return matchesSearch(m, q);
		});
		if (!items.length) {
			list.innerHTML = "";
			setStatus(listCache.length ? "No matches." : "No messages in this folder.");
			return;
		}
		setStatus("");
		list.innerHTML = items
			.map(function (m) {
				var from = displayName(m);
				var cls = "usis-ol-row";
				if (!m.is_read && folder === "inbox") cls += " is-unread";
				if (m.id === selectedId) cls += " is-on";
				return (
					'<button type="button" class="' +
					cls +
					'" data-id="' +
					esc(m.id) +
					'" data-from="' +
					esc((m.from && m.from.address) || "") +
					'" data-subject="' +
					esc(m.subject || "") +
					'"><span class="usis-ol-avatar" style="background:' +
					avatarColor(from) +
					'">' +
					esc(initials(from)) +
					'</span><span><div class="usis-ol-from">' +
					esc(from) +
					'</div><div class="usis-ol-subject">' +
					esc(m.subject) +
					'</div><div class="usis-ol-preview">' +
					esc(m.preview) +
					'</div></span><span class="usis-ol-when">' +
					esc(formatWhen(m.received)) +
					"</span></button>"
				);
			})
			.join("");
		list.querySelectorAll("[data-id]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				openMessage(btn.getAttribute("data-id"), btn);
			});
		});
	}

	function loadList() {
		var list = document.getElementById("usis-mail-list");
		if (!list || !api()) return;
		list.innerHTML = "";
		setStatus("Loading…");
		api()
			.fetchJson("/api/v1/mail/messages", { params: { folder: folder, top: 50 } })
			.then(function (data) {
				listCache = (data && data.items) || [];
				renderList();
			})
			.catch(function (err) {
				listCache = [];
				setStatus(err.message || "Could not load mail.", true);
			});
	}

	function markRowActive(id) {
		document.querySelectorAll("#usis-mail-list [data-id]").forEach(function (btn) {
			var on = btn.getAttribute("data-id") === id;
			btn.classList.toggle("is-on", on);
			if (on) btn.classList.remove("is-unread");
		});
	}

	function openMessage(id, rowBtn) {
		selectedId = id;
		if (rowBtn) {
			selectedMeta = {
				from: rowBtn.getAttribute("data-from") || "",
				subject: rowBtn.getAttribute("data-subject") || "",
			};
		}
		showCompose(false);
		showRead();
		markRowActive(id);
		var pane = document.getElementById("usis-mail-read");
		var head = document.getElementById("usis-mail-read-head");
		if (!pane || !api()) return;
		if (head) head.innerHTML = "<p class='mb-0' style='color:#616161'>Loading message…</p>";
		pane.innerHTML = "";
		api()
			.fetchJson("/api/v1/mail/messages/" + encodeURIComponent(id))
			.then(function (m) {
				var fromName = (m.from && (m.from.name || m.from.address)) || "";
				var fromAddr = (m.from && m.from.address) || "";
				selectedMeta = { from: fromAddr, subject: m.subject || "" };
				var to = (m.to || [])
					.map(function (a) {
						return a.address || a.name;
					})
					.join("; ");
				if (head) {
					head.innerHTML =
						"<h2>" +
						esc(m.subject || "(no subject)") +
						'</h2><div class="usis-ol-person"><span class="usis-ol-avatar" style="background:' +
						avatarColor(fromName) +
						'">' +
						esc(initials(fromName)) +
						'</span><div><div class="usis-ol-person-name">' +
						esc(fromName) +
						'</div><div class="usis-ol-person-addr">' +
						esc(fromAddr) +
						'</div><div class="usis-ol-person-to">To: ' +
						esc(to) +
						'</div></div><div class="usis-ol-person-when">' +
						esc(formatWhen(m.received, true)) +
						"</div></div>";
				}
				var attachments = (m.attachments || [])
					.map(function (a) {
						var href =
							(api().apiBase ? api().apiBase() : "") +
							"/api/v1/mail/messages/" +
							encodeURIComponent(id) +
							"/attachments/" +
							encodeURIComponent(a.id);
						return (
							'<a class="usis-ol-file" href="' +
							esc(href) +
							'" target="_blank" rel="noopener">' +
							esc(a.name) +
							"</a>"
						);
					})
					.join("");
				pane.innerHTML = attachments ? '<div class="usis-ol-files">' + attachments + "</div>" : "";
				if ((m.body_type || "").toLowerCase() === "html") {
					var frame = document.createElement("iframe");
					frame.setAttribute("sandbox", "");
					frame.setAttribute("referrerpolicy", "no-referrer");
					frame.setAttribute("title", "Message body");
					frame.srcdoc = String(m.body_content || "").replace(/<\/iframe/gi, "&lt;/iframe");
					pane.appendChild(frame);
				} else {
					var pre = document.createElement("pre");
					pre.className = "mb-0";
					pre.style.whiteSpace = "pre-wrap";
					pre.style.fontFamily = "inherit";
					pre.style.padding = "12px 20px";
					pre.textContent = m.body_content || "";
					pane.appendChild(pre);
				}
				if (!m.is_read && folder === "inbox") {
					api()
						.fetchJson("/api/v1/mail/messages/" + encodeURIComponent(id), {
							method: "PATCH",
							body: { is_read: true },
						})
						.catch(function () {});
				}
			})
			.catch(function (err) {
				if (head) head.innerHTML = "";
				pane.innerHTML = '<p class="text-danger">' + esc(err.message || "Could not open message.") + "</p>";
			});
	}

	function deleteSelected() {
		if (!selectedId) return;
		if (!window.confirm("Delete this message? It will move to Deleted Items in Outlook.")) return;
		api()
			.fetchJson("/api/v1/mail/messages/" + encodeURIComponent(selectedId), { method: "DELETE" })
			.then(function () {
				selectedId = null;
				selectedMeta = null;
				showEmpty();
				loadList();
			})
			.catch(function (err) {
				var N = notify();
				if (N) N.error(err.message || "Delete failed");
				else alert(err.message || "Delete failed");
			});
	}

	function replySelected() {
		if (!selectedMeta) return;
		showCompose(true);
		var to = document.getElementById("usis-mail-to");
		var subj = document.getElementById("usis-mail-subject");
		if (to) to.value = selectedMeta.from || "";
		if (subj) {
			var s = selectedMeta.subject || "";
			subj.value = /^re:/i.test(s) ? s : "Re: " + s;
		}
		var body = document.getElementById("usis-mail-body");
		if (body) body.focus();
	}

	function sendCompose(ev) {
		ev.preventDefault();
		if (!api()) return;
		var to = (document.getElementById("usis-mail-to") || {}).value || "";
		var cc = (document.getElementById("usis-mail-cc") || {}).value || "";
		var subject = (document.getElementById("usis-mail-subject") || {}).value || "";
		var body = (document.getElementById("usis-mail-body") || {}).value || "";
		var btn = document.getElementById("usis-mail-send");
		if (btn) btn.disabled = true;
		api()
			.fetchJson("/api/v1/messages/email", {
				method: "POST",
				body: { to: to.trim(), cc: cc.trim(), subject: subject.trim(), message: body },
			})
			.then(function (data) {
				var N = notify();
				if (data.dry_run) {
					if (N) N.warning("Mail was logged only (Graph not fully configured).");
					else alert("Mail was logged only (Graph not fully configured).");
					return;
				}
				if (N) N.success("Email sent.");
				["usis-mail-to", "usis-mail-cc", "usis-mail-subject", "usis-mail-body"].forEach(function (id) {
					var el = document.getElementById(id);
					if (el) el.value = "";
				});
				showCompose(false);
				showEmpty();
				if (folder === "sent") loadList();
			})
			.catch(function (err) {
				var N = notify();
				if (N) N.error(err.message || "Send failed");
				else alert(err.message || "Send failed");
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		loadMe();
		loadList();
		document.querySelectorAll("[data-folder]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				setFolder(btn.getAttribute("data-folder"));
			});
		});
		var composeBtn = document.getElementById("usis-mail-compose-btn");
		if (composeBtn)
			composeBtn.addEventListener("click", function () {
				showCompose(true);
			});
		var cancel = document.getElementById("usis-mail-compose-cancel");
		if (cancel)
			cancel.addEventListener("click", function () {
				showCompose(false);
				showEmpty();
			});
		var delBtn = document.getElementById("usis-mail-delete-btn");
		if (delBtn) delBtn.addEventListener("click", deleteSelected);
		var replyBtn = document.getElementById("usis-mail-reply-btn");
		if (replyBtn) replyBtn.addEventListener("click", replySelected);
		var form = document.getElementById("usis-mail-compose-form");
		if (form) form.addEventListener("submit", sendCompose);
		var search = document.getElementById("usis-mail-search");
		if (search) search.addEventListener("input", renderList);
	});
})();
