/**
 * Wave 1 Sage CM: job cost codes, CPR/CO, directory, daily log, SCO.
 */
(function () {
	"use strict";

	function api() {
		return window.USIS_API || {};
	}

	function projectId() {
		if (window.USISProjectContext && typeof window.USISProjectContext.projectIdFromQuery === "function") {
			return window.USISProjectContext.projectIdFromQuery();
		}
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim() || null;
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function money(n) {
		if (n == null || n === "") return "—";
		var x = Number(n);
		if (isNaN(x)) return String(n);
		return x.toLocaleString(undefined, { style: "currency", currency: "USD" });
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function pidPath(suffix) {
		return "/api/v1/projects/" + encodeURIComponent(projectId()) + suffix;
	}

	function emptyRow(cols, msg) {
		return '<tr><td colspan="' + cols + '" class="text-muted">' + esc(msg) + "</td></tr>";
	}

	function linesToList(text) {
		return String(text || "")
			.split("\n")
			.map(function (s) {
				return s.trim();
			})
			.filter(Boolean)
			.map(function (line) {
				return { notes: line };
			});
	}

	function listToLines(arr) {
		if (!arr) return "";
		if (typeof arr === "string") return arr;
		if (!Array.isArray(arr)) return "";
		return arr
			.map(function (x) {
				if (typeof x === "string") return x;
				if (x.company || x.count) {
					return [x.company, x.count, x.notes].filter(Boolean).join(" — ");
				}
				return x.notes || x.name || x.description || "";
			})
			.filter(Boolean)
			.join("\n");
	}

	function loadJcc() {
		var tbody = document.getElementById("usis-jcc-tbody");
		if (!tbody || !projectId()) return Promise.resolve();
		return fetchJson(pidPath("/rfi-lookups/cost_codes"))
			.then(function (data) {
				var items = (data && data.items) || data || [];
				if (!Array.isArray(items)) items = [];
				if (!items.length) {
					tbody.innerHTML = emptyRow(7, "No takeoff cost codes yet. Assign codes on takeoff lines.");
					return;
				}
				tbody.innerHTML = items
					.map(function (cc) {
						var warn = cc.in_company_list === false ? ' <span class="text-muted">(not in company list)</span>' : "";
						return (
							'<tr data-id="' +
							esc(cc.id) +
							'"><td>' +
							esc(cc.order_number != null ? cc.order_number : "") +
							"</td><td>" +
							esc(cc.code || "") +
							"</td><td>" +
							esc(cc.description || "") +
							warn +
							"</td><td>" +
							esc(cc.quantity != null ? cc.quantity : "") +
							"</td><td>" +
							esc(cc.units || "") +
							'</td><td class="text-end">' +
							money(cc.revenue_budget) +
							'</td><td class="text-end">' +
							esc(cc.takeoff_line_count != null ? cc.takeoff_line_count : "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(7, "Could not load cost codes.");
			});
	}

	function renderChangeRows(tbody, items, cols, convert) {
		if (!tbody) return;
		if (!items || !items.length) {
			tbody.innerHTML = emptyRow(cols, "None yet.");
			return;
		}
		tbody.innerHTML = items
			.map(function (it) {
				var extra = convert
					? '<td><button type="button" class="btn btn-link btn-sm p-0 usis-cpr-to-co" data-id="' +
						esc(it.id) +
						'">To prime CO</button></td>'
					: "";
				return (
					"<tr><td>" +
					esc(it.number || "") +
					"</td><td>" +
					esc(it.subject || it.title || "") +
					"</td><td>" +
					esc(it.status || "") +
					"</td><td class=\"text-end\">" +
					money(it.amount) +
					"</td>" +
					extra +
					"</tr>"
				);
			})
			.join("");
	}

	function loadCprs() {
		var tbody = document.getElementById("usis-ca-cpr-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/cprs"))
			.then(function (data) {
				renderChangeRows(tbody, data.items || [], 5, true);
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(5, "Could not load CPRs.");
			});
	}

	function loadCos() {
		var tbody = document.getElementById("usis-ca-co-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/change-orders"))
			.then(function (data) {
				renderChangeRows(tbody, data.items || [], 4, false);
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(4, "Could not load change orders.");
			});
	}

	function addCpr() {
		var subject = window.prompt("CPR subject");
		if (!subject) return;
		var amount = window.prompt("Amount (optional)") || "0";
		fetchJson(pidPath("/cprs"), {
			method: "POST",
			body: {
				subject: subject.trim(),
				items: [{ description: subject.trim(), quantity: 1, unit_price: amount }],
			},
		})
			.then(loadCprs)
			.catch(function (err) {
				window.alert((err && err.body) || "Could not create CPR.");
			});
	}

	function addCo() {
		var subject = window.prompt("Prime CO subject");
		if (!subject) return;
		var amount = window.prompt("Amount (optional)") || "0";
		fetchJson(pidPath("/change-orders"), {
			method: "POST",
			body: {
				subject: subject.trim(),
				status: "draft",
				items: [{ description: subject.trim(), quantity: 1, unit_price: amount }],
			},
		})
			.then(loadCos)
			.catch(function (err) {
				window.alert((err && err.body) || "Could not create change order.");
			});
	}

	function cprToCo(cprId) {
		fetchJson(pidPath("/change-orders"), { method: "POST", body: { cpr_id: cprId } })
			.then(function () {
				loadCos();
				loadCprs();
			})
			.catch(function (err) {
				window.alert((err && err.body) || "Could not convert CPR.");
			});
	}

	function loadDirectory() {
		var tbody = document.getElementById("usis-ca-dir-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/directory/companies?all=1"))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = emptyRow(3, "No companies in the project directory.");
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
						return (
							"<tr><td>" +
							esc(it.name) +
							"</td><td>" +
							esc(it.company_type || "") +
							"</td><td>" +
							esc(it.directory_role || "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(3, "Could not load directory.");
			});
	}

	var dailyReportId = null;

	function loadDailyLog() {
		var dateEl = document.getElementById("usis-dailylog-date");
		if (!dateEl || !projectId()) return;
		if (!dateEl.value) {
			var d = new Date();
			dateEl.value =
				d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
		}
		fetchJson(pidPath("/daily-reports?date=" + encodeURIComponent(dateEl.value)))
			.then(function (data) {
				var item = data.item || data;
				dailyReportId = item.id;
				var sec = item.sections || {};
				var weather = sec.weather || {};
				document.getElementById("usis-dailylog-weather").value = weather.notes || weather.conditions || "";
				document.getElementById("usis-dailylog-work").value = typeof sec.work_performed === "string" ? sec.work_performed : "";
				document.getElementById("usis-dailylog-manpower").value = listToLines(sec.manpower);
				document.getElementById("usis-dailylog-equipment").value = listToLines(sec.equipment);
				document.getElementById("usis-dailylog-deliveries").value = listToLines(sec.deliveries);
				document.getElementById("usis-dailylog-visitors").value = listToLines(sec.visitors);
				document.getElementById("usis-dailylog-delays").value = typeof sec.delays === "string" ? sec.delays : listToLines(sec.delays);
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Loaded " + (item.date || dateEl.value) + " (" + (item.status || "draft") + ").";
			})
			.catch(function () {
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Could not load daily log.";
			});
	}

	function prefillDailyLog() {
		var dateEl = document.getElementById("usis-dailylog-date");
		var box = document.getElementById("usis-dailylog-manpower");
		var st = document.getElementById("usis-dailylog-status");
		if (!box || !projectId()) return;
		var day = (dateEl && dateEl.value) || "";
		if (!day) {
			var d = new Date();
			day = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
		}
		fetchJson("/api/time/projects/" + encodeURIComponent(projectId()) + "/manpower-prefill?date=" + encodeURIComponent(day))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					if (st) st.textContent = "No punches on " + day + " to prefill.";
					return;
				}
				var lines = items.map(function (it) {
					return (it.company || "USIS") + " — " + (it.count || 1) + " — " + (it.notes || "");
				});
				box.value = lines.join("\n");
				if (st) st.textContent = "Prefill from " + items.length + " punch" + (items.length === 1 ? "" : "es") + ". Save to keep.";
			})
			.catch(function () {
				if (st) st.textContent = "Could not prefill from punches.";
			});
	}

	function saveDailyLog() {
		if (!dailyReportId) {
			loadDailyLog();
			return;
		}
		var weather = (document.getElementById("usis-dailylog-weather") || {}).value || "";
		fetchJson("/api/v1/daily-reports/" + encodeURIComponent(dailyReportId), {
			method: "PUT",
			body: {
				sections: {
					weather: { notes: weather, conditions: weather },
					work_performed: (document.getElementById("usis-dailylog-work") || {}).value || "",
					manpower: linesToList((document.getElementById("usis-dailylog-manpower") || {}).value),
					equipment: linesToList((document.getElementById("usis-dailylog-equipment") || {}).value),
					deliveries: linesToList((document.getElementById("usis-dailylog-deliveries") || {}).value),
					visitors: linesToList((document.getElementById("usis-dailylog-visitors") || {}).value),
					delays: (document.getElementById("usis-dailylog-delays") || {}).value || "",
				},
			},
		})
			.then(function () {
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Saved.";
			})
			.catch(function () {
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Save failed.";
			});
	}

	function loadScos() {
		var tbody = document.getElementById("usis-sco-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/scos"))
			.then(function (data) {
				renderChangeRows(tbody, data.items || [], 4, false);
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(4, "Could not load SCOs.");
			});
	}

	function addSco() {
		var commitmentId = window.prompt("Subcontract commitment UUID");
		if (!commitmentId) return;
		var subject = window.prompt("SCO subject");
		if (!subject) return;
		var amount = window.prompt("Amount (optional)") || "0";
		fetchJson(pidPath("/scos"), {
			method: "POST",
			body: {
				commitment_id: commitmentId.trim(),
				subject: subject.trim(),
				items: [{ description: subject.trim(), quantity: 1, unit_price: amount }],
			},
		})
			.then(loadScos)
			.catch(function (err) {
				window.alert((err && err.body) || "Could not create SCO.");
			});
	}

	function onReady() {
		if (!projectId()) return;
		loadJcc();
		loadCprs();
		loadCos();
		loadDirectory();
		loadDailyLog();
		loadScos();

		var addCprBtn = document.getElementById("usis-ca-cpr-add");
		if (addCprBtn) addCprBtn.addEventListener("click", addCpr);
		var addCoBtn = document.getElementById("usis-ca-co-add");
		if (addCoBtn) addCoBtn.addEventListener("click", addCo);
		var cprBody = document.getElementById("usis-ca-cpr-tbody");
		if (cprBody) {
			cprBody.addEventListener("click", function (e) {
				var btn = e.target.closest(".usis-cpr-to-co");
				if (btn) cprToCo(btn.getAttribute("data-id"));
			});
		}
		var saveDl = document.getElementById("usis-dailylog-save");
		if (saveDl) saveDl.addEventListener("click", saveDailyLog);
		var prefillDl = document.getElementById("usis-dailylog-prefill");
		if (prefillDl) prefillDl.addEventListener("click", prefillDailyLog);
		var dateEl = document.getElementById("usis-dailylog-date");
		if (dateEl) dateEl.addEventListener("change", loadDailyLog);
		var addScoBtn = document.getElementById("usis-sco-add");
		if (addScoBtn) addScoBtn.addEventListener("click", addSco);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
