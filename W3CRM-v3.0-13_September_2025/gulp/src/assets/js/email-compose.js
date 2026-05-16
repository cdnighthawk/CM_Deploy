/**
 * Wire the W3CRM email-compose page to POST /api/v1/messages/email.
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		return "";
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) return { "X-Usis-User-Id": id.trim() };
		return {};
	}

	function notifyEmailResult(data) {
		var N = window.USISNotify;
		if (!N) return;
		if (data.errors && data.errors.length) {
			N.error("Some messages failed: " + data.errors.join("; "));
			return;
		}
		if (data.dry_run) {
			N.warning(
				"SMTP is not configured on the server (MAIL_SERVER, MAIL_USERNAME, MAIL_FROM). " +
					"Your message was logged only — no email was delivered. Set MAIL_* on Render to send."
			);
			return;
		}
		if (data.queued) {
			N.info("Email queued for delivery.");
			return;
		}
		N.success("Email sent to " + (data.sent || 1) + " recipient(s).");
	}

	function sendEmail() {
		var toEl = document.getElementById("usis-compose-to");
		var subjEl = document.getElementById("usis-compose-subject");
		var bodyEl = document.getElementById("usis-compose-body");
		var btn = document.getElementById("usis-compose-send");
		if (!toEl || !subjEl || !bodyEl) return;

		var to = (toEl.value || "").trim();
		if (!to) {
			if (window.USISNotify) USISNotify.error("Enter at least one recipient in To.");
			else alert("Enter at least one recipient in To.");
			toEl.focus();
			return;
		}

		if (btn) {
			btn.disabled = true;
			btn.setAttribute("aria-busy", "true");
		}

		fetch(apiBase() + "/api/v1/messages/email", {
			method: "POST",
			credentials: "include",
			headers: Object.assign(
				{ Accept: "application/json", "Content-Type": "application/json" },
				actorHeaders()
			),
			body: JSON.stringify({
				to: to,
				subject: (subjEl.value || "").trim(),
				message: (bodyEl.value || "").trim(),
			}),
		})
			.then(function (res) {
				return res.text().then(function (t) {
					var data = {};
					try {
						data = t ? JSON.parse(t) : {};
					} catch (e) {}
					if (!res.ok) {
						var err = new Error(data.error || data.message || t || res.statusText);
						err.status = res.status;
						throw err;
					}
					return data;
				});
			})
			.then(function (data) {
				notifyEmailResult(data);
				toEl.value = "";
				subjEl.value = "";
				bodyEl.value = "";
			})
			.catch(function (err) {
				var msg = err.message || String(err);
				if (err.status === 401) {
					msg = "Sign in required. Open the login page and try again.";
				}
				if (window.USISNotify) USISNotify.error(msg);
				else alert(msg);
			})
			.finally(function () {
				if (btn) {
					btn.disabled = false;
					btn.removeAttribute("aria-busy");
				}
			});
	}

	function init() {
		var send = document.getElementById("usis-compose-send");
		var discard = document.getElementById("usis-compose-discard");
		if (send) send.addEventListener("click", sendEmail);
		if (discard) {
			discard.addEventListener("click", function () {
				["usis-compose-to", "usis-compose-subject", "usis-compose-body"].forEach(function (id) {
					var el = document.getElementById(id);
					if (el) el.value = "";
				});
			});
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
