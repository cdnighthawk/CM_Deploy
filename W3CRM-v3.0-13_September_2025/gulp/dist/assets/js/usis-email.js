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
	var ICONS = {
		inbox: '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M2.5 5.75A2.25 2.25 0 0 1 4.75 3.5h10.5A2.25 2.25 0 0 1 17.5 5.75v8.5A2.25 2.25 0 0 1 15.25 16.5H4.75A2.25 2.25 0 0 1 2.5 14.25v-8.5Zm1.5 0v.66l6 3.6 6-3.6v-.66a.75.75 0 0 0-.75-.75H4.75a.75.75 0 0 0-.75.75Zm13 2.34-5.72 3.43a1.75 1.75 0 0 1-1.56 0L4 8.09v6.16c0 .41.34.75.75.75h10.5c.41 0 .75-.34.75-.75V8.09Z"/></svg>',
		drafts: '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M14.06 3.44a1.5 1.5 0 0 1 2.12 2.12l-8.5 8.5-3.18.79a.75.75 0 0 1-.91-.91l.79-3.18 8.5-8.5Z"/></svg>',
		sent: '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M2.72 2.05a.75.75 0 0 0-1.01.96l2.4 6.24H9.25a.75.75 0 0 1 0 1.5H4.11l-2.4 6.24a.75.75 0 0 0 1.01.96l15.5-7.25a.75.75 0 0 0 0-1.4L2.72 2.05Z"/></svg>',
		deleted: '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M8.5 4h3a1.5 1.5 0 0 0-3 0ZM7 4a2.5 2.5 0 0 1 5 0h4.25a.75.75 0 0 1 0 1.5h-.84l-.9 9.07A2.75 2.75 0 0 1 11.77 17H8.23a2.75 2.75 0 0 1-2.74-2.43L4.59 5.5H3.75a.75.75 0 0 1 0-1.5H7Z"/></svg>',
		folder: '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M2.5 5.75A2.25 2.25 0 0 1 4.75 3.5h3.06c.4 0 .78.16 1.06.44l.83.83h5.55A2.25 2.25 0 0 1 17.5 7.02v7.23A2.25 2.25 0 0 1 15.25 16.5H4.75A2.25 2.25 0 0 1 2.5 14.25v-8.5Z"/></svg>',
		chevron: '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M4.7 5.8a.75.75 0 0 1 1.06 0L8 8.04l2.24-2.24a.75.75 0 1 1 1.06 1.06l-2.77 2.77a.75.75 0 0 1-1.06 0L4.7 6.86a.75.75 0 0 1 0-1.06Z"/></svg>',
	};

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

	function httpUrl(url) {
		var s = String(url || "").trim();
		if (!s) return "";
		try {
			var u = new URL(s);
			if (u.protocol !== "http:" && u.protocol !== "https:") return "";
			return u.href;
		} catch (e) {
			return "";
		}
	}

	function tagAttr(tag, name) {
		var re = new RegExp("\\b" + name + "\\s*=\\s*(\"[^\"]*\"|'[^']*'|[^\\s>]+)", "i");
		var m = String(tag || "").match(re);
		if (!m) return "";
		return m[1].replace(/^['"]|['"]$/g, "");
	}

	function embedFallback(url) {
		var href = httpUrl(url);
		if (!href) return "";
		var label = /docusign\.(com|net)/i.test(href) ? "Review document in DocuSign" : "Open linked content";
		return (
			'<p style="margin:12px 0"><a href="' +
			esc(href) +
			'" target="_blank" rel="noopener noreferrer">' +
			esc(label) +
			"</a></p>"
		);
	}

	function forceOpenOutside(tagName, attrs) {
		var a = attrs || "";
		if (/\btarget\s*=/i.test(a)) {
			a = a.replace(/\btarget\s*=\s*(['"]?)[^'"\s>]*\1/i, ' target="_blank"');
		} else {
			a += ' target="_blank"';
		}
		if (!/\brel\s*=/i.test(a)) a += ' rel="noopener noreferrer"';
		return "<" + tagName + a + ">";
	}

	function extractActionLinks(html) {
		var seen = {};
		var links = [];
		var re = /<a\b[^>]*href\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
		var m;
		while ((m = re.exec(String(html || "")))) {
			var href = httpUrl(m[1]);
			if (!href || seen[href]) continue;
			var text = String(m[2] || "")
				.replace(/<[^>]+>/g, " ")
				.replace(/\s+/g, " ")
				.trim();
			var docusign = /docusign\.(com|net)/i.test(href);
			var review = /review\s+document/i.test(text);
			if (!docusign && !review) continue;
			seen[href] = true;
			links.push({
				href: href,
				label: docusign ? "Review document in DocuSign" : text || "Open linked content",
			});
		}
		return links;
	}

	function prepareMailHtml(raw) {
		var html = String(raw || "");
		html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "");
		html = html.replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, "");
		html = html.replace(/<iframe\b[^>]*(?:\/>|>[\s\S]*?<\/iframe>|>)/gi, function (tag) {
			return embedFallback(tagAttr(tag, "src"));
		});
		html = html.replace(/<(object|embed|frame)\b[^>]*>/gi, function (tag) {
			return embedFallback(tagAttr(tag, "src") || tagAttr(tag, "data"));
		});
		html = html.replace(/<a\b([^>]*)>/gi, function (_, attrs) {
			var rawHref = tagAttr("<a" + attrs + ">", "href");
			if (rawHref && !httpUrl(rawHref) && !/^mailto:/i.test(rawHref)) {
				attrs = attrs.replace(/\bhref\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/i, ' href="#"');
			}
			return forceOpenOutside("a", attrs);
		});
		html = html.replace(/<form\b([^>]*)>/gi, function (_, attrs) {
			return forceOpenOutside("form", attrs);
		});
		html = html.replace(/<\/iframe/gi, "&lt;/iframe");
		var headBits =
			'<meta charset="utf-8"><meta name="referrer" content="no-referrer">' +
			'<base target="_blank">' +
			"<style>html,body{margin:0;padding:8px 12px;background:#fff;color:#242424;" +
			"font-family:'Segoe UI',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45}" +
			"img{max-width:100%;height:auto}a{color:#0f6cbd}noscript{display:none!important}</style>";
		if (/<head[\s>]/i.test(html)) {
			html = html.replace(/<head([^>]*)>/i, "<head$1>" + headBits);
		} else if (/<html[\s>]/i.test(html)) {
			html = html.replace(/<html([^>]*)>/i, "<html$1><head>" + headBits + "</head>");
		} else {
			html = "<!DOCTYPE html><html><head>" + headBits + "</head><body>" + html + "</body></html>";
		}
		return html;
	}

	function displayName(m) {
		var from = (m.from && (m.from.name || m.from.address)) || "";
		if (isSentFolder()) {
			var to0 = (m.to && m.to[0]) || {};
			from = to0.name || to0.address || from;
		}
		return from;
	}

	function isSentFolder() {
		var key = String(folder || "").toLowerCase();
		return key === "sent" || key === "sentitems";
	}

	function folderIcon(node) {
		var well = String((node && (node.well_known || node.key)) || "").toLowerCase();
		if (well === "inbox") return ICONS.inbox;
		if (well === "drafts") return ICONS.drafts;
		if (well === "sent" || well === "sentitems") return ICONS.sent;
		if (well === "deleted" || well === "deleteditems") return ICONS.deleted;
		return ICONS.folder;
	}

	function folderId(node) {
		return (node && (node.key || node.id)) || "";
	}

	function rememberTitles(nodes) {
		(nodes || []).forEach(function (n) {
			var id = folderId(n);
			if (id && n.name) FOLDER_TITLES[id] = n.name;
			rememberTitles(n.children);
		});
	}

	function renderFolderNode(node, depth) {
		var id = folderId(node);
		var kids = (node && node.children) || [];
		var unread = node.unread
			? '<span class="usis-ol-folder-unread">' + esc(String(node.unread)) + "</span>"
			: "";
		var toggle = kids.length
			? '<button type="button" class="usis-ol-folder-toggle" data-toggle-folder="' +
			  esc(id) +
			  '" aria-label="Toggle ' +
			  esc(node.name || "folder") +
			  '" aria-expanded="true">' +
			  ICONS.chevron +
			  "</button>"
			: '<span class="usis-ol-folder-toggle is-leaf" aria-hidden="true"></span>';
		var html =
			'<div class="usis-ol-folder-block"><div class="usis-ol-folder-row" style="padding-left:' +
			(depth * 12) +
			'px">' +
			toggle +
			'<button type="button" class="usis-ol-folder" data-folder="' +
			esc(id) +
			'" data-name="' +
			esc(node.name || "") +
			'" title="' +
			esc(node.name || "") +
			'">' +
			folderIcon(node) +
			'<span class="usis-ol-folder-name">' +
			esc(node.name || "Folder") +
			"</span>" +
			unread +
			"</button></div>";
		if (kids.length) {
			html +=
				'<div class="usis-ol-folder-children">' +
				kids
					.map(function (child) {
						return renderFolderNode(child, depth + 1);
					})
					.join("") +
				"</div>";
		}
		return html + "</div>";
	}

	function markActiveFolder() {
		document.querySelectorAll("[data-folder]").forEach(function (btn) {
			btn.classList.toggle("is-active", btn.getAttribute("data-folder") === folder);
		});
	}

	function bindFolderNav() {
		document.querySelectorAll("[data-folder]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				setFolder(btn.getAttribute("data-folder"), btn.getAttribute("data-name"));
			});
		});
		document.querySelectorAll("[data-toggle-folder]").forEach(function (btn) {
			btn.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				var block = btn.closest(".usis-ol-folder-block");
				if (!block) return;
				var collapsed = block.classList.toggle("is-collapsed");
				btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
			});
		});
	}

	function loadFolders() {
		var nav = document.getElementById("usis-mail-folders");
		if (!nav || !api()) return;
		api()
			.fetchJson("/api/v1/mail/folders")
			.then(function (data) {
				var items = (data && data.items) || [];
				if (!items.length) return;
				rememberTitles(items);
				nav.innerHTML = items
					.map(function (n) {
						return renderFolderNode(n, 0);
					})
					.join("");
				bindFolderNav();
				markActiveFolder();
			})
			.catch(function () {});
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

	function setFolder(next, name) {
		folder = next;
		selectedId = null;
		selectedMeta = null;
		markActiveFolder();
		var title = document.getElementById("usis-mail-folder-title");
		if (title) title.textContent = name || FOLDER_TITLES[folder] || "Mail";
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
				if (!m.is_read) cls += " is-unread";
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
				var bodyHtml = String(m.body_content || "");
				var actionLinks =
					(m.body_type || "").toLowerCase() === "html" ? extractActionLinks(bodyHtml) : [];
				var actionBar = actionLinks
					.map(function (link) {
						return (
							'<a class="usis-ol-mail-action" href="' +
							esc(link.href) +
							'" target="_blank" rel="noopener noreferrer">' +
							esc(link.label) +
							"</a>"
						);
					})
					.join("");
				pane.innerHTML =
					(attachments ? '<div class="usis-ol-files">' + attachments + "</div>" : "") +
					(actionBar ? '<div class="usis-ol-mail-actions">' + actionBar + "</div>" : "");
				if ((m.body_type || "").toLowerCase() === "html") {
					var frame = document.createElement("iframe");
					frame.setAttribute(
						"sandbox",
						"allow-popups allow-popups-to-escape-sandbox allow-forms"
					);
					frame.setAttribute("referrerpolicy", "no-referrer");
					frame.setAttribute("title", "Message body");
					frame.srcdoc = prepareMailHtml(bodyHtml);
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
				if (!m.is_read) {
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
				if (isSentFolder()) loadList();
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
		bindFolderNav();
		loadFolders();
		loadList();
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
