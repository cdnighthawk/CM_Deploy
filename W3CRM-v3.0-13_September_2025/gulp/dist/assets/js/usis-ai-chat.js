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
	};

	var state = {
		messages: loadMessages(),
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
			sessionStorage.setItem(STORE_KEY, JSON.stringify(state.messages.slice(-MAX_STORED)));
		} catch (e) {}
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
				'<p class="usis-ai-chat__status small text-muted px-3 mb-0" data-usis-chat-status>Checking Grok…</p>' +
				'<div class="usis-ai-chat__messages" data-usis-chat-log role="log" aria-live="polite"></div>' +
				'<div class="usis-ai-chat__composer">' +
				'<form data-usis-chat-form>' +
				'<label class="visually-hidden" for="usis-ai-chat-input">Message</label>' +
				'<textarea class="form-control form-control-sm" id="usis-ai-chat-input" data-usis-chat-input rows="3" placeholder="Ask Grok about projects, leads, RFIs…"></textarea>' +
				'<div class="d-flex align-items-center justify-content-between gap-2 mt-2">' +
				'<button type="button" class="btn btn-sm btn-outline-secondary" data-usis-chat-clear>Clear</button>' +
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
		if (state.els.mode) state.els.mode.textContent = modeLabel(state.mode);
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
			empty.textContent =
				"Ask Grok about projects, leads, RFIs, estimates, or what is on this page. It can look up live USIS records you are allowed to see.";
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

	function openBox() {
		ensureChatbox();
		if (state.els.box) state.els.box.classList.add("active");
		refreshStatus();
		if (state.els.input) state.els.input.focus();
	}

	function closeBox() {
		if (state.els.box) state.els.box.classList.remove("active");
	}

	function setSending(on) {
		state.sending = !!on;
		if (state.els.send) state.els.send.disabled = state.sending;
		if (state.els.input) state.els.input.disabled = state.sending;
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
		if (!content || state.sending) return Promise.resolve();
		if (o.mode) {
			state.mode = o.mode;
			if (state.els.mode) state.els.mode.textContent = modeLabel(state.mode);
		}
		if (o.open !== false) openBox();
		state.messages.push({ role: "user", content: content });
		persist();
		render();
		setSending(true);
		setStatus("Grok is thinking…", "");
		var payload = {
			messages: state.messages.slice(-SEND_WINDOW).map(function (m) {
				return { role: m.role, content: m.content };
			}),
		};
		if (state.mode) payload.mode = state.mode;
		return fetchJson("/api/ai/chat", { method: "POST", body: payload })
			.then(function (data) {
				var reply = extractReply(data) || "(No reply)";
				var tools = (data && data.tool_calls_made) || [];
				state.messages.push({
					role: "assistant",
					content: reply,
					tools: tools,
				});
				persist();
				render();
				var model = (data && data.model) || state.status.model || "Grok";
				setStatus("Grok · " + model, "ok");
			})
			.catch(function (err) {
				var msg = errorMessage(err);
				state.messages.push({ role: "assistant", content: msg });
				persist();
				render();
				setStatus(msg, "error");
			})
			.then(function () {
				setSending(false);
			});
	}

	function refreshStatus() {
		return fetchJson("/api/ai/status")
			.then(function (data) {
				state.status = data || state.status;
				state.statusLoaded = true;
				if (data && data.enabled) {
					setStatus("Grok ready" + (data.model ? " · " + data.model : ""), "ok");
				} else {
					setStatus("Grok is not configured on this server yet.", "error");
				}
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
				state.messages = [];
				persist();
				render();
				setStatus("Conversation cleared.", "");
			});
		}

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
