/**
 * Site-wide Grok assistant. Upgrades the header Chat drawer to POST /api/ai/chat.
 */
(function (global) {
	"use strict";

	if (global.USIS_AI_CHAT) return;

	var path0 = ((global.location && location.pathname) || "").toLowerCase();
	if (/page-login|page-register|page-forgot|page-reset|page-lock|page-error|\/apply\/|apply\.html/.test(path0)) {
		return;
	}

	var STORE_KEY = "usis.ai.chat.v1";
	var SESSION_KEY = "usis.ai.chat.session.v1";
	var MAX_STORED = 40;
	var SEND_WINDOW = 20;
	var MODE_LABELS = {
		construction_review: "Plans",
		estimating_review: "Estimating",
		bid_feasibility_review: "Bid",
		financial_review: "Financials",
		field_review: "Field",
		safety_review: "Safety",
		analytics_review: "Reports",
		submittal_review: "Submittals",
		spec_package_review: "Spec package",
	};

	var MAX_ATTACH = 4;
	var MAX_FILE_BYTES = 6 * 1024 * 1024;
	var FILE_ACCEPT = "image/jpeg,image/png,image/webp,image/gif,application/pdf,text/plain,text/csv,text/markdown,application/json,.txt,.csv,.md,.pdf";

	var state = {
		messages: loadMessages(),
		sessionId: loadSessionId(),
		sessions: [],
		persisted: false,
		historyLoaded: false,
		pending: [],
		sending: false,
		mode: inferMode(),
		status: { enabled: false, model: null, provider: "xai" },
		statusLoaded: false,
		els: {},
	};

	function fetchJson(path, opts) {
		if (global.USIS_API && typeof global.USIS_API.fetchJson === "function") {
			return global.USIS_API.fetchJson(path, opts);
		}
		var o = opts || {};
		var headers = Object.assign({ Accept: "application/json" }, o.headers || {});
		var init = { method: o.method || "GET", headers: headers, credentials: "include" };
		if (o.body !== undefined && o.body !== null) {
			if (!headers["Content-Type"]) headers["Content-Type"] = "application/json";
			init.headers = headers;
			init.body = typeof o.body === "string" ? o.body : JSON.stringify(o.body);
		}
		return fetch(path, init).then(function (res) {
			return res.text().then(function (t) {
				var data = null;
				try {
					data = t ? JSON.parse(t) : null;
				} catch (e) {
					data = t;
				}
				if (!res.ok) {
					var err = new Error((data && data.error) || t || res.statusText);
					err.status = res.status;
					err.body = data;
					throw err;
				}
				return data;
			});
		});
	}

	function inferMode() {
		var p = ((global.location && location.pathname) || "").toLowerCase();
		if (/drawing-viewer|specs-viewer|door-schedule|hardware-schedules/.test(p)) return "construction_review";
		if (/estimate|quotation|pricing/.test(p)) return "estimating_review";
		if (/bid-feasib|lead-detail/.test(p)) return "bid_feasibility_review";
		if (/submittal/.test(p)) return "submittal_review";
		if (/invoice|finance|transaction|procurement/.test(p)) return "financial_review";
		if (/safety/.test(p)) return "safety_review";
		if (/report/.test(p)) return "analytics_review";
		if (/attendance|time-sheet|timesheet|daily/.test(p)) return "field_review";
		return "";
	}

	function modeLabel(mode) {
		return MODE_LABELS[mode] || "Assistant";
	}

	function loadSessionId() {
		try {
			return (global.sessionStorage && sessionStorage.getItem(SESSION_KEY)) || "";
		} catch (e) {
			return "";
		}
	}

	function loadMessages() {
		try {
			var raw = global.sessionStorage && sessionStorage.getItem(STORE_KEY);
			var parsed = raw ? JSON.parse(raw) : [];
			if (!Array.isArray(parsed)) return [];
			return parsed.filter(function (m) {
				return m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string";
			});
		} catch (e) {
			return [];
		}
	}

	function persist() {
		try {
			if (!global.sessionStorage) return;
			var slim = state.messages.slice(-MAX_STORED).map(function (m) {
				var row = { role: m.role, content: m.content };
				if (m.attachments && m.attachments.length) {
					row.attachments = m.attachments.map(function (a) {
						return { kind: a.kind, name: a.name, url: a.url };
					});
				}
				return row;
			});
			sessionStorage.setItem(STORE_KEY, JSON.stringify(slim));
			if (state.sessionId) sessionStorage.setItem(SESSION_KEY, state.sessionId);
			else sessionStorage.removeItem(SESSION_KEY);
		} catch (e) {}
	}

	function closePlusMenu() {
		if (state.els.plusMenu) state.els.plusMenu.classList.add("d-none");
		if (state.els.plus) state.els.plus.setAttribute("aria-expanded", "false");
	}

	function renderPending() {
		var el = state.els.chips;
		if (!el) return;
		el.innerHTML = "";
		state.pending.forEach(function (a, idx) {
			var chip = document.createElement("span");
			chip.className = "usis-ai-chat__chip";
			chip.textContent = a.url ? a.url : a.name || "file";
			var rm = document.createElement("button");
			rm.type = "button";
			rm.className = "usis-ai-chat__chip-x";
			rm.setAttribute("aria-label", "Remove " + (a.name || "attachment"));
			rm.textContent = "×";
			rm.addEventListener("click", function () {
				state.pending.splice(idx, 1);
				renderPending();
			});
			chip.appendChild(rm);
			el.appendChild(chip);
		});
	}

	function addFiles(fileList) {
		if (!fileList || !fileList.length) return;
		Array.prototype.forEach.call(fileList, function (file) {
			if (state.pending.length >= MAX_ATTACH) {
				setStatus("You can attach up to " + MAX_ATTACH + " items.", "error");
				return;
			}
			if (file.size > MAX_FILE_BYTES) {
				setStatus(file.name + " is larger than 6 MB.", "error");
				return;
			}
			var reader = new FileReader();
			reader.onload = function () {
				var result = String(reader.result || "");
				var b64 = result.indexOf(",") >= 0 ? result.split(",")[1] : result;
				state.pending.push({ kind: "file", name: file.name, mime: file.type || "", data: b64 });
				renderPending();
				setStatus("Attached " + file.name, "ok");
			};
			reader.onerror = function () {
				setStatus("Could not read " + file.name, "error");
			};
			reader.readAsDataURL(file);
		});
	}

	function addLink(raw) {
		var url = String(raw || "").trim();
		if (!url) return;
		if (!/^https?:\/\//i.test(url)) url = "https://" + url;
		try {
			var parsed = new URL(url);
			if (parsed.protocol !== "http:" && parsed.protocol !== "https:") throw new Error("bad");
		} catch (e) {
			setStatus("Enter a full http or https link.", "error");
			return;
		}
		if (state.pending.length >= MAX_ATTACH) {
			setStatus("You can attach up to " + MAX_ATTACH + " items.", "error");
			return;
		}
		state.pending.push({ kind: "url", name: url, url: url });
		renderPending();
		if (state.els.link) state.els.link.value = "";
		if (state.els.linkRow) state.els.linkRow.classList.add("d-none");
		setStatus("Added link", "ok");
	}

	function escapeHtml(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function formatText(s) {
		return escapeHtml(s).replace(/\n/g, "<br>");
	}

	function ensureHeaderButton() {
		if (document.querySelector(".btn-chatbox")) return;
		var nav = document.querySelector(".header .navbar-nav.header-right");
		if (!nav) return;
		var li = document.createElement("li");
		li.className = "nav-item align-self-center me-2";
		li.innerHTML =
			'<button type="button" class="btn btn-sm btn-outline-secondary px-2 btn-chatbox" title="Open AI assistant" aria-label="Open AI assistant">' +
			'<i class="icon feather icon-message-square" aria-hidden="true"></i>' +
			'<span class="d-none d-lg-inline ms-1">Chat</span></button>';
		nav.insertBefore(li, nav.firstChild);
	}

	function ensureChatbox() {
		var box = document.querySelector(".chatbox");
		if (!box) {
			box = document.createElement("div");
			box.className = "chatbox";
			box.setAttribute("hidden", "hidden");
			box.setAttribute("aria-hidden", "true");
			box.innerHTML = '<div class="chatbox-close"></div>';
			document.body.appendChild(box);
		}
		box.classList.add("usis-ai-chatbox");
		var close = box.querySelector(".chatbox-close");
		var panel = box.querySelector("[data-usis-ai-chat]");
		if (!panel) {
			panel = document.createElement("div");
			panel.className = "usis-ai-chat";
			panel.setAttribute("data-usis-ai-chat", "1");
			var keep = close ? [close] : [];
			Array.prototype.slice.call(box.childNodes).forEach(function (n) {
				if (keep.indexOf(n) === -1) box.removeChild(n);
			});
			if (close && close.parentNode !== box) box.insertBefore(close, box.firstChild);
			box.appendChild(panel);
			panel.innerHTML =
				'<div class="usis-ai-chat__header">' +
				'<div>' +
				'<div class="usis-overline mb-0">Assistant</div>' +
				'<div class="fw-semibold">USIS + Grok</div>' +
				"</div>" +
				'<div class="d-flex align-items-center gap-2">' +
				'<span class="usis-status-chip usis-status-chip--progress" data-usis-chat-mode>Assistant</span>' +
				'<span class="usis-seg" data-usis-chat-provider title="xAI Grok">' +
				'<span class="btn btn-sm active" aria-pressed="true">Grok</span>' +
				"</span>" +
				"</div>" +
				"</div>" +
				'<div class="usis-ai-chat__toolbar d-none" data-usis-chat-toolbar>' +
				'<label class="visually-hidden" for="usis-ai-chat-history">Saved chats</label>' +
				'<select class="form-select form-select-sm" id="usis-ai-chat-history" data-usis-chat-history></select>' +
				"</div>" +
				'<p class="usis-ai-chat__status small text-muted px-3 mb-0" data-usis-chat-status>Checking Grok…</p>' +
				'<div class="usis-ai-chat__messages" data-usis-chat-log role="log" aria-live="polite"></div>' +
				'<div class="usis-ai-chat__composer">' +
				'<div class="usis-ai-chat__drop d-none" data-usis-chat-drop>Drop files here</div>' +
				'<div class="usis-ai-chat__chips" data-usis-chat-chips></div>' +
				'<form data-usis-chat-form>' +
				'<label class="visually-hidden" for="usis-ai-chat-input">Message</label>' +
				'<textarea class="form-control form-control-sm" id="usis-ai-chat-input" data-usis-chat-input rows="3" placeholder="Ask Grok, or attach a file or link…"></textarea>' +
				'<div class="usis-ai-chat__linkrow d-none" data-usis-chat-linkrow>' +
				'<input type="url" class="form-control form-control-sm" data-usis-chat-link placeholder="https://…" autocomplete="off">' +
				'<button type="button" class="btn btn-sm btn-primary" data-usis-chat-link-add>Add link</button>' +
				"</div>" +
				'<div class="d-flex align-items-center justify-content-between gap-2 mt-2">' +
				'<div class="d-flex align-items-center gap-1">' +
				'<div class="usis-ai-chat__pluswrap">' +
				'<button type="button" class="btn btn-sm btn-outline-secondary usis-ai-chat__plus" data-usis-chat-plus title="Attach a file or link" aria-label="Attach a file or link" aria-expanded="false">+</button>' +
				'<div class="usis-ai-chat__plusmenu d-none" data-usis-chat-plusmenu>' +
				'<button type="button" data-usis-chat-pickfile>From this computer</button>' +
				'<button type="button" data-usis-chat-picklink>Paste a link</button>' +
				"</div>" +
				"</div>" +
				'<input type="file" class="d-none" data-usis-chat-file multiple accept="' +
				FILE_ACCEPT +
				'">' +
				'<button type="button" class="btn btn-sm btn-outline-secondary" data-usis-chat-clear>New</button>' +
				"</div>" +
				'<button type="submit" class="btn btn-sm btn-primary" data-usis-chat-send>Send</button>' +
				"</div>" +
				"</form>" +
				"</div>";
		}
		state.els.box = box;
		state.els.close = box.querySelector(".chatbox-close");
		state.els.panel = panel;
		state.els.log = panel.querySelector("[data-usis-chat-log]");
		state.els.form = panel.querySelector("[data-usis-chat-form]");
		state.els.input = panel.querySelector("[data-usis-chat-input]");
		state.els.send = panel.querySelector("[data-usis-chat-send]");
		state.els.clear = panel.querySelector("[data-usis-chat-clear]");
		state.els.status = panel.querySelector("[data-usis-chat-status]");
		state.els.mode = panel.querySelector("[data-usis-chat-mode]");
		ensureAttachUi(panel);
		ensureHistoryUi(panel);
		if (state.els.mode) state.els.mode.textContent = modeLabel(state.mode);
	}

	function ensureHistoryUi(panel) {
		if (!panel) return;
		if (!panel.querySelector("[data-usis-chat-history]")) {
			var status = panel.querySelector("[data-usis-chat-status]");
			var bar = document.createElement("div");
			bar.className = "usis-ai-chat__toolbar d-none";
			bar.setAttribute("data-usis-chat-toolbar", "1");
			bar.innerHTML =
				'<label class="visually-hidden" for="usis-ai-chat-history">Saved chats</label>' +
				'<select class="form-select form-select-sm" id="usis-ai-chat-history" data-usis-chat-history></select>';
			if (status && status.parentNode) status.parentNode.insertBefore(bar, status);
			else panel.insertBefore(bar, panel.firstChild);
		}
		state.els.toolbar = panel.querySelector("[data-usis-chat-toolbar]");
		state.els.history = panel.querySelector("[data-usis-chat-history]");
	}

	function ensureAttachUi(panel) {
		if (!panel) return;
		var composer = panel.querySelector(".usis-ai-chat__composer");
		if (!composer) return;
		if (!composer.querySelector("[data-usis-chat-plus]")) {
			var form = composer.querySelector("form") || composer;
			var bar = form.querySelector(".d-flex.align-items-center.justify-content-between") || form;
			var plusWrap = document.createElement("div");
			plusWrap.innerHTML =
				'<div class="usis-ai-chat__drop d-none" data-usis-chat-drop>Drop files here</div>' +
				'<div class="usis-ai-chat__chips" data-usis-chat-chips></div>' +
				'<div class="usis-ai-chat__linkrow d-none" data-usis-chat-linkrow>' +
				'<input type="url" class="form-control form-control-sm" data-usis-chat-link placeholder="https://…" autocomplete="off">' +
				'<button type="button" class="btn btn-sm btn-primary" data-usis-chat-link-add>Add link</button>' +
				"</div>" +
				'<div class="usis-ai-chat__pluswrap">' +
				'<button type="button" class="btn btn-sm btn-outline-secondary usis-ai-chat__plus" data-usis-chat-plus title="Attach a file or link" aria-label="Attach a file or link">+</button>' +
				'<div class="usis-ai-chat__plusmenu d-none" data-usis-chat-plusmenu>' +
				'<button type="button" data-usis-chat-pickfile>From this computer</button>' +
				'<button type="button" data-usis-chat-picklink>Paste a link</button>' +
				"</div></div>" +
				'<input type="file" class="d-none" data-usis-chat-file multiple accept="' +
				FILE_ACCEPT +
				'">';
			form.insertBefore(plusWrap, form.firstChild);
			if (bar && !bar.querySelector("[data-usis-chat-plus]")) {
				var first = bar.firstChild;
				var plusBtn = plusWrap.querySelector(".usis-ai-chat__pluswrap");
				if (plusBtn && first) bar.insertBefore(plusBtn, first);
			}
		}
		state.els.drop = panel.querySelector("[data-usis-chat-drop]");
		state.els.chips = panel.querySelector("[data-usis-chat-chips]");
		state.els.plus = panel.querySelector("[data-usis-chat-plus]");
		state.els.plusMenu = panel.querySelector("[data-usis-chat-plusmenu]");
		state.els.file = panel.querySelector("[data-usis-chat-file]");
		state.els.linkRow = panel.querySelector("[data-usis-chat-linkrow]");
		state.els.link = panel.querySelector("[data-usis-chat-link]");
		state.els.linkAdd = panel.querySelector("[data-usis-chat-link-add]");
		state.els.pickFile = panel.querySelector("[data-usis-chat-pickfile]");
		state.els.pickLink = panel.querySelector("[data-usis-chat-picklink]");
	}

	function setStatus(text, kind) {
		if (!state.els.status) return;
		state.els.status.textContent = text;
		state.els.status.classList.remove("text-danger", "text-success", "text-muted");
		state.els.status.classList.add(kind === "error" ? "text-danger" : kind === "ok" ? "text-success" : "text-muted");
	}

	function render() {
		var log = state.els.log;
		if (!log) return;
		log.innerHTML = "";
		if (!state.messages.length) {
			var empty = document.createElement("div");
			empty.className = "text-muted small";
			empty.textContent = state.persisted
				? "Ask Grok about projects, leads, RFIs, or this page. Chats are saved to your account."
				: "Ask Grok about projects, leads, RFIs, or this page. Use + to attach a file from your computer, drop a file here, or paste a link.";
			log.appendChild(empty);
			return;
		}
		state.messages.forEach(function (m) {
			var wrap = document.createElement("div");
			wrap.className = "usis-chat-bubble usis-chat-bubble--" + (m.role === "user" ? "user" : "assistant");
			var who = document.createElement("div");
			who.className = "usis-ai-chat__who";
			who.textContent = m.role === "user" ? "You" : "Grok";
			var body = document.createElement("div");
			body.innerHTML = formatText(m.content);
			wrap.appendChild(who);
			wrap.appendChild(body);
			if (m.attachments && m.attachments.length) {
				var att = document.createElement("div");
				att.className = "usis-ai-chat__attached";
				m.attachments.forEach(function (a) {
					var chip = document.createElement("span");
					chip.className = "usis-ai-chat__chip";
					chip.textContent = a.url ? a.url : a.name || "file";
					att.appendChild(chip);
				});
				wrap.appendChild(att);
			}
			if (m.tools && m.tools.length) {
				var tools = document.createElement("div");
				tools.className = "usis-ai-chat__tools";
				tools.textContent =
					"Used " +
					m.tools
						.map(function (t) {
							return t.name;
						})
						.join(", ");
				wrap.appendChild(tools);
			}
			log.appendChild(wrap);
		});
		log.scrollTop = log.scrollHeight;
	}

	function renderHistory() {
		var sel = state.els.history;
		var bar = state.els.toolbar;
		if (!sel) return;
		if (!state.persisted) {
			if (bar) bar.classList.add("d-none");
			if (state.els.clear) {
				state.els.clear.textContent = "Clear";
				state.els.clear.removeAttribute("title");
			}
			return;
		}
		if (bar) bar.classList.remove("d-none");
		if (state.els.clear) {
			state.els.clear.textContent = "New";
			state.els.clear.title = "Start a new chat. Previous chats stay in your account.";
		}
		var current = state.sessionId || "";
		var known = state.sessions.some(function (s) {
			return s.id === current;
		});
		var html = "";
		if (!current || !known) html += '<option value="">New chat</option>';
		state.sessions.forEach(function (s) {
			html +=
				'<option value="' +
				escapeHtml(s.id) +
				'"' +
				(s.id === current ? " selected" : "") +
				">" +
				escapeHtml(s.title || "Chat") +
				"</option>";
		});
		sel.innerHTML = html;
		if (current && known) sel.value = current;
	}

	function applySession(data) {
		if (!data) return;
		state.sessionId = data.id || "";
		state.messages = (data.messages || []).filter(function (m) {
			return m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string";
		});
		persist();
		render();
		renderHistory();
	}

	function loadSession(id) {
		if (!id) return Promise.resolve();
		return fetchJson("/api/ai/sessions/" + encodeURIComponent(id))
			.then(applySession)
			.catch(function () {});
	}

	function refreshSessionList() {
		return fetchJson("/api/ai/sessions")
			.then(function (data) {
				state.persisted = !!(data && data.persisted);
				state.sessions = (data && data.items) || [];
				renderHistory();
				return data;
			})
			.catch(function () {
				state.persisted = false;
				state.sessions = [];
				renderHistory();
				return null;
			});
	}

	function slimStoredMessages() {
		return state.messages.map(function (m) {
			var row = { role: m.role, content: m.content };
			if (m.attachments && m.attachments.length) row.attachments = m.attachments;
			return row;
		});
	}

	function loadPersisted() {
		return refreshSessionList().then(function (data) {
			if (!data || !data.persisted) return;
			if (state.sessionId) return loadSession(state.sessionId);
			if (data.items && data.items[0]) return loadSession(data.items[0].id);
			if (state.messages.length) {
				return fetchJson("/api/ai/sessions", {
					method: "POST",
					body: { mode: state.mode || "", messages: slimStoredMessages() },
				}).then(function (created) {
					state.sessionId = created && created.id ? created.id : "";
					persist();
					return refreshSessionList();
				});
			}
		});
	}

	function newChat() {
		state.messages = [];
		state.pending = [];
		renderPending();
		if (!state.persisted) {
			state.sessionId = "";
			persist();
			render();
			setStatus("Conversation cleared.", "");
			return Promise.resolve();
		}
		return fetchJson("/api/ai/sessions", { method: "POST", body: { mode: state.mode || "" } })
			.then(function (created) {
				state.sessionId = created && created.id ? created.id : "";
				persist();
				render();
				return refreshSessionList();
			})
			.then(function () {
				setStatus("New chat — saved to your account.", "ok");
			})
			.catch(function () {
				state.sessionId = "";
				persist();
				render();
				setStatus("Started a new chat.", "");
			});
	}

	function openBox() {
		ensureChatbox();
		if (state.els.box) {
			state.els.box.classList.add("active");
			state.els.box.removeAttribute("hidden");
			state.els.box.setAttribute("aria-hidden", "false");
		}
		refreshStatus();
		if (!state.historyLoaded) {
			state.historyLoaded = true;
			loadPersisted();
		} else if (state.persisted) {
			refreshSessionList();
		}
		if (state.els.input) state.els.input.focus();
	}

	function closeBox() {
		if (state.els.box) {
			state.els.box.classList.remove("active");
			state.els.box.setAttribute("hidden", "hidden");
			state.els.box.setAttribute("aria-hidden", "true");
		}
	}

	function setSending(on) {
		state.sending = !!on;
		if (state.els.send) state.els.send.disabled = state.sending;
		if (state.els.input) state.els.input.disabled = state.sending;
		if (state.els.plus) state.els.plus.disabled = state.sending;
	}

	function extractReply(data) {
		if (!data) return "";
		var msg = data.message;
		if (msg && typeof msg === "object") return String(msg.content || "");
		if (typeof msg === "string") return msg;
		if (typeof data.reply === "string") return data.reply;
		if (typeof data.content === "string") return data.content;
		return "";
	}

	function errorMessage(err) {
		var status = err && err.status;
		var body = err && err.body;
		var apiErr = "";
		if (body && typeof body === "object" && body.error) apiErr = String(body.error);
		else if (typeof (err && err.message) === "string") {
			var m = err.message;
			try {
				var parsed = JSON.parse(m.replace(/^\d+\s+/, ""));
				if (parsed && parsed.error) apiErr = String(parsed.error);
			} catch (e) {
				apiErr = m;
			}
		}
		if (status === 401) return "Sign in to use the Grok assistant.";
		if (status === 403) return "Your role does not include the AI assistant.";
		if (status === 503) return apiErr || "Grok is not configured on this server (USIS_AI_ENABLED and USIS_XAI_API_KEY).";
		return apiErr || "Grok could not answer. Try again.";
	}

	function send(text, opts) {
		var o = opts || {};
		var content = String(text || "").trim();
		var pending = (o.attachments || state.pending || []).slice();
		if ((!content && !pending.length) || state.sending) return Promise.resolve();
		if (!content) {
			content = pending.length === 1 ? "Please review this attachment." : "Please review these attachments.";
		}
		if (o.mode) {
			state.mode = o.mode;
			if (state.els.mode) state.els.mode.textContent = modeLabel(state.mode);
		}
		if (o.open !== false) openBox();
		state.messages.push({
			role: "user",
			content: content,
			attachments: pending.map(function (a) {
				return { kind: a.kind, name: a.name, url: a.url };
			}),
		});
		state.pending = [];
		renderPending();
		persist();
		render();
		setSending(true);
		setStatus("Grok is thinking…", "");
		var payload = {
			messages: state.messages.slice(-SEND_WINDOW).map(function (m) {
				return { role: m.role, content: m.content };
			}),
		};
		if (pending.length) {
			payload.attachments = pending.map(function (a) {
				if (a.kind === "url") return { kind: "url", url: a.url, name: a.name };
				return { kind: "file", name: a.name, mime: a.mime || "", data: a.data };
			});
		}
		if (state.mode) payload.mode = state.mode;
		if (o.system_hint || o.systemHint) payload.system_hint = o.system_hint || o.systemHint;
		if (state.sessionId) payload.session_id = state.sessionId;
		return fetchJson("/api/ai/chat", { method: "POST", body: payload })
			.then(function (data) {
				var reply = extractReply(data) || "(No reply)";
				var tools = (data && data.tool_calls_made) || [];
				state.messages.push({
					role: "assistant",
					content: reply,
					tools: tools,
				});
				if (data && data.session_id) state.sessionId = data.session_id;
				if (data && data.persisted) state.persisted = true;
				persist();
				render();
				if (state.persisted) refreshSessionList();
				var model = (data && data.model) || state.status.model || "Grok";
				setStatus((state.persisted ? "Saved · " : "Grok · ") + model, "ok");
				return data;
			})
			.catch(function (err) {
				var msg = errorMessage(err);
				state.messages.push({ role: "assistant", content: msg });
				persist();
				render();
				setStatus(msg, "error");
				throw err;
			})
			.then(function (data) {
				setSending(false);
				return data;
			}, function (err) {
				setSending(false);
				throw err;
			});
	}

	function refreshStatus() {
		return fetchJson("/api/ai/status")
			.then(function (data) {
				state.status = data || state.status;
				state.statusLoaded = true;
				if (data && data.persisted) state.persisted = true;
				if (data && data.enabled) {
					setStatus(
						(state.persisted ? "Saved to your account" : "Grok ready") + (data.model ? " · " + data.model : ""),
						"ok"
					);
				} else {
					setStatus("Grok is not configured on this server yet.", "error");
				}
				renderHistory();
			})
			.catch(function (err) {
				state.statusLoaded = true;
				setStatus(errorMessage(err), "error");
			});
	}

	function bind() {
		ensureHeaderButton();
		ensureChatbox();
		render();

		document.addEventListener("click", function (ev) {
			var openBtn = ev.target.closest && ev.target.closest(".btn-chatbox");
			if (openBtn) {
				ev.preventDefault();
				openBox();
			}
			if (state.els.close && ev.target === state.els.close) {
				closeBox();
			}
		});

		if (state.els.form) {
			state.els.form.addEventListener("submit", function (ev) {
				ev.preventDefault();
				var val = state.els.input ? state.els.input.value : "";
				if (state.els.input) state.els.input.value = "";
				send(val);
			});
		}
		if (state.els.input) {
			state.els.input.addEventListener("keydown", function (ev) {
				if (ev.key === "Enter" && !ev.shiftKey) {
					ev.preventDefault();
					if (state.els.form) state.els.form.requestSubmit();
				}
			});
		}
		if (state.els.clear) {
			state.els.clear.addEventListener("click", function () {
				newChat();
			});
		}
		if (state.els.history) {
			state.els.history.addEventListener("change", function () {
				var id = state.els.history.value;
				if (!id) return;
				loadSession(id);
			});
		}

		if (state.els.plus) {
			state.els.plus.addEventListener("click", function (ev) {
				ev.preventDefault();
				if (!state.els.plusMenu) return;
				var open = state.els.plusMenu.classList.contains("d-none");
				state.els.plusMenu.classList.toggle("d-none", !open);
				state.els.plus.setAttribute("aria-expanded", open ? "true" : "false");
			});
		}
		if (state.els.pickFile) {
			state.els.pickFile.addEventListener("click", function () {
				closePlusMenu();
				if (state.els.file) state.els.file.click();
			});
		}
		if (state.els.pickLink) {
			state.els.pickLink.addEventListener("click", function () {
				closePlusMenu();
				if (state.els.linkRow) state.els.linkRow.classList.toggle("d-none");
				if (state.els.link) state.els.link.focus();
			});
		}
		if (state.els.file) {
			state.els.file.addEventListener("change", function () {
				addFiles(state.els.file.files);
				state.els.file.value = "";
			});
		}
		if (state.els.linkAdd) {
			state.els.linkAdd.addEventListener("click", function () {
				addLink(state.els.link ? state.els.link.value : "");
			});
		}
		if (state.els.link) {
			state.els.link.addEventListener("keydown", function (ev) {
				if (ev.key === "Enter") {
					ev.preventDefault();
					addLink(state.els.link.value);
				}
			});
		}

		var dropRoot = state.els.panel || state.els.box;
		if (dropRoot) {
			["dragenter", "dragover"].forEach(function (evt) {
				dropRoot.addEventListener(evt, function (ev) {
					var types = ev.dataTransfer && ev.dataTransfer.types;
					var hasFiles = types && (types.contains ? types.contains("Files") : Array.prototype.indexOf.call(types, "Files") !== -1);
					if (!hasFiles) {
						return;
					}
					ev.preventDefault();
					if (state.els.drop) state.els.drop.classList.remove("d-none");
				});
			});
			["dragleave", "drop"].forEach(function (evt) {
				dropRoot.addEventListener(evt, function (ev) {
					if (evt === "drop") {
						ev.preventDefault();
						addFiles(ev.dataTransfer && ev.dataTransfer.files);
					}
					if (state.els.drop) state.els.drop.classList.add("d-none");
				});
			});
		}
		document.addEventListener("click", function (ev) {
			if (state.els.plus && state.els.plusMenu && !state.els.plus.contains(ev.target) && !state.els.plusMenu.contains(ev.target)) {
				closePlusMenu();
			}
		});

		if (global.aiReviewBus && typeof global.aiReviewBus.on === "function") {
			function onReview(payload) {
				var p = payload || {};
				if (p.mode) {
					state.mode = p.mode;
					if (state.els.mode) state.els.mode.textContent = modeLabel(state.mode);
				}
				openBox();
			}
			global.aiReviewBus.on("review-request", onReview);
			global.aiReviewBus.on("review_requested", onReview);
		}

		refreshStatus();
		if (!state.historyLoaded) {
			state.historyLoaded = true;
			loadPersisted();
		}
	}

	var api = {
		open: openBox,
		close: closeBox,
		ask: send,
		setMode: function (mode) {
			state.mode = mode || "";
			if (state.els.mode) state.els.mode.textContent = modeLabel(state.mode);
		},
		mode: function () {
			return state.mode;
		},
	};
	global.USIS_AI_CHAT = api;

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", bind);
	} else {
		bind();
	}
})(typeof window !== "undefined" ? window : this);
