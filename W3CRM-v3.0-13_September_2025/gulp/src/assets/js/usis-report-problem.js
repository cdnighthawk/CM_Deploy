/**
 * Header "Report a problem" — files a GitHub issue with the current page URL.
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
		var nameInput = modalEl.querySelector("[name='reporterName']");
		var diagnostics = modalEl.querySelector("[data-usis-report-diagnostics]");
		var statusEl = modalEl.querySelector("[data-usis-report-status]");
		var sendBtn = modalEl.querySelector("[type='submit']");
		var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

		function refreshContext() {
			var ctx = pageContext();
			if (diagnostics) diagnostics.value = diagnosticsText(ctx);
			if (nameInput && !nameInput.value.trim()) nameInput.value = sessionName();
			if (statusEl) {
				statusEl.className = "alert d-none";
				statusEl.textContent = "";
			}
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
			var kind = (form.querySelector("[name='kind']") || {}).value || "bug";
			var reporterName = (form.querySelector("[name='reporterName']") || {}).value || "";
			title = title.trim();
			details = details.trim();
			if (!title || !details) {
				setStatus(statusEl, "danger", "Add a title and details.");
				return;
			}

			var ctx = pageContext();
			if (sendBtn) sendBtn.disabled = true;
			var api = global.USIS_API;
			if (!api || typeof api.fetchJson !== "function") {
				setStatus(statusEl, "danger", "Couldn't send the report. Try again later.");
				if (sendBtn) sendBtn.disabled = false;
				return;
			}

			api
				.fetchJson("/api/v1/feedback", {
					method: "POST",
					body: {
						kind: kind,
						title: title,
						details: details,
						reporterName: reporterName.trim(),
						page: ctx.page,
						pageUrl: ctx.pageUrl,
						pageTitle: ctx.pageTitle,
						userAgent: ctx.userAgent,
					},
				})
				.then(function (data) {
					setStatus(statusEl, "success", (data && data.message) || "Report sent.");
					form.reset();
					if (diagnostics) diagnostics.value = diagnosticsText(pageContext());
					setTimeout(function () {
						modal.hide();
					}, 1400);
				})
				.catch(function (err) {
					var message = "Couldn't send the report. Try again later.";
					try {
						var parsed = err && err.body ? JSON.parse(err.body) : null;
						if (parsed && parsed.error) message = parsed.error;
					} catch (e) {}
					setStatus(statusEl, "danger", message);
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
