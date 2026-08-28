(function () {
	"use strict";

	var STATUSES = ["New", "Triaged", "In Progress", "Pending Review", "Resolved", "Closed"];
	var SOURCE_LABELS = {
		ai_review: "AI Review",
		rfi: "RFI",
		punch: "Punch",
		field: "Field",
		safety: "Safety",
		manual: "Manual",
		feedback: "Website",
	};
	var state = { items: [], view: "kanban", selected: null, summary: {} };

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	function sourceLabel(value) {
		var label = SOURCE_LABELS[value] || value || "";
		return t(label);
	}

	function issueNumber(issue) {
		if (issue && issue.number) return "#" + issue.number;
		var linked = issue && issue.linked_change_order_id ? String(issue.linked_change_order_id) : "";
		var match = /^github:(\d+)$/i.exec(linked);
		return match ? "#" + match[1] : "";
	}

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		if (window.location.protocol === "file:") return "http://127.0.0.1:5000";
		return "";
	}

	function qs(name) {
		return new URLSearchParams(window.location.search).get(name);
	}

	function esc(value) {
		var d = document.createElement("div");
		d.textContent = value == null ? "" : String(value);
		return d.innerHTML;
	}

	function projectId() {
		var sel = document.getElementById("usis-issue-project");
		if (sel && sel.options && sel.options.length) {
			return sel.value || "";
		}
		return qs("project_id") || qs("projectId") || "";
	}

	function notify(kind, message) {
		if (window.USISNotify && window.USISNotify[kind]) window.USISNotify[kind](message);
	}

	function fetchJson(path, opts) {
		opts = opts || {};
		return fetch(apiBase() + path, {
			method: opts.method || "GET",
			headers: Object.assign({ Accept: "application/json" }, opts.body ? { "Content-Type": "application/json" } : {}),
			credentials: "include",
			body: opts.body ? JSON.stringify(opts.body) : undefined,
		}).then(function (res) {
			return res.json().then(function (data) {
				if (!res.ok) throw new Error(data.error || res.statusText || "Request failed");
				return data;
			});
		});
	}

	function queryString() {
		var p = new URLSearchParams();
		var pid = projectId();
		if (pid) p.set("project_id", pid);
		var status = document.getElementById("usis-issue-status").value;
		var severity = document.getElementById("usis-issue-severity").value;
		var trade = document.getElementById("usis-issue-trade").value;
		var source = document.getElementById("usis-issue-source").value;
		var search = document.getElementById("usis-issue-search").value.trim();
		if (status) p.set("status", status);
		if (severity) p.set("severity", severity);
		if (trade) p.set("trade", trade);
		if (source) p.set("source_type", source);
		if (search) p.set("search", search);
		return p.toString();
	}

	function loadProjects() {
		return fetchJson("/api/v1/projects").then(function (data) {
			var items = data.items || data.projects || [];
			var sel = document.getElementById("usis-issue-project");
			var current = qs("project_id") || qs("projectId") || "";
			sel.innerHTML =
				'<option value="" data-i18n="All projects">' +
				t("All projects") +
				"</option>" +
				items
					.map(function (p) {
						return '<option value="' + esc(p.id) + '">' + esc(p.name || p.title || p.id) + "</option>";
					})
					.join("");
			if (current) sel.value = current;
		});
	}

	function load(opts) {
		var silent = opts && opts.silent;
		if (!silent) document.getElementById("usis-issue-count").textContent = t("Loading…");
		return fetchJson("/api/v1/issues?" + queryString())
			.then(function (data) {
				state.items = data.items || [];
				state.summary = data.summary || {};
				paintCount();
				render();
			})
			.catch(function (err) {
				if (!silent) {
					document.getElementById("usis-issue-count").textContent = t("Could not load issues");
					notify("error", err.message);
				}
			});
	}

	function paintCount() {
		var el = document.getElementById("usis-issue-count");
		if (!el) return;
		el.textContent = t("{n} shown · {c} open critical")
			.replace("{n}", state.items.length)
			.replace("{c}", (state.summary && state.summary.open_critical) || 0);
	}

	function cardHtml(issue) {
		return (
			'<button type="button" class="usis-issue-card" data-id="' +
			esc(issue.id) +
			'">' +
			'<div class="d-flex justify-content-between align-items-center"><span class="fw-semibold">' +
			esc(issueNumber(issue) || "—") +
			'</span><span class="badge usis-issue-sev-' +
			esc(issue.severity) +
			'">' +
			esc(t(issue.severity || "")) +
			"</span></div>" +
			'<div class="fw-semibold mt-2">' +
			esc(issue.title) +
			"</div>" +
			'<div class="usis-issue-card-desc mt-1">' +
			esc(issue.description) +
			"</div>" +
			'<div class="d-flex flex-wrap gap-1 mt-2">' +
			'<span class="badge text-bg-light">' +
			esc(t(issue.trade || "")) +
			"</span>" +
			'<span class="badge text-bg-light">' +
			esc(sourceLabel(issue.source_type)) +
			"</span></div>" +
			'<div class="small text-muted mt-2">' +
			esc(issue.assignee_name || t("Unassigned")) +
			"</div></button>"
		);
	}

	function renderKanban() {
		var root = document.getElementById("usis-issue-kanban");
		root.innerHTML = STATUSES.map(function (status) {
			var cards = state.items.filter(function (item) {
				return item.status === status;
			});
			return (
				'<section class="usis-issue-col" data-status="' +
				esc(status) +
				'"><div class="usis-issue-col-head"><h3>' +
				esc(t(status)) +
				'</h3><span class="badge text-bg-light">' +
				cards.length +
				"</span></div><div class=\"usis-issue-col-body\">" +
				(cards.map(cardHtml).join("") || '<div class="small text-muted">' + t("No issues") + "</div>") +
				"</div></section>"
			);
		}).join("");
		root.querySelectorAll(".usis-issue-card").forEach(function (btn) {
			btn.addEventListener("click", function () {
				openIssue(btn.getAttribute("data-id"));
			});
		});
	}

	function renderTable() {
		var tb = document.getElementById("usis-issue-tbody");
		if (!state.items.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted text-center py-4">' + t("No issues yet.") + "</td></tr>";
			return;
		}
		tb.innerHTML = state.items
			.map(function (issue) {
				return (
					"<tr data-id=\"" +
					esc(issue.id) +
					"\"><td>" +
					esc(issueNumber(issue) || "—") +
					"</td><td>" +
					esc(t(issue.severity || "")) +
					"</td><td>" +
					esc(issue.title) +
					"</td><td>" +
					esc(t(issue.status || "")) +
					"</td><td>" +
					esc(t(issue.trade || "")) +
					"</td><td>" +
					esc(sourceLabel(issue.source_type)) +
					(issue.sheet_number ? " · " + esc(issue.sheet_number) : "") +
					"</td><td>" +
					esc(issue.assignee_name || "—") +
					"</td></tr>"
				);
			})
			.join("");
		tb.querySelectorAll("tr[data-id]").forEach(function (row) {
			row.addEventListener("click", function () {
				openIssue(row.getAttribute("data-id"));
			});
		});
	}

	function render() {
		var kanban = document.getElementById("usis-issue-kanban");
		var table = document.getElementById("usis-issue-table-wrap");
		if (state.view === "table") {
			kanban.classList.add("d-none");
			table.classList.remove("d-none");
			renderTable();
		} else {
			table.classList.add("d-none");
			kanban.classList.remove("d-none");
			renderKanban();
		}
	}

	function openIssue(id) {
		fetchJson("/api/v1/issues/" + encodeURIComponent(id))
			.then(function (data) {
				state.selected = data.issue;
				var issue = data.issue;
				document.getElementById("usis-issue-drawer-title").textContent =
					(issueNumber(issue) ? issueNumber(issue) + " " : "") + issue.title;
				var viewer = "";
				if (issue.drawing_id) {
					viewer =
						'<a class="btn btn-sm btn-outline-secondary" href="construction/drawing-viewer.html?drawing_id=' +
						encodeURIComponent(issue.drawing_id) +
						(issue.project_id ? "&project_id=" + encodeURIComponent(issue.project_id) : "") +
						(issue.source_id ? "&annotation_id=" + encodeURIComponent(issue.source_id) : "") +
						'">' +
						t("Open in DrawingViewer") +
						"</a>";
				}
				document.getElementById("usis-issue-drawer-body").innerHTML =
					'<p class="text-muted">' +
					esc(issue.description || t("No description yet.")) +
					"</p>" +
					'<div class="d-flex flex-wrap gap-1 mb-3"><span class="badge usis-issue-sev-' +
					esc(issue.severity) +
					'">' +
					esc(t(issue.severity || "")) +
					'</span><span class="badge text-bg-light">' +
					esc(t(issue.trade || "")) +
					'</span><span class="badge text-bg-light">' +
					esc(sourceLabel(issue.source_type)) +
					"</span></div>" +
					'<div class="mb-3"><span class="badge text-bg-primary">' +
					esc(t(issue.status || "")) +
					"</span></div>" +
					'<div class="d-flex flex-wrap gap-2 mb-3">' +
					'<button type="button" class="btn btn-sm btn-primary" id="usis-issue-create-co">' +
					t("Create Change Order") +
					"</button>" +
					'<button type="button" class="btn btn-sm btn-outline-primary" id="usis-issue-create-rfi">' +
					t("Create RFI") +
					"</button>" +
					viewer +
					"</div>" +
					(issue.events && issue.events.length
						? "<h3 class=\"h6\">" + t("History") + "</h3><ul class=\"usis-issue-history\">" +
							issue.events
								.map(function (event) {
									return (
										"<li><strong>" +
										esc(event.action) +
										"</strong>" +
										(event.detail ? " — " + esc(event.detail) : "") +
										'<div class="small text-muted">' +
										esc(event.created_by_name || "System") +
										"</div></li>"
									);
								})
								.join("") +
							"</ul>"
						: "");
				var canvas = document.getElementById("usis-issue-drawer");
				if (window.bootstrap && window.bootstrap.Offcanvas) {
					window.bootstrap.Offcanvas.getOrCreateInstance(canvas).show();
				} else {
					canvas.classList.add("show");
				}
				document.getElementById("usis-issue-create-rfi").addEventListener("click", function () {
					fetchJson("/api/v1/issues/" + encodeURIComponent(issue.id) + "/create-rfi", { method: "POST" })
						.then(function (result) {
							notify("success", t("RFI prefill ready"));
							if (result.redirect_to) window.location.href = result.redirect_to;
						})
						.catch(function (err) {
							notify("error", err.message);
						});
				});
				document.getElementById("usis-issue-create-co").addEventListener("click", function () {
					fetchJson("/api/v1/issues/" + encodeURIComponent(issue.id) + "/create-co", { method: "POST" })
						.then(function (result) {
							notify("success", t("Change order prepared from this issue"));
							if (result.redirect_to) window.location.href = result.redirect_to;
						})
						.catch(function (err) {
							notify("error", err.message);
						});
				});
			})
			.catch(function (err) {
				notify("error", err.message);
			});
	}

	function setView(view) {
		state.view = view;
		document.getElementById("usis-issue-view-kanban").className =
			"btn btn-sm " + (view === "kanban" ? "btn-primary" : "btn-outline-primary");
		document.getElementById("usis-issue-view-table").className =
			"btn btn-sm " + (view === "table" ? "btn-primary" : "btn-outline-primary");
		render();
	}

	document.addEventListener("DOMContentLoaded", function () {
		["usis-issue-project", "usis-issue-status", "usis-issue-severity", "usis-issue-trade", "usis-issue-source"].forEach(
			function (id) {
				document.getElementById(id).addEventListener("change", load);
			}
		);
		document.getElementById("usis-issue-search").addEventListener("input", function () {
			clearTimeout(window.__usisIssueSearch);
			window.__usisIssueSearch = setTimeout(load, 250);
		});
		document.getElementById("usis-issue-refresh").addEventListener("click", load);
		document.getElementById("usis-issue-view-kanban").addEventListener("click", function () {
			setView("kanban");
		});
		document.getElementById("usis-issue-view-table").addEventListener("click", function () {
			setView("table");
		});
		document.getElementById("usis-issue-new").addEventListener("click", function () {
			var modal = document.getElementById("usis-issue-new-modal");
			if (window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(modal).show();
		});
		document.getElementById("usis-issue-new-form").addEventListener("submit", function (ev) {
			ev.preventDefault();
			var form = ev.target;
			var body = {
				title: form.title.value,
				description: form.description.value,
				severity: form.severity.value,
				trade: form.trade.value,
				source_type: form.source_type.value,
				project_id: projectId() || undefined,
			};
			fetchJson("/api/v1/issues", { method: "POST", body: body })
				.then(function (data) {
					notify("success", t("Issue created"));
					var modal = document.getElementById("usis-issue-new-modal");
					if (window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(modal).hide();
					form.reset();
					return load().then(function () {
						if (data.issue) openIssue(data.issue.id);
					});
				})
				.catch(function (err) {
					notify("error", err.message);
				});
		});
		if (window.aiReviewBus && window.aiReviewBus.on) {
			window.aiReviewBus.on("review-complete", function () {
				notify("info", t("AI review findings added to Issues"));
				load();
			});
		}
		if (qs("track") === "1") {
			var form = document.getElementById("usis-issue-new-form");
			form.title.value = qs("title") || "";
			form.description.value = qs("description") || "";
			var modal = document.getElementById("usis-issue-new-modal");
			if (window.bootstrap && window.bootstrap.Modal) window.bootstrap.Modal.getOrCreateInstance(modal).show();
		}
		document.addEventListener("usis:languagechange", function () {
			var sel = document.getElementById("usis-issue-project");
			if (sel && sel.options && sel.options[0] && !sel.options[0].value) {
				sel.options[0].textContent = t("All projects");
			}
			if (state.items) paintCount();
			render();
		});
		loadProjects().finally(load);
		setInterval(function () {
			if (document.hidden) return;
			load({ silent: true });
		}, 12000);
	});
})();
