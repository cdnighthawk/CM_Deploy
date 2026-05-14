(function () {
	"use strict";

	function apiBase() {
		if (window.location.protocol === "file:") return "http://127.0.0.1:5000";
		return "";
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function qs(name) {
		var m = new RegExp("[?&]" + name + "=([^&]*)").exec(window.location.search);
		return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
	}

	function showErr(msg) {
		var el = document.getElementById("usis-pbr-alert");
		if (!el) return;
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function esc(s) {
		if (s == null) return "";
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	var runId = qs("run_id");
	var state = { run: null, users: [] };

	function loadUsers(cb) {
		fetch(apiBase() + "/api/v1/rfi-users", { credentials: "omit" })
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				state.users = data.items || data || [];
				if (cb) cb();
			})
			.catch(function () {
				state.users = [];
				if (cb) cb();
			});
	}

	function userLabel(uid) {
		if (!uid) return "—";
		var u = state.users.find(function (x) {
			return x.id === uid;
		});
		if (u) return (u.first_name || "") + " " + (u.last_name || "") + " · " + (u.email || "");
		return uid.slice(0, 8) + "…";
	}

	function loadRun() {
		if (!runId) return;
		fetch(apiBase() + "/api/v1/playbooks/runs/" + encodeURIComponent(runId), {
			credentials: "omit",
			headers: actorHeaders(),
		})
			.then(function (r) {
				if (!r.ok) return r.json().then(function (j) {
					throw new Error(j.error || "HTTP " + r.status);
				});
				return r.json();
			})
			.then(function (data) {
				state.run = data.item;
				document.getElementById("usis-pbr-empty").classList.add("d-none");
				document.getElementById("usis-pbr-main").classList.remove("d-none");
				document.getElementById("usis-pbr-title").textContent = data.item.title || "";
				document.getElementById("usis-pbr-meta").textContent =
					"Status: " +
					data.item.status +
					(data.item.is_blocked ? " · Blocked" : "") +
					(data.item.project_id ? " · Project " + data.item.project_id : "");
				var pct = data.item.progress_percent != null ? data.item.progress_percent : 0;
				var bar = document.getElementById("usis-pbr-progress");
				bar.style.width = pct + "%";
				bar.setAttribute("aria-valuenow", String(pct));
				renderSteps(data.item.steps || []);
			})
			.catch(function (err) {
				showErr(err.message || String(err));
			});
	}

	function patchStep(stepId, body) {
		return fetch(
			apiBase() +
				"/api/v1/playbooks/runs/" +
				encodeURIComponent(runId) +
				"/steps/" +
				encodeURIComponent(stepId),
			{
				method: "PATCH",
				credentials: "omit",
				headers: Object.assign({ "Content-Type": "application/json" }, actorHeaders()),
				body: JSON.stringify(body),
			}
		).then(function (r) {
			if (!r.ok) return r.json().then(function (j) {
				throw new Error(j.error || "HTTP " + r.status);
			});
			return r.json();
		});
	}

	function patchRun(body) {
		return fetch(apiBase() + "/api/v1/playbooks/runs/" + encodeURIComponent(runId), {
			method: "PATCH",
			credentials: "omit",
			headers: Object.assign({ "Content-Type": "application/json" }, actorHeaders()),
			body: JSON.stringify(body),
		}).then(function (r) {
			if (!r.ok) return r.json().then(function (j) {
				throw new Error(j.error || "HTTP " + r.status);
			});
			return r.json();
		});
	}

	function renderSteps(steps) {
		var tbody = document.getElementById("usis-pbr-steps-body");
		if (!tbody) return;
		tbody.innerHTML = "";
		steps
			.slice()
			.sort(function (a, b) {
				return a.sequence - b.sequence;
			})
			.forEach(function (s) {
				var tr = document.createElement("tr");
				var actions = "";
				if (s.status === "pending") {
					actions =
						'<button type="button" class="btn btn-sm btn-success usis-pbr-done" data-id="' +
						esc(s.id) +
						'">Done</button> <button type="button" class="btn btn-sm btn-outline-secondary usis-pbr-skip" data-id="' +
						esc(s.id) +
						'">Skip</button>';
				} else {
					actions =
						'<button type="button" class="btn btn-sm btn-outline-warning usis-pbr-reopen" data-id="' +
						esc(s.id) +
						'">Reopen</button>';
				}
				tr.innerHTML =
					"<td>" +
					s.sequence +
					"</td><td><strong>" +
					esc(s.title) +
					"</strong>" +
					(s.body ? '<div class="text-muted small">' + esc(s.body) + "</div>" : "") +
					"</td><td class=\"small\">" +
					esc(userLabel(s.assignee_user_id)) +
					'</td><td><span class="badge bg-light text-dark">' +
					esc(s.status) +
					"</span></td><td>" +
					actions +
					"</td>";
				tbody.appendChild(tr);
			});
		tbody.querySelectorAll(".usis-pbr-done").forEach(function (btn) {
			btn.addEventListener("click", function () {
				patchStep(btn.getAttribute("data-id"), { status: "done" })
					.then(function () {
						loadRun();
					})
					.catch(function (e) {
						showErr(e.message);
					});
			});
		});
		tbody.querySelectorAll(".usis-pbr-skip").forEach(function (btn) {
			btn.addEventListener("click", function () {
				patchStep(btn.getAttribute("data-id"), { status: "skipped" })
					.then(function () {
						loadRun();
					})
					.catch(function (e) {
						showErr(e.message);
					});
			});
		});
		tbody.querySelectorAll(".usis-pbr-reopen").forEach(function (btn) {
			btn.addEventListener("click", function () {
				patchStep(btn.getAttribute("data-id"), { status: "pending" })
					.then(function () {
						loadRun();
					})
					.catch(function (e) {
						showErr(e.message);
					});
			});
		});
	}

	function init() {
		if (!runId) return;
		loadUsers(function () {
			loadRun();
		});
		var blk = document.getElementById("usis-pbr-block");
		var can = document.getElementById("usis-pbr-cancel");
		if (blk) {
			blk.classList.remove("d-none");
			blk.addEventListener("click", function () {
				patchRun({ is_blocked: state.run ? !state.run.is_blocked : true })
					.then(function (d) {
						state.run = d.item;
						loadRun();
					})
					.catch(function (e) {
						showErr(e.message);
					});
			});
		}
		if (can) {
			can.classList.remove("d-none");
			can.addEventListener("click", function () {
				if (!window.confirm("Cancel this run?")) return;
				patchRun({ status: "cancelled" })
					.then(function () {
						loadRun();
					})
					.catch(function (e) {
						showErr(e.message);
					});
			});
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
