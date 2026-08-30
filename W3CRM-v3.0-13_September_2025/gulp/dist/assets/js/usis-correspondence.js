(function () {
	"use strict";

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function fetchJson(path, opts) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path, opts || {});
		return fetch(path, { credentials: "include", headers: { Accept: "application/json" } }).then(function (r) {
			return r.json();
		});
	}

	function projectId() {
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim();
	}

	function fmtDate(iso) {
		if (!iso) return "—";
		try {
			return new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
		} catch (e) {
			return String(iso);
		}
	}

	function renderRows(items, tbodyId, opts) {
		opts = opts || {};
		var tb = document.getElementById(tbodyId);
		if (!tb) return;
		tb.innerHTML = "";
		if (!items.length) {
			tb.innerHTML = '<tr><td colspan="6" class="text-muted small">No correspondence files.</td></tr>';
			return;
		}
		items.forEach(function (row) {
			var fileBtn = opts.showFile && row.unfiled
				? '<button type="button" class="btn btn-link btn-sm p-0 usis-corr-file" data-id="' +
					esc(row.id) +
					'">File to project</button>'
				: "";
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td>" +
				esc(fmtDate(row.sentAt)) +
				"</td><td>" +
				esc(row.fromName || row.fromEmail || "—") +
				"</td><td>" +
				esc(row.subject || "") +
				"</td><td>" +
				(opts.showProject ? esc(row.projectName || (row.unfiled ? "Unfiled" : "—")) + "</td><td>" : "") +
				esc(row.attachmentCount || 0) +
				'</td><td class="text-end text-nowrap"><a class="btn btn-sm btn-outline-secondary" href="' +
				esc(row.downloadUrl) +
				'">Download</a> ' +
				fileBtn +
				"</td>";
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-corr-file").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var pid = window.prompt("Project UUID to file this message to");
				if (!pid) return;
				fetchJson("/api/correspondence/" + encodeURIComponent(btn.getAttribute("data-id")) + "/file", {
					method: "POST",
					body: { project_id: pid.trim() },
				})
					.then(function () {
						loadHub();
					})
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(e.message || String(e));
					});
			});
		});
	}

	function loadProject() {
		var pid = projectId();
		var tb = document.getElementById("usis-proj-corr-tbody");
		if (!tb || !pid) return;
		fetchJson("/api/correspondence?project_id=" + encodeURIComponent(pid))
			.then(function (body) {
				renderRows(body.items || [], "usis-proj-corr-tbody", { showProject: false, showFile: false });
			})
			.catch(function () {
				tb.innerHTML = '<tr><td colspan="5" class="text-danger small">Could not load correspondence.</td></tr>';
			});
	}

	function loadHub() {
		var tb = document.getElementById("usis-corr-tbody");
		if (!tb) return;
		var q = (document.getElementById("usis-corr-q") || {}).value || "";
		var unfiled = document.getElementById("usis-corr-unfiled");
		var path = "/api/correspondence?q=" + encodeURIComponent(q);
		if (unfiled && unfiled.checked) path += "&unfiled=1";
		fetchJson(path)
			.then(function (body) {
				renderRows(body.items || [], "usis-corr-tbody", { showProject: true, showFile: true });
			})
			.catch(function () {
				tb.innerHTML = '<tr><td colspan="6" class="text-danger small">Could not load correspondence.</td></tr>';
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		if (document.getElementById("usis-proj-corr-tbody")) {
			loadProject();
			var tab = document.getElementById("proj-tab-correspondence");
			if (tab) tab.addEventListener("shown.bs.tab", loadProject);
		}
		if (document.getElementById("usis-corr-tbody")) {
			loadHub();
			var apply = document.getElementById("usis-corr-apply");
			if (apply) apply.addEventListener("click", loadHub);
			var sync = document.getElementById("usis-corr-sync");
			if (sync) {
				sync.addEventListener("click", function () {
					fetchJson("/api/correspondence/sync", { method: "POST", body: {} })
						.then(function (body) {
							if (window.USISNotify) window.USISNotify.success("Ingested " + (body.created || 0) + " messages");
							loadHub();
						})
						.catch(function (e) {
							if (window.USISNotify) window.USISNotify.error(e.message || String(e));
						});
				});
			}
		}
	});
})();
