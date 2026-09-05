/**
 * Safety hub — loads GET /api/v1/safety/summary and recent daily pretasks.
 */
(function () {
	"use strict";

	function api() {
		return window.USIS_API;
	}

	function setErr(msg) {
		var el = document.getElementById("usis-safety-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
			el.textContent = "";
		}
	}

	function setText(sel, value) {
		var el = document.querySelector(sel);
		if (el) el.textContent = value == null ? "—" : String(value);
	}

	function statusChip(status) {
		var st = String(status || "draft").toLowerCase();
		var cls = st === "submitted" ? "usis-status-chip--success" : "usis-status-chip--draft";
		return '<span class="usis-status-chip ' + cls + '">' + (st === "submitted" ? "Submitted" : "Draft") + "</span>";
	}

	function esc(s) {
		return String(s || "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function renderRecent(items) {
		var tbody = document.getElementById("usis-safety-recent-body");
		if (!tbody) return;
		if (!items || !items.length) {
			tbody.innerHTML =
				'<tr><td colspan="6" class="text-muted text-center py-4">No daily pretasks yet. Open a job and file today\'s plan before work starts.</td></tr>';
			return;
		}
		tbody.innerHTML = items
			.map(function (row) {
				var href = "usis-daily-pretask.html?id=" + encodeURIComponent(row.id);
				var job = (row.project_number ? row.project_number + " — " : "") + (row.project_name || "Project");
				return (
					"<tr>" +
					'<td><a href="' +
					href +
					'">' +
					esc(row.work_date) +
					"</a></td>" +
					"<td>" +
					esc(job) +
					"</td>" +
					"<td>" +
					esc(row.area_of_work) +
					"</td>" +
					"<td>" +
					esc(row.crew_lead_name) +
					"</td>" +
					"<td>" +
					statusChip(row.status) +
					"</td>" +
					'<td class="text-end">' +
					(window.USISUi && window.USISUi.rowMenu
						? window.USISUi.rowMenu({
								id: row.id,
								editHref: href,
								createHref: "usis-daily-pretask.html",
								deleteClass: "usis-safety-del",
							})
						: '<a class="btn btn-sm btn-outline-primary" href="' + href + '">Open</a>') +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
	}

	function load() {
		setErr("");
		if (!api() || typeof api().fetchJson !== "function") {
			setErr("API helper failed to load.");
			return;
		}
		api()
			.fetchJson("/api/v1/safety/summary")
			.then(function (body) {
				var counts = (body && body.counts) || {};
				setText("[data-usis-safety-k=open_incidents]", counts.open_incidents);
				setText("[data-usis-safety-k=observations_this_week]", counts.observations_this_week);
				setText("[data-usis-safety-k=expiring_certs_30d]", counts.expiring_certs_30d);
				setText("[data-usis-safety-k=training_overdue]", counts.training_overdue);
				setText("[data-usis-safety-k=pretasks_today]", counts.pretasks_today);
				setText("[data-usis-safety-k=pretasks_submitted_today]", counts.pretasks_submitted_today);
				setText("[data-usis-safety-k=pretasks_this_week]", counts.pretasks_this_week);
				renderRecent(body.recent_pretasks || []);
			})
			.catch(function (err) {
				var msg = (err && err.message) || "Could not load safety summary.";
				if (String(msg).indexOf("401") !== -1 || String(msg).indexOf("403") !== -1) {
					msg = "Sign in with Safety access, or set localStorage usisActorUserId for local testing.";
				}
				setErr(msg);
			});
	}

	function wire() {
		var reload = document.getElementById("usis-safety-reload");
		if (reload) reload.addEventListener("click", load);
		load();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
	else wire();
})();
