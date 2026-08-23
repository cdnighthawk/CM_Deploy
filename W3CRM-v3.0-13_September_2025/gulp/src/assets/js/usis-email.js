/**
 * Real Outlook mailbox UI for usis-email.html (Graph via /api/v1/mail/*).
 */
(function () {
	"use strict";

	var folder = "inbox";
	var selectedId = null;

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

	function statusEl() {
		return document.getElementById("usis-mail-status");
	}

	function setStatus(msg, isError) {
		var el = statusEl();
		if (!el) return;
		el.className = "p-3 small " + (isError ? "text-danger" : "text-muted");
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function showCompose(show) {
		var read = document.getElementById("usis-mail-read-card");
		var compose = document.getElementById("usis-mail-compose-card");
		if (read) read.classList.toggle("d-none", !!show);
		if (compose) compose.classList.toggle("d-none", !show);
	}

	function formatWhen(iso) {
		if (!iso) return "";
		try {
			return new Date(iso).toLocaleString();
		} catch (e) {
			return String(iso);
		}
	}

	function loadMe() {
		var el = document.getElementById("usis-mail-sending-as");
		if (!api()) return;
		api()
			.fetchJson("/api/v1/me")
			.then(function (data) {
				var email = (data.item && data.item.email) || "";
				if (el && email) el.textContent = "Sending as " + email;
			})
			.catch(function () {});
	}

	function setFolder(next) {
		folder = next;
		selectedId = null;
		document.querySelectorAll("[data-folder]").forEach(function (btn) {
			btn.classList.toggle("active", btn.getAttribute("data-folder") === folder);
		});
		var title = document.getElementById("usis-mail-folder-title");
		if (title) title.textContent = folder === "sent" ? "Sent" : "Inbox";
		showCompose(false);
		loadList();
	}

	function loadList() {
		var list = document.getElementById("usis-mail-list");
		if (!list || !api()) return;
		list.innerHTML = "";
		setStatus("Loading…");
		api()
			.fetchJson("/api/v1/mail/messages", { params: { folder: folder, top: 50 } })
			.then(function (data) {
				var items = (data && data.items) || [];
				if (!items.length) {
					setStatus("No messages in this folder.");
					return;
				}
				setStatus("");
				list.innerHTML = items
					.map(function (m) {
						var from = (m.from && (m.from.name || m.from.address)) || "";
						var cls = "list-group-item list-group-item-action usis-mail-list-item";
						if (!m.is_read && folder === "inbox") cls += " usis-mail-unread";
						if (m.id === selectedId) cls += " active";
						return (
							'<button type="button" class="' +
							cls +
							'" data-id="' +
							esc(m.id) +
							'"><div class="d-flex justify-content-between gap-2"><span>' +
							esc(from) +
							'</span><span class="text-muted small">' +
							esc(formatWhen(m.received)) +
							"</span></div><div>" +
							esc(m.subject) +
							'</div><div class="text-muted small text-truncate">' +
							esc(m.preview) +
							"</div></button>"
						);
					})
					.join("");
				list.querySelectorAll("[data-id]").forEach(function (btn) {
					btn.addEventListener("click", function () {
						openMessage(btn.getAttribute("data-id"));
					});
				});
			})
			.catch(function (err) {
				setStatus(err.message || "Could not load mail.", true);
			});
	}

	function openMessage(id) {
		selectedId = id;
		showCompose(false);
		var pane = document.getElementById("usis-mail-read");
		if (!pane || !api()) return;
		pane.innerHTML = '<p class="text-muted">Loading message…</p>';
		api()
			.fetchJson("/api/v1/mail/messages/" + encodeURIComponent(id))
			.then(function (m) {
				var from = (m.from && (m.from.address || m.from.name)) || "";
				var to = (m.to || [])
					.map(function (a) {
						return a.address || a.name;
					})
					.join(", ");
				var attachments = (m.attachments || [])
					.map(function (a) {
						var href =
							(api().apiBase ? api().apiBase() : "") +
							"/api/v1/mail/messages/" +
							encodeURIComponent(id) +
							"/attachments/" +
							encodeURIComponent(a.id);
						return (
							'<a class="btn btn-sm btn-outline-secondary me-1 mb-1" href="' +
							esc(href) +
							'" target="_blank" rel="noopener">' +
							esc(a.name) +
							"</a>"
						);
					})
					.join("");
				pane.innerHTML =
					'<div class="d-flex justify-content-between align-items-start gap-2 mb-2">' +
					"<div><h5 class='mb-1'>" +
					esc(m.subject) +
					"</h5><div class='small text-muted'>From " +
					esc(from) +
					" · To " +
					esc(to) +
					" · " +
					esc(formatWhen(m.received)) +
					"</div></div>" +
					'<button type="button" class="btn btn-sm btn-outline-danger" id="usis-mail-delete">Delete</button></div>' +
					(attachments ? '<div class="mb-2">' + attachments + "</div>" : "");
				if ((m.body_type || "").toLowerCase() === "html") {
					var frame = document.createElement("iframe");
					frame.setAttribute("sandbox", "");
					frame.setAttribute("referrerpolicy", "no-referrer");
					frame.setAttribute("title", "Message body");
					frame.className = "w-100 border-top pt-3 usis-mail-body-html";
					frame.style.minHeight = "360px";
					frame.srcdoc = String(m.body_content || "").replace(/<\/iframe/gi, "&lt;/iframe");
					pane.appendChild(frame);
				} else {
					var pre = document.createElement("pre");
					pre.className = "border-top pt-3 mb-0";
					pre.style.whiteSpace = "pre-wrap";
					pre.style.fontFamily = "inherit";
					pre.textContent = m.body_content || "";
					pane.appendChild(pre);
				}
				var del = document.getElementById("usis-mail-delete");
				if (del) {
					del.addEventListener("click", function () {
						deleteMessage(id);
					});
				}
				if (!m.is_read && folder === "inbox") {
					api()
						.fetchJson("/api/v1/mail/messages/" + encodeURIComponent(id), {
							method: "PATCH",
							body: { is_read: true },
						})
						.catch(function () {});
				}
				loadList();
			})
			.catch(function (err) {
				pane.innerHTML = '<p class="text-danger">' + esc(err.message || "Could not open message.") + "</p>";
			});
	}

	function deleteMessage(id) {
		if (!api()) return;
		if (!window.confirm("Delete this message? It will move to Deleted Items in Outlook.")) return;
		api()
			.fetchJson("/api/v1/mail/messages/" + encodeURIComponent(id), { method: "DELETE" })
			.then(function () {
				selectedId = null;
				var pane = document.getElementById("usis-mail-read");
				if (pane) pane.innerHTML = '<p class="text-muted mb-0">Message deleted.</p>';
				loadList();
			})
			.catch(function (err) {
				var N = notify();
				if (N) N.error(err.message || "Delete failed");
				else alert(err.message || "Delete failed");
			});
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
		var inbox = document.getElementById("usis-mail-folder-inbox");
		var sent = document.getElementById("usis-mail-folder-sent");
		if (inbox) inbox.addEventListener("click", function () { setFolder("inbox"); });
		if (sent) sent.addEventListener("click", function () { setFolder("sent"); });
		var composeBtn = document.getElementById("usis-mail-compose-btn");
		if (composeBtn) composeBtn.addEventListener("click", function () { showCompose(true); });
		var cancel = document.getElementById("usis-mail-compose-cancel");
		if (cancel) cancel.addEventListener("click", function () { showCompose(false); });
		var form = document.getElementById("usis-mail-compose-form");
		if (form) form.addEventListener("submit", sendCompose);
	});
})();
