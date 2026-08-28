/**
 * Header "Report a problem" — files an internal Issues-page report. Page-specific
 * kinds include the URL; a general recommendation stays site-wide.
 */
(function (global) {
	"use strict";

	function pageContext() {
		var loc = global.location || {};
		return {
			page: loc.pathname || "",
			pageUrl: loc.href || "",
			pageTitle: (global.document && document.title) || "",
			userAgent: (global.navigator && navigator.userAgent) || "",
		};
	}

	function diagnosticsText(ctx) {
		return [
			"Page: " + (ctx.page || "(unknown)"),
			"Page URL: " + (ctx.pageUrl || "(unknown)"),
			ctx.pageTitle ? "Page title: " + ctx.pageTitle : "",
		]
			.filter(Boolean)
			.join("\n");
	}

	function sessionName() {
		var el = document.querySelector(".usis-header-session-name");
		var name = el && el.textContent ? el.textContent.trim() : "";
		return name && name !== "—" ? name : "";
	}

	function setStatus(el, kind, message) {
		if (!el) return;
		el.className = "alert alert-" + kind;
		el.textContent = message;
		el.classList.remove("d-none");
	}

	function bind() {
		var openBtns = document.querySelectorAll("[data-usis-report-problem]");
		var modalEl = document.getElementById("usis-report-problem-modal");
		if (!openBtns.length || !modalEl || !global.bootstrap) return;

		var form = modalEl.querySelector("form");
		var kindSelect = modalEl.querySelector("[name='kind']");
		var nameInput = modalEl.querySelector("[name='reporterName']");
		var diagnostics = modalEl.querySelector("[data-usis-report-diagnostics]");
		var pageBlock = modalEl.querySelector("[data-usis-report-page-block]");
		var sitewideNote = modalEl.querySelector("[data-usis-report-sitewide]");
		var statusEl = modalEl.querySelector("[data-usis-report-status]");
		var sendBtn = modalEl.querySelector("[type='submit']");
		var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

		function isGeneral() {
			return kindSelect && kindSelect.value === "general";
		}

		function syncKindUi() {
			var general = isGeneral();
			if (pageBlock) pageBlock.classList.toggle("d-none", general);
			if (sitewideNote) sitewideNote.classList.toggle("d-none", !general);
		}

		function refreshContext() {
			var ctx = pageContext();
			if (diagnostics) diagnostics.value = diagnosticsText(ctx);
			if (nameInput && !nameInput.value.trim()) nameInput.value = sessionName();
			if (statusEl) {
				statusEl.className = "alert d-none";
				statusEl.textContent = "";
			}
			syncKindUi();
		}

		if (kindSelect) {
			kindSelect.addEventListener("change", syncKindUi);
		}

		openBtns.forEach(function (btn) {
			btn.addEventListener("click", function () {
				refreshContext();
				modal.show();
			});
		});

		modalEl.addEventListener("show.bs.modal", refreshContext);

		if (!form) return;
		form.addEventListener("submit", function (event) {
			event.preventDefault();
			var title = (form.querySelector("[name='title']") || {}).value || "";
			var details = (form.querySelector("[name='details']") || {}).value || "";
			var kind = (kindSelect && kindSelect.value) || "bug";
			var reporterName = (form.querySelector("[name='reporterName']") || {}).value || "";
			title = title.trim();
			details = details.trim();
			if (!title || !details) {
				setStatus(statusEl, "danger", "Add a title and details.");
				return;
			}

			var ctx = pageContext();
			var payload = {
				kind: kind,
				title: title,
				details: details,
				reporterName: reporterName.trim(),
				userAgent: ctx.userAgent,
			};
			if (kind !== "general") {
				payload.page = ctx.page;
				payload.pageUrl = ctx.pageUrl;
				payload.pageTitle = ctx.pageTitle;
			}
			if (sendBtn) sendBtn.disabled = true;
			var api = global.USIS_API;
			if (!api || typeof api.fetchJson !== "function") {
				setStatus(statusEl, "danger", "Couldn't send the report. Try again later.");
				if (sendBtn) sendBtn.disabled = false;
				return;
			}

			function isRetryable(err) {
				return Boolean(err && (err.status === 502 || err.status === 503));
			}

			function errorMessage(err) {
				try {
					var parsed = err && err.body ? JSON.parse(err.body) : null;
					if (parsed && parsed.error) return parsed.error;
				} catch (e) {}
				if (isRetryable(err)) {
					return "The site was updating. Try sending again.";
				}
				return "Couldn't send the report. Try again later.";
			}

			function sendReport(attempt) {
				return api
					.fetchJson("/api/v1/feedback", {
						method: "POST",
						body: payload,
					})
					.catch(function (err) {
						if (attempt < 1 && isRetryable(err)) {
							return new Promise(function (resolve) {
								setTimeout(resolve, 1500);
							}).then(function () {
								return sendReport(attempt + 1);
							});
						}
						throw err;
					});
			}

			sendReport(0)
				.then(function (data) {
					setStatus(statusEl, "success", (data && data.message) || "Report sent.");
					form.reset();
					if (diagnostics) diagnostics.value = diagnosticsText(pageContext());
					syncKindUi();
					setTimeout(function () {
						modal.hide();
					}, 1400);
				})
				.catch(function (err) {
					setStatus(statusEl, "danger", errorMessage(err));
				})
				.finally(function () {
					if (sendBtn) sendBtn.disabled = false;
				});
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", bind);
	} else {
		bind();
	}
})(typeof window !== "undefined" ? window : this);
