(function () {
	"use strict";

	var CLOSED_RFP = { awarded: 1, closed: 1, cancelled: 1, canceled: 1, void: 1 };

	function fetchJson(path, opts) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path, opts);
		return fetch(path, { credentials: "include", headers: { Accept: "application/json" } }).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
				return j;
			});
		});
	}

	function fill(id, value) {
		var el = document.getElementById(id);
		if (el) el.textContent = value == null ? "—" : String(value);
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function setQueue(id, html) {
		var el = document.getElementById(id);
		if (el) el.innerHTML = html;
	}

	function emptyRow(text) {
		return '<div class="list-group-item text-muted small">' + esc(text) + "</div>";
	}

	function showSecondary(body) {
		var row = document.getElementById("usis-dash-kpi-secondary");
		if (!row) return;
		var ai = Number(body.aiCritical) || 0;
		var rubber = Number(body.rubberStampSuspectThisWeek) || 0;
		var late = Number(body.poLate) || 0;
		row.classList.toggle("d-none", ai < 1 && rubber < 1 && late < 1);
	}

	function loadKpis() {
		return fetchJson("/api/v1/dashboard/ops-kpis")
			.then(function (body) {
				fill("usis-dash-open-rfps", body.openRfps);
				fill("usis-dash-qc-aging", body.qcAging);
				fill("usis-dash-ai-critical", body.aiCritical);
				fill("usis-dash-po-transit", body.poInTransit);
				fill("usis-dash-po-late", body.poLate);
				fill("usis-dash-sub-overdue", body.submittalsOverdue);
				fill("usis-dash-sub-rubber", body.rubberStampSuspectThisWeek);
				fill("usis-dash-sub-block", body.unreleasedBlockingPos);
				showSecondary(body);
				var n = Number(body.unreleasedBlockingPos) || 0;
				if (n < 1) {
					setQueue("usis-dash-queue-pos", emptyRow("Nothing is blocking buyout."));
				} else {
					setQueue(
						"usis-dash-queue-pos",
						'<a class="list-group-item list-group-item-action" href="usis-procurement.html">' +
							esc(n + " unreleased submittals are holding procurement.") +
							"</a>"
					);
				}
				return body;
			})
			.catch(function () {
				setQueue("usis-dash-queue-pos", emptyRow("Could not load blocking POs."));
			});
	}

	function loadRfps() {
		return fetchJson("/api/v1/rfps")
			.then(function (data) {
				var items = (data.items || []).filter(function (r) {
					return !CLOSED_RFP[String(r.status || "").toLowerCase()];
				});
				items = items.slice(0, 8);
				if (!items.length) {
					setQueue("usis-dash-queue-rfps", emptyRow("No open RFPs."));
					return;
				}
				setQueue(
					"usis-dash-queue-rfps",
					items
						.map(function (r) {
							var href = "usis-rfp-detail.html?id=" + encodeURIComponent(r.id);
							var label = r.title || "RFP";
							var meta = r.status ? " · " + r.status : "";
							return (
								'<a class="list-group-item list-group-item-action py-2" href="' +
								href +
								'"><span class="d-block text-truncate">' +
								esc(label) +
								'</span><span class="small text-muted">' +
								esc((r.due_at || "").slice(0, 10) + meta) +
								"</span></a>"
							);
						})
						.join("")
				);
			})
			.catch(function () {
				setQueue("usis-dash-queue-rfps", emptyRow("Could not load RFPs."));
			});
	}

	function loadSubmittals() {
		return fetchJson("/api/submittals?overdue=1")
			.then(function (data) {
				var items = (data.items || []).slice(0, 8);
				if (!items.length) {
					setQueue("usis-dash-queue-subs", emptyRow("No overdue submittals."));
					return;
				}
				setQueue(
					"usis-dash-queue-subs",
					items
						.map(function (s) {
							var href =
								"construction/submittal-detail.html?id=" + encodeURIComponent(s.id || "");
							var label = s.submittalNumber || s.title || "Submittal";
							var meta = [s.specSection, s.trade].filter(Boolean).join(" · ");
							return (
								'<a class="list-group-item list-group-item-action py-2" href="' +
								href +
								'"><span class="d-block text-truncate">' +
								esc(label) +
								(s.title && s.title !== label ? " — " + esc(s.title) : "") +
								'</span><span class="small text-muted">' +
								esc(meta || s.status || "") +
								"</span></a>"
							);
						})
						.join("")
				);
			})
			.catch(function () {
				setQueue("usis-dash-queue-subs", emptyRow("Could not load submittals."));
			});
	}

	function taskWhen(item) {
		var raw = item && (item.due || item.created);
		if (!raw) return "";
		var dt = new Date(raw);
		if (isNaN(dt.getTime())) return String(raw).slice(0, 10);
		return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
	}

	function taskHref(item) {
		if (item && item.kind === "flagged_mail") return "usis-email.html";
		var link = item && item.web_link;
		if (link && /^https:\/\//i.test(link)) return link;
		return "https://to-do.office.com/tasks";
	}

	function renderTasks(body) {
		var items = (body && body.items) || [];
		var sources = (body && body.sources) || {};
		var meta = document.getElementById("usis-dash-tasks-meta");
		var notes = [];
		if (sources.todo && sources.todo.ok === false) notes.push("To Do needs Tasks.Read.All");
		if (sources.flagged_mail && sources.flagged_mail.ok === false) notes.push("Flagged mail unavailable");
		if (meta) meta.textContent = notes.join(" · ");
		if (!items.length) {
			var empty = "No Microsoft To Do tasks or flagged Outlook mail.";
			if (notes.length) empty = notes.join(" ") + ".";
			setQueue("usis-dash-tasks-list", emptyRow(empty));
			return;
		}
		setQueue(
			"usis-dash-tasks-list",
			items
				.map(function (item) {
					var kind = item.kind === "flagged_mail" ? "Flagged" : "To Do";
					var href = taskHref(item);
					var extra = item.kind === "flagged_mail" ? item.from || "Outlook" : item.list_name || "To Do";
					var when = taskWhen(item);
					var complete =
						'<button type="button" class="btn btn-sm btn-outline-secondary usis-dash-task-done" data-kind="' +
						esc(item.kind || "") +
						'" data-id="' +
						esc(item.id || "") +
						'" data-list="' +
						esc(item.list_id || "") +
						'">Done</button>';
					var target = item.kind === "flagged_mail" ? "" : ' target="_blank" rel="noopener noreferrer"';
					return (
						'<div class="list-group-item py-2 usis-dash-task">' +
						'<a class="usis-dash-task__main text-decoration-none text-body" href="' +
						esc(href) +
						'"' +
						target +
						"><span class=\"usis-status-chip usis-dash-task__kind\">" +
						esc(kind) +
						'</span><span class="d-block text-truncate">' +
						esc(item.title || "Task") +
						'</span><span class="small text-muted">' +
						esc([extra, when].filter(Boolean).join(" · ")) +
						"</span></a>" +
						complete +
						"</div>"
					);
				})
				.join("")
		);
		document.querySelectorAll("#usis-dash-tasks-list .usis-dash-task-done").forEach(function (btn) {
			btn.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				completeTask(btn);
			});
		});
	}

	function loadMyTasks() {
		if (!document.getElementById("usis-dash-tasks-list")) return Promise.resolve();
		setQueue("usis-dash-tasks-list", emptyRow("Loading…"));
		return fetchJson("/api/v1/me/tasks")
			.then(renderTasks)
			.catch(function (err) {
				var msg = (err && err.message) || "Could not load personal tasks.";
				if (String(msg).indexOf("sign in") !== -1 || String(msg).indexOf("401") === 0) {
					msg = "Sign in with Microsoft to see To Do and flagged Outlook mail.";
				}
				setQueue("usis-dash-tasks-list", emptyRow(msg));
			});
	}

	function completeTask(btn) {
		if (!btn || btn.disabled) return;
		btn.disabled = true;
		fetchJson("/api/v1/me/tasks/complete", {
			method: "POST",
			body: {
				kind: btn.getAttribute("data-kind"),
				id: btn.getAttribute("data-id"),
				list_id: btn.getAttribute("data-list") || undefined,
			},
		})
			.then(function () {
				loadMyTasks();
			})
			.catch(function () {
				btn.disabled = false;
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		if (!document.getElementById("usis-dashboard-dark-page")) return;
		loadKpis();
		loadRfps();
		loadSubmittals();
		loadMyTasks();
		var refresh = document.getElementById("usis-dash-tasks-refresh");
		if (refresh) refresh.addEventListener("click", loadMyTasks);
	});
})();
